"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const client_1 = require("./api/client");
const costCodeLensProvider_1 = require("./codelens/costCodeLensProvider");
const costHoverProvider_1 = require("./hover/costHoverProvider");
const statusBarItem_1 = require("./statusbar/statusBarItem");
const costTreeDataProvider_1 = require("./views/costTreeDataProvider");
const costDiagnostics_1 = require("./diagnostics/costDiagnostics");
const registerCommands_1 = require("./commands/registerCommands");
let pollTimer;
function activate(context) {
    console.log('CostOpt VS Code Extension activated.');
    const apiClient = new client_1.CostOptApiClient();
    // 1. Providers
    const codeLensProvider = new costCodeLensProvider_1.CostCodeLensProvider(apiClient);
    const hoverProvider = new costHoverProvider_1.CostHoverProvider(apiClient);
    const treeDataProvider = new costTreeDataProvider_1.CostTreeDataProvider(apiClient);
    const statusBarItem = new statusBarItem_1.CostStatusBarItem(apiClient);
    const diagnosticsManager = new costDiagnostics_1.CostDiagnosticsManager(apiClient);
    // Register CodeLens & Hover Providers for Python, JavaScript, TypeScript
    const selectors = [
        { scheme: 'file', language: 'python' },
        { scheme: 'file', language: 'javascript' },
        { scheme: 'file', language: 'typescript' }
    ];
    for (const selector of selectors) {
        context.subscriptions.push(vscode.languages.registerCodeLensProvider(selector, codeLensProvider));
        context.subscriptions.push(vscode.languages.registerHoverProvider(selector, hoverProvider));
    }
    // 2. Tree View Sidebar
    context.subscriptions.push(vscode.window.registerTreeDataProvider('costopt-sidebar', treeDataProvider));
    // 3. Register Commands
    (0, registerCommands_1.registerCostOptCommands)(context, apiClient, treeDataProvider, statusBarItem, codeLensProvider);
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
        }
        else {
            currentDelay = Math.min(currentDelay * 2, MAX_DELAY);
        }
        pollTimer = setTimeout(pollLoop, currentDelay);
    }
    pollLoop();
    // Active Editor change hook
    context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(() => {
        diagnosticsManager.updateDiagnostics();
        codeLensProvider.refresh();
    }));
    context.subscriptions.push(statusBarItem);
    context.subscriptions.push(diagnosticsManager);
}
function deactivate() {
    if (pollTimer) {
        clearTimeout(pollTimer);
    }
}
//# sourceMappingURL=extension.js.map