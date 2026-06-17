import * as vscode from 'vscode';
import { AnvilClient } from './AnvilClient';
import { getConfig, resolveTheme } from './config';
import {
  Action,
  ConnectionStatus,
  RequestPayload,
  ResponsePayload,
  StreamPayload,
  WebViewMessage,
} from './types';

export class AnvilProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'anvil.panel';

  private view?: vscode.WebviewView;
  private outputBuffer = '';

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly client: AnvilClient
  ) {
    this.setupClientListeners();
  }

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this.view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [
        vscode.Uri.joinPath(this.extensionUri, 'media'),
      ],
    };

    webviewView.webview.html = this.getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(
      (message: WebViewMessage) => this.handleWebViewMessage(message),
      undefined,
    );

    webviewView.onDidDispose(() => {
      this.view = undefined;
    });
  }

  async sendAction(action: Action, code?: string, filePath?: string): Promise<void> {
    const payload: RequestPayload = {
      action,
      code,
      filePath,
      language: filePath ? this.getLanguageFromPath(filePath) : undefined,
    };

    this.postMessage({ type: 'request', data: { action, loading: true } });

    try {
      const response = await this.client.send(payload, {
        onStream: (chunk: StreamPayload) => {
          this.outputBuffer += chunk.chunk;
          this.postMessage({
            type: 'response',
            data: { stream: chunk.chunk, partial: this.outputBuffer },
          });
        },
      });

      this.outputBuffer = '';
      this.postMessage({
        type: 'response',
        data: { result: response, action, loading: false },
      });
    } catch (error) {
      this.outputBuffer = '';
      const errorMsg = error instanceof Error ? error.message : String(error);
      this.postMessage({
        type: 'error',
        data: { message: errorMsg, action, loading: false },
      });
    }
  }

  async verify(code: string, filePath?: string): Promise<ResponsePayload | undefined> {
    const payload: RequestPayload = {
      action: 'verify',
      code,
      filePath,
      language: filePath ? this.getLanguageFromPath(filePath) : undefined,
    };

    try {
      const response = await this.client.send(payload);
      this.postMessage({
        type: 'response',
        data: { result: response, action: 'verify' },
      });
      return response;
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      this.postMessage({
        type: 'error',
        data: { message: errorMsg, action: 'verify' },
      });
      return undefined;
    }
  }

  private async handleWebViewMessage(message: WebViewMessage): Promise<void> {
    switch (message.type) {
      case 'ready':
        this.syncConfig();
        this.syncTheme();
        break;
      case 'request': {
        const data = message.data as { action: Action; code?: string; filePath?: string };
        await this.sendAction(data.action, data.code, data.filePath);
        break;
      }
      case 'update_config':
        this.syncConfig();
        break;
      case 'update_theme':
        this.syncTheme();
        break;
    }
  }

  private setupClientListeners(): void {
    this.client.on('statusChange', (status: ConnectionStatus) => {
      this.postMessage({
        type: 'response',
        data: { status, connected: status === 'connected' },
      });
    });

    this.client.on('error', (error: Error) => {
      this.postMessage({
        type: 'error',
        data: { message: error.message },
      });
    });
  }

  private syncConfig(): void {
    const config = getConfig();
    this.postMessage({
      type: 'response',
      data: { config },
    });
  }

  private syncTheme(): void {
    const config = getConfig();
    const theme = resolveTheme(config.theme);
    this.postMessage({
      type: 'response',
      data: { theme },
    });
  }

  private postMessage(message: WebViewMessage): void {
    this.view?.webview.postMessage(message);
  }

  private getLanguageFromPath(filePath: string): string {
    const ext = filePath.split('.').pop()?.toLowerCase() ?? '';
    const langMap: Record<string, string> = {
      ts: 'typescript',
      tsx: 'typescriptreact',
      js: 'javascript',
      jsx: 'javascriptreact',
      py: 'python',
      rb: 'ruby',
      rs: 'rust',
      go: 'go',
      java: 'java',
      kt: 'kotlin',
      swift: 'swift',
      cpp: 'cpp',
      c: 'c',
      cs: 'csharp',
      php: 'php',
      html: 'html',
      css: 'css',
      scss: 'scss',
      json: 'json',
      yaml: 'yaml',
      yml: 'yaml',
      md: 'markdown',
      sh: 'shellscript',
      sql: 'sql',
      dart: 'dart',
      lua: 'lua',
      r: 'r',
      scala: 'scala',
      hs: 'haskell',
      el: 'elixir',
      clj: 'clojure',
    };
    return langMap[ext] ?? ext;
  }

  private getHtmlForWebview(webview: vscode.Webview): string {
    const config = getConfig();
    const theme = resolveTheme(config.theme);

    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'webview', 'styles.css')
    );
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'webview', 'app.js')
    );

    const nonce = this.getNonce();

    return `<!DOCTYPE html>
<html lang="en" data-theme="${theme}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none';
    style-src ${webview.cspSource} 'unsafe-inline';
    script-src 'nonce-${nonce}';
    font-src ${webview.cspSource};">
  <link href="${styleUri}" rel="stylesheet">
  <title>Anvil AI</title>
</head>
<body class="anvil-${theme}">
  <div id="app">
    <header class="anvil-header">
      <div class="anvil-logo">
        <span class="anvil-logo-icon">&#9874;</span>
        <span class="anvil-logo-text">Anvil AI</span>
      </div>
      <div class="anvil-status" id="status-indicator">
        <span class="status-dot"></span>
        <span class="status-text">Disconnected</span>
      </div>
    </header>

    <div class="anvil-toolbar">
      <button class="toolbar-btn" data-action="ask" title="Ask (Ctrl+Shift+I)">
        <span class="btn-icon">&#128172;</span> Ask
      </button>
      <button class="toolbar-btn" data-action="explain" title="Explain">
        <span class="btn-icon">&#128218;</span> Explain
      </button>
      <button class="toolbar-btn" data-action="refactor" title="Refactor">
        <span class="btn-icon">&#9998;</span> Refactor
      </button>
      <button class="toolbar-btn" data-action="fix" title="Fix">
        <span class="btn-icon">&#128295;</span> Fix
      </button>
      <button class="toolbar-btn" data-action="generate_tests" title="Generate Tests">
        <span class="btn-icon">&#128221;</span> Tests
      </button>
      <button class="toolbar-btn toolbar-btn-verify" data-action="verify" title="Verify (Ctrl+Shift+V)">
        <span class="btn-icon">&#9989;</span> Verify
      </button>
    </div>

    <div class="anvil-chat" id="chat-container">
      <div class="chat-empty" id="chat-empty">
        <div class="empty-icon">&#9874;</div>
        <p>Select code and use an action to get started</p>
        <p class="empty-hint">Or ask a question about your codebase</p>
      </div>
    </div>

    <div class="anvil-input-area">
      <div class="input-wrapper">
        <textarea
          id="input-area"
          class="anvil-input"
          placeholder="Ask Anvil anything..."
          rows="2"
        ></textarea>
        <div class="input-actions">
          <button class="send-btn" id="send-btn" title="Send (Enter)">
            &#10148;
          </button>
        </div>
      </div>
    </div>

    <footer class="anvil-footer">
      <span class="footer-model" id="footer-model">Model: local</span>
      <span class="footer-tokens" id="footer-tokens">Tokens: 0</span>
    </footer>
  </div>

  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }

  private getNonce(): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let nonce = '';
    for (let i = 0; i < 32; i++) {
      nonce += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return nonce;
  }
}
