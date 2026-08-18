"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.registerCostOptCommands = registerCostOptCommands;
const vscode = require("vscode");
function registerCostOptCommands(context, apiClient, treeProvider, statusBar, codeLensProvider) {
    // 1. Show Cost Summary
    context.subscriptions.push(vscode.commands.registerCommand('costopt.showCostSummary', async () => {
        const forecast = await apiClient.getForecast();
        if (!forecast || !forecast.has_enough_data) {
            vscode.window.showInformationMessage('CostOpt: Connected, but no LLM telemetry has been recorded yet.');
            return;
        }
        vscode.window.showInformationMessage(`CostOpt Summary — Today: $${forecast.spend_today.toFixed(2)} | Projected Monthly: $${forecast.projected_monthly.toFixed(2)} / $${forecast.budget.toFixed(2)} budget (${forecast.budget_remaining.toFixed(2)} remaining)`);
    }));
    // 2. Show Current File Cost
    context.subscriptions.push(vscode.commands.registerCommand('costopt.showCurrentFileCost', async (filePathArg) => {
        const editor = vscode.window.activeTextEditor;
        const filePath = filePathArg || editor?.document.fileName;
        if (!filePath) {
            vscode.window.showWarningMessage('CostOpt: No active file to inspect.');
            return;
        }
        const fileStats = await apiClient.getFileStats(filePath);
        if (!fileStats || fileStats.total_file_calls === 0) {
            vscode.window.showInformationMessage(`CostOpt: No telemetry recorded for ${filePath}`);
            return;
        }
        vscode.window.showInformationMessage(`CostOpt File Intelligence: ${fileStats.total_file_calls} calls recorded (${fileStats.line_stats.length} lines) | Total spend: $${fileStats.total_file_spend.toFixed(4)}`);
    }));
    // 3. Show Feature Costs
    context.subscriptions.push(vscode.commands.registerCommand('costopt.showFeatureCosts', async () => {
        const featRes = await apiClient.getFeatures();
        if (!featRes || !featRes.features || featRes.features.length === 0) {
            vscode.window.showInformationMessage('CostOpt: No feature-tagged calls recorded yet.');
            return;
        }
        const items = featRes.features.map(f => `${f.feature}: $${f.total_cost.toFixed(4)} (${f.call_count} calls, avg $${f.avg_cost_per_call.toFixed(4)}/call)`);
        vscode.window.showQuickPick(items, { placeHolder: 'CostOpt Feature Cost Attribution' });
    }));
    // 4. Show Cost Forecast
    context.subscriptions.push(vscode.commands.registerCommand('costopt.showCostForecast', async () => {
        const forecast = await apiClient.getForecast();
        if (!forecast || !forecast.has_enough_data) {
            vscode.window.showInformationMessage('CostOpt: Not enough usage data for a reliable monthly forecast.');
            return;
        }
        vscode.window.showInformationMessage(`CostOpt Monthly Forecast: $${forecast.projected_monthly.toFixed(2)} projected | Daily avg: $${forecast.daily_average.toFixed(2)} | Budget remaining: $${forecast.budget_remaining.toFixed(2)}`);
    }));
    // 5. Refresh Telemetry
    context.subscriptions.push(vscode.commands.registerCommand('costopt.refreshTelemetry', async () => {
        treeProvider.refresh();
        await statusBar.update();
        codeLensProvider.refresh();
        vscode.window.showInformationMessage('CostOpt: Telemetry refreshed.');
    }));
    // 6. Open Local Dashboard
    context.subscriptions.push(vscode.commands.registerCommand('costopt.openLocalDashboard', async () => {
        const endpoint = vscode.workspace.getConfiguration('costopt').get('endpoint', 'http://127.0.0.1:8000');
        vscode.env.openExternal(vscode.Uri.parse(endpoint));
    }));
}
//# sourceMappingURL=registerCommands.js.map