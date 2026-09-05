import * as vscode from 'vscode';
import { CostOptApiClient } from './api/client';
import { CostCodeLensProvider } from './codelens/costCodeLensProvider';
import { CostHoverProvider } from './hover/costHoverProvider';
import { CostStatusBarItem } from './statusbar/statusBarItem';
import { CostTreeDataProvider } from './views/costTreeDataProvider';
import { CostDiagnosticsManager } from './diagnostics/costDiagnostics';
import { registerCostOptCommands } from './commands/registerCommands';

let pollTimer: NodeJS.Timeout | undefined;

export function activate(context: vscode.ExtensionContext) {
  console.log('CostOpt VS Code Extension activated.');

  const apiClient = new CostOptApiClient();

  // 1. Providers
  const codeLensProvider = new CostCodeLensProvider(apiClient);
  const hoverProvider = new CostHoverProvider(apiClient);
  const treeDataProvider = new CostTreeDataProvider(apiClient);
  const statusBarItem = new CostStatusBarItem(apiClient);
  const diagnosticsManager = new CostDiagnosticsManager(apiClient);

  // Register CodeLens & Hover Providers for Python, JavaScript, TypeScript
  const selectors: vscode.DocumentSelector[] = [
    { scheme: 'file', language: 'python' },
    { scheme: 'file', language: 'javascript' },
    { scheme: 'file', language: 'typescript' }
  ];

  for (const selector of selectors) {
    context.subscriptions.push(vscode.languages.registerCodeLensProvider(selector, codeLensProvider));
    context.subscriptions.push(vscode.languages.registerHoverProvider(selector, hoverProvider));
  }

  // 2. Tree View Sidebar
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('costopt-sidebar', treeDataProvider)
  );

  // 3. Register Commands
  registerCostOptCommands(context, apiClient, treeDataProvider, statusBarItem, codeLensProvider);

  // 4. Initial Status Bar Update & Diagnostics Sync
  statusBarItem.update();
  diagnosticsManager.updateDiagnostics();

  // 5. Dynamic polling with exponential backoff when disconnected
  let currentDelay = 15000;
  const MIN_DELAY = 15000;
  const MAX_DELAY = 300000;

  async function pollLoop() {
    const isConnected = await apiClient.checkHealth();
    await statusBarItem.update();
    diagnosticsManager.updateDiagnostics();
    treeDataProvider.refresh();
    codeLensProvider.refresh();

    if (isConnected) {
      currentDelay = MIN_DELAY;
    } else {
      currentDelay = Math.min(currentDelay * 2, MAX_DELAY);
    }

    pollTimer = setTimeout(pollLoop, currentDelay);
  }

  pollLoop();

  // Active Editor change hook
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(() => {
      diagnosticsManager.updateDiagnostics();
      codeLensProvider.refresh();
    })
  );

  context.subscriptions.push(statusBarItem);
  context.subscriptions.push(diagnosticsManager);
}

export function deactivate() {
  if (pollTimer) {
    clearTimeout(pollTimer);
  }
}
