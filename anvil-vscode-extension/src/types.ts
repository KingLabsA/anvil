export interface AnvilConfig {
  serverUrl: string;
  model: ModelProvider;
  autoVerify: boolean;
  theme: ThemeMode;
  maxTokens: number;
  temperature: number;
  autoStart: boolean;
}

export type ModelProvider = 'local' | 'openai' | 'anthropic' | 'gemini' | 'deepseek';

export type ThemeMode = 'auto' | 'light' | 'dark';

export interface AnvilMessage {
  type: MessageType;
  id: string;
  payload: unknown;
  timestamp: number;
}

export type MessageType =
  | 'request'
  | 'response'
  | 'error'
  | 'stream'
  | 'stream_end'
  | 'status'
  | 'verification'
  | 'cancel';

export interface RequestPayload {
  action: Action;
  code?: string;
  context?: string;
  language?: string;
  filePath?: string;
  selection?: SelectionRange;
  options?: RequestOptions;
}

export type Action =
  | 'ask'
  | 'explain'
  | 'refactor'
  | 'fix'
  | 'generate_tests'
  | 'verify'
  | 'complete';

export interface SelectionRange {
  startLine: number;
  startColumn: number;
  endLine: number;
  endColumn: number;
}

export interface RequestOptions {
  model?: ModelProvider;
  maxTokens?: number;
  temperature?: number;
  autoVerify?: boolean;
}

export interface ResponsePayload {
  result?: string;
  suggestions?: Suggestion[];
  verification?: VerificationResult;
  tokens?: TokenUsage;
  error?: string;
}

export interface Suggestion {
  code: string;
  description: string;
  confidence: number;
  range?: SelectionRange;
}

export interface VerificationResult {
  passed: boolean;
  checks: VerificationCheck[];
  score: number;
  summary: string;
}

export interface VerificationCheck {
  name: string;
  passed: boolean;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

export interface TokenUsage {
  prompt: number;
  completion: number;
  total: number;
}

export interface StatusPayload {
  status: ConnectionStatus;
  model?: ModelProvider;
  version?: string;
  message?: string;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface StreamPayload {
  chunk: string;
  done: boolean;
  tokens?: TokenUsage;
}

export interface WebViewMessage {
  type: WebViewMessageType;
  data?: unknown;
}

export type WebViewMessageType =
  | 'ready'
  | 'request'
  | 'response'
  | 'update_theme'
  | 'update_config'
  | 'error';

export interface ServerInfo {
  url: string;
  version: string;
  models: ModelProvider[];
  status: ConnectionStatus;
}

export interface CommandContext {
  code: string;
  language: string;
  filePath: string;
  selection: SelectionRange;
  diagnostics: Diagnostic[];
}

export interface Diagnostic {
  message: string;
  severity: 'error' | 'warning' | 'info' | 'hint';
  line: number;
  column: number;
  endLine?: number;
  endColumn?: number;
  source?: string;
}

export interface ExtensionState {
  connected: boolean;
  currentModel: ModelProvider;
  tokenUsage: TokenUsage;
  lastAction?: Action;
  serverInfo?: ServerInfo;
}
