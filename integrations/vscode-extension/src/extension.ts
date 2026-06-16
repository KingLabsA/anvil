import * as vscode from 'vscode';
import axios from 'axios';

let statusBarItem: vscode.StatusBarItem;
let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
    console.log('Anvil extension is now active');

    // Create output channel
    outputChannel = vscode.window.createOutputChannel('Anvil');
    outputChannel.appendLine('Anvil extension activated');

    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.text = '$(tools) Anvil';
    statusBarItem.tooltip = 'Anvil - Self-Verified Coding Agent';
    statusBarItem.command = 'anvil.showHistory';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Register commands
    const commands = [
        vscode.commands.registerCommand('anvil.runTask', runTask),
        vscode.commands.registerCommand('anvil.verifyCode', verifyCode),
        vscode.commands.registerCommand('anvil.explainCode', explainCode),
        vscode.commands.registerCommand('anvil.refactorCode', refactorCode),
        vscode.commands.registerCommand('anvil.fixErrors', fixErrors),
        vscode.commands.registerCommand('anvil.generateTests', generateTests),
        vscode.commands.registerCommand('anvil.showHistory', showHistory),
        vscode.commands.registerCommand('anvil.configureSettings', configureSettings),
    ];

    commands.forEach(cmd => context.subscriptions.push(cmd));

    // Create sidebar views
    const taskProvider = new TaskProvider();
    vscode.window.registerTreeDataProvider('anvil-tasks', taskProvider);

    const historyProvider = new HistoryProvider();
    vscode.window.registerTreeDataProvider('anvil-history', historyProvider);

    outputChannel.appendLine('All commands registered');
}

export function deactivate() {
    if (statusBarItem) {
        statusBarItem.dispose();
    }
    if (outputChannel) {
        outputChannel.dispose();
    }
}

// Helper functions
function getConfig() {
    const config = vscode.workspace.getConfiguration('anvil');
    return {
        serverUrl: config.get<string>('serverUrl', 'http://localhost:8000'),
        model: config.get<string>('model', 'local'),
        autoVerify: config.get<boolean>('autoVerify', true),
        maxIterations: config.get<number>('maxIterations', 20),
    };
}

async function callAnvilAPI(endpoint: string, data: any): Promise<any> {
    const config = getConfig();
    const url = `${config.serverUrl}${endpoint}`;
    
    outputChannel.appendLine(`Calling API: ${url}`);
    outputChannel.appendLine(`Data: ${JSON.stringify(data, null, 2)}`);

    try {
        const response = await axios.post(url, data, {
            timeout: 30000,
        });
        outputChannel.appendLine(`Response: ${JSON.stringify(response.data, null, 2)}`);
        return response.data;
    } catch (error: any) {
        outputChannel.appendLine(`Error: ${error.message}`);
        throw error;
    }
}

// Command implementations
async function runTask() {
    const task = await vscode.window.showInputBox({
        prompt: 'Enter task for Anvil',
        placeHolder: 'e.g., Fix the authentication bug in auth.py',
    });

    if (!task) {
        return;
    }

    outputChannel.show();
    outputChannel.appendLine(`\n=== Running Task: ${task} ===\n`);

    statusBarItem.text = '$(loading~spin) Anvil: Running...';

    try {
        const result = await callAnvilAPI('/run', {
            task,
            model: getConfig().model,
            max_iterations: getConfig().maxIterations,
        });

        if (result.success) {
            vscode.window.showInformationMessage(`✓ Task completed: ${task}`);
            outputChannel.appendLine(`\n✓ Task completed successfully`);
            outputChannel.appendLine(`Output: ${result.output}`);
        } else {
            vscode.window.showErrorMessage(`✗ Task failed: ${result.error}`);
            outputChannel.appendLine(`\n✗ Task failed: ${result.error}`);
        }
    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to connect to Anvil server: ${error.message}`);
        outputChannel.appendLine(`\n✗ Connection error: ${error.message}`);
    } finally {
        statusBarItem.text = '$(tools) Anvil';
    }
}

async function verifyCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const document = editor.document;
    const code = document.getText();
    const filePath = document.fileName;

    outputChannel.show();
    outputChannel.appendLine(`\n=== Verifying: ${filePath} ===\n`);

    statusBarItem.text = '$(loading~spin) Anvil: Verifying...';

    try {
        const result = await callAnvilAPI('/verify', {
            code,
            file_path: filePath,
            language: document.languageId,
        });

        if (result.passed) {
            vscode.window.showInformationMessage('✓ Code verification passed');
            outputChannel.appendLine(`\n✓ Verification passed`);
        } else {
            vscode.window.showWarningMessage(`✗ Verification failed: ${result.failures.join(', ')}`);
            outputChannel.appendLine(`\n✗ Verification failed: ${result.failures.join(', ')}`);
        }
    } catch (error: any) {
        vscode.window.showErrorMessage(`Verification failed: ${error.message}`);
        outputChannel.appendLine(`\n✗ Error: ${error.message}`);
    } finally {
        statusBarItem.text = '$(tools) Anvil';
    }
}

async function explainCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const selection = editor.selection;
    const code = selection.isEmpty ? editor.document.getText() : editor.document.getText(selection);

    outputChannel.show();
    outputChannel.appendLine(`\n=== Explaining Code ===\n`);

    statusBarItem.text = '$(loading~spin) Anvil: Explaining...';

    try {
        const result = await callAnvilAPI('/explain', { code });
        
        const panel = vscode.window.createWebviewPanel(
            'anvilExplanation',
            'Anvil: Code Explanation',
            vscode.ViewColumn.Beside,
            {}
        );

        panel.webview.html = `
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: var(--vscode-font-family); padding: 20px; }
                    pre { background: var(--vscode-editor-background); padding: 10px; border-radius: 4px; }
                </style>
            </head>
            <body>
                <h2>Code Explanation</h2>
                <pre>${result.explanation}</pre>
            </body>
            </html>
        `;

        outputChannel.appendLine(`\n✓ Explanation generated`);
    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to explain code: ${error.message}`);
        outputChannel.appendLine(`\n✗ Error: ${error.message}`);
    } finally {
        statusBarItem.text = '$(tools) Anvil';
    }
}

async function refactorCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const suggestion = await vscode.window.showInputBox({
        prompt: 'What would you like to refactor?',
        placeHolder: 'e.g., Extract this into a separate function',
    });

    if (!suggestion) {
        return;
    }

    const code = editor.document.getText();

    outputChannel.show();
    outputChannel.appendLine(`\n=== Refactoring: ${suggestion} ===\n`);

    statusBarItem.text = '$(loading~spin) Anvil: Refactoring...';

    try {
        const result = await callAnvilAPI('/refactor', {
            code,
            suggestion,
        });

        if (result.refactored_code) {
            const edit = new vscode.WorkspaceEdit();
            const fullRange = new vscode.Range(
                editor.document.positionAt(0),
                editor.document.positionAt(code.length)
            );
            edit.replace(editor.document.uri, fullRange, result.refactored_code);
            await vscode.workspace.applyEdit(edit);

            vscode.window.showInformationMessage('✓ Code refactored');
            outputChannel.appendLine(`\n✓ Refactoring applied`);
        }
    } catch (error: any) {
        vscode.window.showErrorMessage(`Refactoring failed: ${error.message}`);
        outputChannel.appendLine(`\n✗ Error: ${error.message}`);
    } finally {
        statusBarItem.text = '$(tools) Anvil';
    }
}

async function fixErrors() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const diagnostics = vscode.languages.getDiagnostics(editor.document.uri);
    const errors = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Error);

    if (errors.length === 0) {
        vscode.window.showInformationMessage('No errors to fix');
        return;
    }

    const code = editor.document.getText();

    outputChannel.show();
    outputChannel.appendLine(`\n=== Fixing ${errors.length} Error(s) ===\n`);

    statusBarItem.text = '$(loading~spin) Anvil: Fixing...';

    try {
        const result = await callAnvilAPI('/fix', {
            code,
            errors: errors.map(e => ({
                message: e.message,
                line: e.range.start.line,
                column: e.range.start.character,
            })),
        });

        if (result.fixed_code) {
            const edit = new vscode.WorkspaceEdit();
            const fullRange = new vscode.Range(
                editor.document.positionAt(0),
                editor.document.positionAt(code.length)
            );
            edit.replace(editor.document.uri, fullRange, result.fixed_code);
            await vscode.workspace.applyEdit(edit);

            vscode.window.showInformationMessage(`✓ Fixed ${errors.length} error(s)`);
            outputChannel.appendLine(`\n✓ Fixed ${errors.length} error(s)`);
        }
    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to fix errors: ${error.message}`);
        outputChannel.appendLine(`\n✗ Error: ${error.message}`);
    } finally {
        statusBarItem.text = '$(tools) Anvil';
    }
}

async function generateTests() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const code = editor.document.getText();
    const filePath = editor.document.fileName;

    outputChannel.show();
    outputChannel.appendLine(`\n=== Generating Tests for ${filePath} ===\n`);

    statusBarItem.text = '$(loading~spin) Anvil: Generating...';

    try {
        const result = await callAnvilAPI('/generate-tests', {
            code,
            file_path: filePath,
            language: editor.document.languageId,
        });

        if (result.tests) {
            const testFilePath = filePath.replace(/\.[^.]+$/, '_test.py');
            const testUri = vscode.Uri.file(testFilePath);
            
            await vscode.workspace.fs.writeFile(testUri, Buffer.from(result.tests, 'utf8'));
            
            const doc = await vscode.workspace.openTextDocument(testUri);
            await vscode.window.showTextDocument(doc, vscode.ViewColumn.Beside);

            vscode.window.showInformationMessage('✓ Tests generated');
            outputChannel.appendLine(`\n✓ Tests generated: ${testFilePath}`);
        }
    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to generate tests: ${error.message}`);
        outputChannel.appendLine(`\n✗ Error: ${error.message}`);
    } finally {
        statusBarItem.text = '$(tools) Anvil';
    }
}

async function showHistory() {
    outputChannel.show();
    outputChannel.appendLine(`\n=== Task History ===\n`);

    try {
        const result = await callAnvilAPI('/sessions', {});
        
        const items = result.sessions.map((s: any) => ({
            label: s.task,
            description: new Date(s.created_at).toLocaleString(),
            detail: s.success ? '✓ Success' : '✗ Failed',
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: 'Select a task to view',
        });

        if (selected) {
            outputChannel.appendLine(`Selected: ${selected.label}`);
        }
    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to load history: ${error.message}`);
        outputChannel.appendLine(`\n✗ Error: ${error.message}`);
    }
}

async function configureSettings() {
    await vscode.commands.executeCommand('workbench.action.openSettings', 'anvil');
}

// Tree data providers
class TaskProvider implements vscode.TreeDataProvider<TaskItem> {
    getTreeItem(element: TaskItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: TaskItem): Thenable<TaskItem[]> {
        if (!element) {
            return Promise.resolve([
                new TaskItem('Run Task', 'anvil.runTask', 'play'),
                new TaskItem('Verify Code', 'anvil.verifyCode', 'check'),
                new TaskItem('Explain Code', 'anvil.explainCode', 'info'),
                new TaskItem('Refactor Code', 'anvil.refactorCode', 'edit'),
                new TaskItem('Fix Errors', 'anvil.fixErrors', 'bug'),
                new TaskItem('Generate Tests', 'anvil.generateTests', 'beaker'),
            ]);
        }
        return Promise.resolve([]);
    }
}

class TaskItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly commandId: string,
        public readonly icon: string
    ) {
        super(label, vscode.TreeItemCollapsibleState.None);
        this.command = {
            command: commandId,
            title: label,
        };
        this.iconPath = new vscode.ThemeIcon(icon);
    }
}

class HistoryProvider implements vscode.TreeDataProvider<HistoryItem> {
    getTreeItem(element: HistoryItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: HistoryItem): Promise<HistoryItem[]> {
        if (!element) {
            try {
                const result = await callAnvilAPI('/sessions', {});
                return result.sessions.map((s: any) => 
                    new HistoryItem(s.task, s.success, new Date(s.created_at))
                );
            } catch {
                return [new HistoryItem('Failed to load history', false, new Date())];
            }
        }
        return [];
    }
}

class HistoryItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly success: boolean,
        public readonly date: Date
    ) {
        super(label, vscode.TreeItemCollapsibleState.None);
        this.description = date.toLocaleString();
        this.iconPath = new vscode.ThemeIcon(success ? 'check' : 'x');
    }
}
