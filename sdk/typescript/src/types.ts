/**
 * TypeScript type definitions for Anvil SDK
 */

export interface AnvilConfig {
  /** Base URL for the Anvil server (default: http://localhost:8765) */
  baseUrl?: string;
  /** Request timeout in milliseconds (default: 30000) */
  timeout?: number;
  /** Model to use for task execution */
  model?: string;
  /** Maximum number of iterations */
  maxIterations?: number;
  /** Enable verification */
  verify?: boolean;
}

export interface RunRequest {
  /** Task description */
  task: string;
  /** Model to use (overrides config) */
  model?: string;
  /** Maximum iterations (overrides config) */
  max_iterations?: number;
  /** Enable verification (overrides config) */
  verify?: boolean;
}

export interface RunResponse {
  /** Whether the task succeeded */
  success: boolean;
  /** Output/result text */
  output: string;
  /** Error message if failed */
  error?: string;
  /** Number of execution steps */
  steps: number;
  /** Session ID for tracking */
  session_id: string;
}

export interface Session {
  /** Unique session ID */
  id: string;
  /** Original task description */
  task: string;
  /** Execution steps */
  steps: Step[];
  /** Session statistics */
  stats: SessionStats;
  /** Creation timestamp */
  created_at: string;
  /** Last update timestamp */
  updated_at: string;
}

export interface Step {
  /** Step ID */
  id: string;
  /** Step kind */
  kind: StepKind;
  /** Step description */
  content: string;
  /** Step status */
  status: StepStatus;
  /** Tool calls made in this step */
  tool_calls?: ToolCall[];
  /** Verification result */
  verify_result?: VerifyResult;
  /** Error message if failed */
  error?: string;
  /** Timestamp */
  timestamp: string;
}

export enum StepKind {
  PLAN = 'plan',
  EXECUTE = 'execute',
  VERIFY = 'verify',
  RECOVER = 'recover'
}

export enum StepStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUCCESS = 'success',
  FAILED = 'failed',
  RECOVERED = 'recovered'
}

export interface ToolCall {
  /** Tool name */
  tool: string;
  /** Tool arguments */
  args: Record<string, any>;
  /** Tool output */
  output?: string;
  /** Whether the call succeeded */
  success: boolean;
}

export interface VerifyResult {
  /** Whether verification passed */
  passed: boolean;
  /** Verification failures */
  failures: string[];
  /** Syntax check results */
  syntax?: CheckResult;
  /** Lint check results */
  lint?: CheckResult;
  /** Import check results */
  imports?: CheckResult;
  /** Type check results */
  types?: CheckResult;
  /** Test execution results */
  tests?: CheckResult;
}

export interface CheckResult {
  /** Check name */
  checker: string;
  /** Check status */
  status: 'pass' | 'fail' | 'skip' | 'error';
  /** Check message */
  message: string;
  /** Detailed output */
  details?: string;
  /** File path if applicable */
  file_path?: string;
}

export interface SessionStats {
  /** Total number of steps */
  total_steps: number;
  /** Number of successful steps */
  successful_steps: number;
  /** Number of failed steps */
  failed_steps: number;
  /** Number of recovered steps */
  recovered_steps: number;
  /** Success rate (0-1) */
  success_rate: number;
  /** Recovery rate (0-1) */
  recovery_rate: number;
}

export interface SessionInfo {
  /** Session ID */
  id: string;
  /** Task description */
  task: string;
  /** Whether the session succeeded */
  success: boolean;
  /** Creation timestamp */
  created_at: string;
}

export interface HealthResponse {
  /** Health status */
  status: 'ok' | 'error';
  /** Server version */
  version: string;
}

export interface StreamMessage {
  /** Message type */
  type: 'status' | 'step' | 'result' | 'error';
  /** Message content */
  message?: string;
  /** Step data (for 'step' type) */
  step?: Step;
  /** Result data (for 'result' type) */
  result?: RunResponse;
  /** Error message (for 'error' type) */
  error?: string;
}
