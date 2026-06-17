import * as vscode from 'vscode';
import { AnvilConfig, ModelProvider, ThemeMode } from './types';

const CONFIG_SECTION = 'anvil';

export function getConfig(): AnvilConfig {
  const config = vscode.workspace.getConfiguration(CONFIG_SECTION);
  return {
    serverUrl: config.get<string>('serverUrl', 'http://localhost:8000'),
    model: config.get<ModelProvider>('model', 'local'),
    autoVerify: config.get<boolean>('autoVerify', true),
    theme: config.get<ThemeMode>('theme', 'auto'),
    maxTokens: config.get<number>('maxTokens', 4096),
    temperature: config.get<number>('temperature', 0.7),
    autoStart: config.get<boolean>('autoStart', false),
  };
}

export async function updateConfig<K extends keyof AnvilConfig>(
  key: K,
  value: AnvilConfig[K],
  target: vscode.ConfigurationTarget = vscode.ConfigurationTarget.Global
): Promise<void> {
  const config = vscode.workspace.getConfiguration(CONFIG_SECTION);
  await config.update(key, value, target);
}

export function onConfigChange(callback: (config: AnvilConfig) => void): vscode.Disposable {
  return vscode.workspace.onDidChangeConfiguration((e) => {
    if (e.affectsConfiguration(CONFIG_SECTION)) {
      callback(getConfig());
    }
  });
}

export function resolveTheme(theme: ThemeMode): 'light' | 'dark' {
  if (theme !== 'auto') {
    return theme;
  }
  return vscode.window.activeColorTheme.kind === vscode.ColorThemeKind.Light
    ? 'light'
    : 'dark';
}

export function getWebSocketUrl(serverUrl: string): string {
  try {
    const url = new URL(serverUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url.toString().replace(/\/$/, '') + '/ws';
  } catch {
    return 'ws://localhost:8000/ws';
  }
}
