import * as vscode from 'vscode';
import { AnvilClient } from './AnvilClient';
import { AnvilProvider } from './AnvilProvider';
import { registerCommands } from './commands';
import { getConfig, onConfigChange } from './config';

let client: AnvilClient | undefined;
let statusBarItem: vscode.StatusBarItem | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const config = getConfig();

  client = new AnvilClient(config.serverUrl);

  setupStatusBar(context);

  const provider = new AnvilProvider(context.extensionUri, client);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(AnvilProvider.viewType, provider, {
      webviewOptions: { retainContextWhenHidden: true },
    })
  );

  registerCommands(context, client, provider);

  setupClientEvents(client);

  context.subscriptions.push(
    onConfigChange((newConfig) => {
      client?.updateServerUrl(newConfig.serverUrl);
      updateStatusBar();
    })
  );

  if (config.autoStart) {
    try {
      await client.connect();
    } catch {
      // Error handled via client events
    }
  }
}

export function deactivate(): void {
  client?.disconnect();
  client = undefined;
  statusBarItem?.dispose();
  statusBarItem = undefined;
}

function setupStatusBar(context: vscode.ExtensionContext): void {
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.command = 'anvil.open';
  context.subscriptions.push(statusBarItem);

  updateStatusBar();
  statusBarItem.show();
}

function setupClientEvents(c: AnvilClient): void {
  c.on('statusChange', () => {
    updateStatusBar();
  });

  c.on('error', (error: Error) => {
    vscode.window.showErrorMessage(`Anvil: ${error.message}`);
  });

  c.on('disconnected', () => {
    updateStatusBar();
  });

  c.on('reconnecting', (info: { attempt: number }) => {
    if (statusBarItem) {
      statusBarItem.text = `$(sync~spin) Anvil (reconnecting #${info.attempt})`;
      statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
    }
  });

  c.on('reconnect_failed', () => {
    vscode.window.showErrorMessage(
      'Anvil: Failed to reconnect after multiple attempts. Check server settings.'
    );
  });
}

function updateStatusBar(): void {
  if (!statusBarItem || !client) {
    return;
  }

  const config = getConfig();
  const status = client.connectionStatus;

  switch (status) {
    case 'connected':
      statusBarItem.text = `$(zap) Anvil (${config.model})`;
      statusBarItem.backgroundColor = undefined;
      statusBarItem.tooltip = 'Anvil AI - Connected';
      break;
    case 'connecting':
      statusBarItem.text = '$(sync~spin) Anvil (connecting)';
      statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
      statusBarItem.tooltip = 'Anvil AI - Connecting...';
      break;
    case 'disconnected':
      statusBarItem.text = '$(circle-slash) Anvil (offline)';
      statusBarItem.backgroundColor = undefined;
      statusBarItem.tooltip = 'Anvil AI - Disconnected. Click to open.';
      break;
    case 'error':
      statusBarItem.text = '$(error) Anvil (error)';
      statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
      statusBarItem.tooltip = 'Anvil AI - Connection error';
      break;
  }
}
