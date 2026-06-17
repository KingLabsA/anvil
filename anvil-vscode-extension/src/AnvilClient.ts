import WebSocket from 'ws';
import { EventEmitter } from 'events';
import {
  AnvilMessage,
  ConnectionStatus,
  RequestPayload,
  ResponsePayload,
  StatusPayload,
  StreamPayload,
} from './types';
import { getWebSocketUrl } from './config';

let messageIdCounter = 0;

function generateId(): string {
  return `msg_${Date.now()}_${++messageIdCounter}`;
}

export class AnvilClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private status: ConnectionStatus = 'disconnected';
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private pendingRequests = new Map<string, {
    resolve: (value: ResponsePayload) => void;
    reject: (error: Error) => void;
    timeout: NodeJS.Timeout;
    onStream?: (chunk: StreamPayload) => void;
  }>();
  private serverUrl: string;
  private requestTimeout = 60000;

  constructor(serverUrl: string) {
    super();
    this.serverUrl = serverUrl;
  }

  get connectionStatus(): ConnectionStatus {
    return this.status;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      this.setStatus('connecting');
      const wsUrl = getWebSocketUrl(this.serverUrl);

      try {
        this.ws = new WebSocket(wsUrl, {
          handshakeTimeout: 10000,
        });

        this.ws.on('open', () => {
          this.reconnectAttempts = 0;
          this.setStatus('connected');
          this.emit('connected');
          resolve();
        });

        this.ws.on('message', (data: WebSocket.Data) => {
          this.handleMessage(data);
        });

        this.ws.on('close', (code: number, reason: Buffer) => {
          this.setStatus('disconnected');
          this.emit('disconnected', { code, reason: reason.toString() });
          this.rejectAllPending('Connection closed');
          this.scheduleReconnect();
        });

        this.ws.on('error', (error: Error) => {
          this.setStatus('error');
          this.emit('error', error);
          if (this.status === 'connecting') {
            reject(error);
          }
        });

        this.ws.on('pong', () => {
          this.emit('heartbeat');
        });
      } catch (error) {
        this.setStatus('error');
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.clearReconnectTimer();
    this.rejectAllPending('Client disconnected');

    if (this.ws) {
      this.ws.removeAllListeners();
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close(1000, 'Client disconnect');
      }
      this.ws = null;
    }

    this.setStatus('disconnected');
  }

  async send(
    action: RequestPayload,
    options?: {
      timeout?: number;
      onStream?: (chunk: StreamPayload) => void;
    }
  ): Promise<ResponsePayload> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('Not connected to Anvil server');
    }

    const id = generateId();
    const message: AnvilMessage = {
      type: 'request',
      id,
      payload: action,
      timestamp: Date.now(),
    };

    const timeout = options?.timeout ?? this.requestTimeout;

    return new Promise<ResponsePayload>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Request timed out after ${timeout}ms`));
      }, timeout);

      this.pendingRequests.set(id, {
        resolve,
        reject,
        timeout: timer,
        onStream: options?.onStream,
      });

      try {
        this.ws!.send(JSON.stringify(message));
      } catch (error) {
        clearTimeout(timer);
        this.pendingRequests.delete(id);
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  }

  cancelRequest(id: string): void {
    const cancelMsg: AnvilMessage = {
      type: 'cancel',
      id: generateId(),
      payload: { requestId: id },
      timestamp: Date.now(),
    };

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(cancelMsg));
    }
  }

  updateServerUrl(url: string): void {
    this.serverUrl = url;
  }

  private handleMessage(data: WebSocket.Data): void {
    try {
      const message: AnvilMessage = JSON.parse(data.toString());

      switch (message.type) {
        case 'response':
          this.handleResponse(message);
          break;
        case 'stream':
          this.handleStream(message);
          break;
        case 'stream_end':
          this.handleStreamEnd(message);
          break;
        case 'error':
          this.handleError(message);
          break;
        case 'status':
          this.handleStatus(message);
          break;
        default:
          this.emit('message', message);
      }
    } catch (error) {
      this.emit('error', new Error(`Failed to parse message: ${error}`));
    }
  }

  private handleResponse(message: AnvilMessage): void {
    const pending = this.pendingRequests.get(message.id);
    if (pending) {
      clearTimeout(pending.timeout);
      this.pendingRequests.delete(message.id);
      pending.resolve(message.payload as ResponsePayload);
    }
    this.emit('response', message);
  }

  private handleStream(message: AnvilMessage): void {
    const pending = this.pendingRequests.get(message.id);
    if (pending?.onStream) {
      pending.onStream(message.payload as StreamPayload);
    }
    this.emit('stream', message);
  }

  private handleStreamEnd(message: AnvilMessage): void {
    const pending = this.pendingRequests.get(message.id);
    if (pending) {
      clearTimeout(pending.timeout);
      this.pendingRequests.delete(message.id);
      pending.resolve(message.payload as ResponsePayload);
    }
    this.emit('stream_end', message);
  }

  private handleError(message: AnvilMessage): void {
    const payload = message.payload as ResponsePayload;
    const pending = this.pendingRequests.get(message.id);
    if (pending) {
      clearTimeout(pending.timeout);
      this.pendingRequests.delete(message.id);
      pending.reject(new Error(payload.error ?? 'Unknown error'));
    }
    this.emit('error', new Error(payload.error ?? 'Unknown server error'));
  }

  private handleStatus(message: AnvilMessage): void {
    const status = message.payload as StatusPayload;
    if (status.status) {
      this.setStatus(status.status);
    }
    this.emit('status', status);
  }

  private setStatus(status: ConnectionStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.emit('statusChange', status);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.emit('reconnect_failed');
      return;
    }

    this.clearReconnectTimer();
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(async () => {
      try {
        await this.connect();
      } catch {
        // Error handled in on('error')
      }
    }, delay);

    this.emit('reconnecting', { attempt: this.reconnectAttempts, delay });
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private rejectAllPending(reason: string): void {
    for (const [id, pending] of this.pendingRequests) {
      clearTimeout(pending.timeout);
      pending.reject(new Error(reason));
    }
    this.pendingRequests.clear();
  }
}
