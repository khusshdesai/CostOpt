"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CostStatusBarItem = void 0;
const vscode = require("vscode");
class CostStatusBarItem {
    apiClient;
    statusBarItem;
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
        this.statusBarItem.command = 'costopt.showCostSummary';
    }
    async update() {
        const isEnabled = vscode.workspace.getConfiguration('costopt').get('enabled', true);
        if (!isEnabled) {
            this.statusBarItem.hide();
            return;
        }
        const isConnected = await this.apiClient.checkHealth();
        if (!isConnected) {
            this.statusBarItem.text = `$(plug) CostOpt: Disconnected`;
            this.statusBarItem.tooltip = `CostOpt local API service is unavailable at ${vscode.workspace.getConfiguration('costopt').get('endpoint')}`;
            this.statusBarItem.show();
            return;
        }
        const forecast = await this.apiClient.getForecast();
        if (!forecast || !forecast.has_enough_data) {
            this.statusBarItem.text = `$(symbol-numeric) CostOpt: Connected`;
            this.statusBarItem.tooltip = `CostOpt is connected and listening for local LLM telemetry.`;
            this.statusBarItem.show();
            return;
        }
        const todayStr = `$${forecast.spend_today.toFixed(2)}`;
        const budgetStr = `$${forecast.budget.toFixed(0)}`;
        if (forecast.over_budget) {
            this.statusBarItem.text = `$(warning) CostOpt: ${todayStr} / ${budgetStr}`;
            this.statusBarItem.tooltip = `⚠️ Projected spend ($${forecast.projected_monthly}/mo) exceeds budget (${budgetStr}). Click for details.`;
        }
        else {
            this.statusBarItem.text = `$(symbol-numeric) CostOpt: ${todayStr} today`;
            this.statusBarItem.tooltip = `Spend today: ${todayStr} | Projected monthly: $${forecast.projected_monthly} / ${budgetStr} budget. Click for details.`;
        }
        this.statusBarItem.show();
    }
    dispose() {
        this.statusBarItem.dispose();
    }
}
exports.CostStatusBarItem = CostStatusBarItem;
//# sourceMappingURL=statusBarItem.js.map