/**
 * Anvil TypeScript SDK
 * 
 * @example
 * ```typescript
 * import { AnvilClient } from '@anvil-ai/sdk';
 * 
 * const anvil = new AnvilClient({
 *   baseUrl: 'http://localhost:8765',
 *   model: 'local',
 *   maxIterations: 20
 * });
 * 
 * // Synchronous execution
 * const result = await anvil.run('Fix the bug in main.py');
 * console.log(result.success, result.output);
 * 
 * // Streaming execution
 * for await (const message of anvil.stream('Create a new feature')) {
 *   if (message.type === 'step') {
 *     console.log('Step:', message.step?.content);
 *   }
 * }
 * ```
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  AnvilConfig,
  RunRequest,
  RunResponse,
  Session,
  SessionInfo,
  HealthResponse,
  StreamMessage
} from './types';

export class AnvilClient {
  private client: AxiosInstance;
  private config: Required<AnvilConfig>;

  constructor(config: AnvilConfig = {}) {
    this.config = {
      baseUrl: config.baseUrl || 'http://localhost:8765',
      timeout: config.timeout || 30000,
      model: config.model || 'local',
      maxIterations: config.maxIterations || 20,
      verify: config.verify !== undefined ? config.verify : true
    };

    this.client = axios.create({
      baseURL: this.config.baseUrl,
      timeout: this.config.timeout,
      headers: {
        'Content-Type': 'application/json'
      }
    });
  }

  /**
   * Execute a task synchronously
   * 
   * @param task - Task description
   * @param options - Optional overrides for model, maxIterations, verify
   * @returns Execution result
   */
  async run(
    task: string,
    options: {
      model?: string;
      maxIterations?: number;
      verify?: boolean;
    } = {}
  ): Promise<RunResponse> {
    const request: RunRequest = {
      task,
      model: options.model || this.config.model,
      max_iterations: options.maxIterations || this.config.maxIterations,
      verify: options.verify !== undefined ? options.verify : this.config.verify
    };

    try {
      const response = await this.client.post<RunResponse>('/run', request);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Execute a task with streaming via WebSocket
   * 
   * @param task - Task description
   * @param options - Optional overrides
   * @yields Stream messages (status, step, result, error)
   */
  async *stream(
    task: string,
    options: {
      model?: string;
      maxIterations?: number;
    } = {}
  ): AsyncGenerator<StreamMessage, void, unknown> {
    const wsUrl = this.config.baseUrl.replace(/^http/, 'ws') + '/stream';
    
    // Dynamic import for WebSocket (works in both Node.js and browser)
    let WebSocketClass: any;
    if (typeof window !== 'undefined' && window.WebSocket) {
      WebSocketClass = window.WebSocket;
    } else {
      const wsModule = await import('ws');
      WebSocketClass = wsModule.default || wsModule.WebSocket;
    }

    const ws = new WebSocketClass(wsUrl);
    const messageQueue: StreamMessage[] = [];
    let resolveNext: ((value: IteratorResult<StreamMessage>) => void) | null = null;
    let isDone = false;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        task,
        model: options.model || this.config.model,
        max_iterations: options.maxIterations || this.config.maxIterations
      }));
    };

    ws.onmessage = (event: any) => {
      const message: StreamMessage = JSON.parse(event.data);
      
      if (resolveNext) {
        resolveNext({ value: message, done: false });
        resolveNext = null;
      } else {
        messageQueue.push(message);
      }
      
      if (message.type === 'result' || message.type === 'error') {
        isDone = true;
        ws.close();
      }
    };

    ws.onerror = (error: any) => {
      const errorMsg: StreamMessage = {
        type: 'error',
        error: `WebSocket error: ${error.message || error}`
      };
      if (resolveNext) {
        resolveNext({ value: errorMsg, done: false });
        resolveNext = null;
      }
      isDone = true;
    };

    ws.onclose = () => {
      isDone = true;
      if (resolveNext) {
        resolveNext({ value: undefined as any, done: true });
        resolveNext = null;
      }
    };

    try {
      while (!isDone || messageQueue.length > 0) {
        if (messageQueue.length > 0) {
          yield messageQueue.shift()!;
        } else if (!isDone) {
          yield await new Promise<StreamMessage>((resolve) => {
            resolveNext = (result) => {
              if (result.done) {
                resolve(undefined as any);
              } else {
                resolve(result.value);
              }
            };
          });
        }
      }
    } finally {
      if (ws.readyState === WebSocketClass.OPEN) {
        ws.close();
      }
    }
  }

  /**
   * Retrieve a session by ID
   * 
   * @param sessionId - Session ID
   * @returns Session data
   */
  async getSession(sessionId: string): Promise<Session> {
    try {
      const response = await this.client.get<Session>(`/sessions/${sessionId}`);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * List recent sessions
   * 
   * @param limit - Maximum number of sessions to return (default: 50)
   * @returns Array of session info
   */
  async listSessions(limit: number = 50): Promise<SessionInfo[]> {
    try {
      const response = await this.client.get<SessionInfo[]>('/sessions', {
        params: { limit }
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Check server health
   * 
   * @returns Health status
   */
  async health(): Promise<HealthResponse> {
    try {
      const response = await this.client.get<HealthResponse>('/health');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Update client configuration
   * 
   * @param config - New configuration options
   */
  configure(config: Partial<AnvilConfig>): void {
    this.config = { ...this.config, ...config };
    this.client.defaults.baseURL = this.config.baseUrl;
    this.client.defaults.timeout = this.config.timeout;
  }

  /**
   * Handle HTTP errors
   */
  private handleError(error: unknown): Error {
    // Check if it's an axios error by checking for response/request properties
    const err = error as any;
    
    if (err?.response) {
      // Server responded with error status
      const data = err.response.data;
      const message = data?.detail || data?.error || err.message;
      return new Error(`Anvil error (${err.response.status}): ${message}`);
    } else if (err?.request) {
      // Request made but no response
      return new Error(`Anvil server not reachable at ${this.config.baseUrl}`);
    }
    
    // Other errors
    return error instanceof Error ? error : new Error(String(error));
  }
}

// Export types
export * from './types';

// Default export
export default AnvilClient;
