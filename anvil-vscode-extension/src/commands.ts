import * as vscode from 'vscode';
import { AnvilClient } from './AnvilClient';
import { AnvilProvider } from './AnvilProvider';
import { getConfig } from './config';
import { Action, CommandContext } from './types';

export function registerCommands(
  context: vscode.ExtensionContext,
  client: AnvilClient,
  provider: AnvilProvider
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand('anvil.start', () => startServer(context)),
    vscode.commands.registerCommand('anvil.open', () => openPanel()),
    vscode.commands.registerCommand('anvil.ask', () => executeAction('ask', client, provider)),
    vscode.commands.registerCommand('anvil.explain', () => executeAction('explain', client, provider)),
    vscode.commands.registerCommand('anvil.refactor', () => executeAction('refactor', client, provider)),
    vscode.commands.registerCommand('anvil.fix', () => executeAction('fix', client, provider)),
    vscode.commands.registerCommand('anvil.generateTests', () => executeAction('generate_tests', client, provider)),
    vscode.commands.registerCommand('anvil.verify', () => executeAction('verify', client, provider)),
  );
}

async function startServer(context: vscode.ExtensionContext): Promise<void> {
  const config = getConfig();

  const terminal = vscode.window.terminals.find((t) => t.name === 'Anvil Server');
  if (terminal) {
    terminal.show();
    vscode.window.showInformationMessage('Anvil server is already running');
    return;
  }

  const serverTerminal = vscode.window.createTerminal({
    name: 'Anvil Server',
    cwd: context.extensionPath,
  });

  serverTerminal.sendText(`anvil serve --port ${new URL(config.serverUrl).port || '8000'}`);
  serverTerminal.show(false);

  vscode.window.showInformationMessage('Anvil server starting...');
}

async function openPanel(): Promise<void> {
  await vscode.commands.executeCommand('workbench.view.extension.anvil');
}

async function executeAction(
  action: Action,
  client: AnvilClient,
  provider: AnvilProvider
): Promise<void> {
  if (client.connectionStatus !== 'connected') {
    const choice = await vscode.window.showWarningMessage(
      'Anvil is not connected. Start the server first?',
      'Start Server',
      'Cancel'
    );
    if (choice === 'Start Server') {
      await vscode.commands.executeCommand('anvil.start');
    }
    return;
  }

  const ctx = getCommandContext();
  if (!ctx) {
    if (action === 'ask') {
      await openPanel();
      return;
    }

    vscode.window.showWarningMessage('Please select some code first');
    return;
  }

  await provider.sendAction(action, ctx.code, ctx.filePath);
  await openPanel();

  if (action === 'verify' && getConfig().autoVerify) {
    const result = await provider.verify(ctx.code, ctx.filePath);
    if (result?.verification) {
      const { passed, score } = result.verification;
      if (passed) {
        vscode.window.showInformationMessage(`Verification passed (score: ${score}/100)`);
      } else {
        vscode.window.showWarningMessage(`Verification failed (score: ${score}/100)`);
      }
    }
  }
}

function getCommandContext(): CommandContext | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    return undefined;
  }

  const selection = editor.selection;
  const code = selection.isEmpty
    ? editor.document.getText()
    : editor.document.getText(selection);

  if (!code.trim()) {
    return undefined;
  }

  const diagnostics = vscode.languages.getDiagnostics(editor.document.uri).map((d) => ({
    message: d.message,
    severity: mapSeverity(d.severity),
    line: d.range.start.line,
    column: d.range.start.character,
    endLine: d.range.end.line,
    endColumn: d.range.end.character,
    source: d.source,
  }));

  return {
    code,
    language: editor.document.languageId,
    filePath: editor.document.uri.fsPath,
    selection: {
      startLine: selection.start.line,
      startColumn: selection.start.character,
      endLine: selection.end.line,
      endColumn: selection.end.character,
    },
    diagnostics,
  };
}

function mapSeverity(severity: vscode.DiagnosticSeverity): 'error' | 'warning' | 'info' | 'hint' {
  switch (severity) {
    case vscode.DiagnosticSeverity.Error:
      return 'error';
    case vscode.DiagnosticSeverity.Warning:
      return 'warning';
    case vscode.DiagnosticSeverity.Information:
      return 'info';
    case vscode.DiagnosticSeverity.Hint:
      return 'hint';
    default:
      return 'info';
  }
}
