/**
 * TypeScript types for Anvil Mobile
 */

export interface Task {
  id: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: string;
  error?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface Settings {
  serverUrl: string;
  model: string;
  maxIterations: number;
  theme: 'light' | 'dark';
}

export interface VoiceCommand {
  text: string;
  confidence: number;
  language: string;
}

export interface Screenshot {
  uri: string;
  width: number;
  height: number;
  timestamp: Date;
}
