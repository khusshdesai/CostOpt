"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CostTreeDataProvider = exports.CostTreeItem = void 0;
const vscode = require("vscode");
class CostTreeItem extends vscode.TreeItem {
    label;
    collapsibleState;
    subtext;
    iconName;
    contextValue;
    constructor(label, collapsibleState, subtext, iconName, contextValue) {
        super(label, collapsibleState);
        this.label = label;
        this.collapsibleState = collapsibleState;
        this.subtext = subtext;
        this.iconName = iconName;
        this.contextValue = contextValue;
        if (subtext) {
            this.description = subtext;
        }
        if (iconName) {
            this.iconPath = new vscode.ThemeIcon(iconName);
        }
        if (contextValue) {
            this.contextValue = contextValue;
        }
    }
}
exports.CostTreeItem = CostTreeItem;
class CostTreeDataProvider {
    apiClient;
    _onDidChangeTreeData = new vscode.EventEmitter();
    onDidChangeTreeData = this._onDidChangeTreeData.event;
    constructor(apiClient) {
        this.apiClient = apiClient;
    }
    refresh() {
        this._onDidChangeTreeData.fire();
    }
    getTreeItem(element) {
        return element;
    }
    async getChildren(element) {
        if (!element) {
            // Root Sections
            return [
                new CostTreeItem('Forecast & Budget', vscode.TreeItemCollapsibleState.Expanded, undefined, 'graph-line', 'section_forecast'),
                new CostTreeItem('Cost by Feature', vscode.TreeItemCollapsibleState.Expanded, undefined, 'symbol-structure', 'section_features'),
                new CostTreeItem('Cost Warnings & Drift', vscode.TreeItemCollapsibleState.Expanded, undefined, 'warning', 'section_warnings')
            ];
        }
        if (element.contextValue === 'section_forecast') {
            const forecast = await this.apiClient.getForecast();
            if (!forecast) {
                const startBtn = new CostTreeItem('▶ Click to Start CostOpt', vscode.TreeItemCollapsibleState.None, 'Launch CostOpt dashboard server on port 8400', 'play');
                startBtn.command = {
                    command: 'costopt.startServer',
                    title: 'Start CostOpt Server'
                };
                const statusItem = new CostTreeItem('🔌 Status: Offline', vscode.TreeItemCollapsibleState.None, 'Run: costopt dashboard --port 8400', 'plug');
                return [startBtn, statusItem];
            }
            const totalSpend = forecast.total_spend ?? 0.0;
            const spendToday = forecast.spend_today ?? 0.0;
            const dailyAvg = forecast.daily_average ?? 0.0;
            const projMonthly = forecast.projected_monthly ?? 0.0;
            const limit = forecast.budget ?? 50.0;
            const remaining = forecast.budget_remaining ?? limit;
            return [
                new CostTreeItem('Current Spend', vscode.TreeItemCollapsibleState.None, `$${totalSpend.toFixed(4)}`, 'dashboard'),
                new CostTreeItem('Spend Today', vscode.TreeItemCollapsibleState.None, `$${spendToday.toFixed(4)}`, 'history'),
                new CostTreeItem('Daily Average', vscode.TreeItemCollapsibleState.None, `$${dailyAvg.toFixed(4)}`, 'graph-line'),
                new CostTreeItem('Projected Monthly', vscode.TreeItemCollapsibleState.None, `$${projMonthly.toFixed(2)}`, projMonthly > limit ? 'error' : 'pulse'),
                new CostTreeItem('Budget Limit', vscode.TreeItemCollapsibleState.None, `$${limit.toFixed(2)}`, 'shield'),
                new CostTreeItem('Budget Remaining', vscode.TreeItemCollapsibleState.None, `$${remaining.toFixed(2)}`, 'pass-filled')
            ];
        }
        if (element.contextValue === 'section_features') {
            const featRes = await this.apiClient.getFeatures();
            if (!featRes || !featRes.features || featRes.features.length === 0) {
                return [
                    new CostTreeItem('No features tracked yet', vscode.TreeItemCollapsibleState.None, 'Pass feature="name" in client.create()', 'info')
                ];
            }
            const totalSpend = featRes.features.reduce((acc, f) => acc + f.total_cost, 0);
            return featRes.features.map(f => {
                const pct = totalSpend > 0 ? ((f.total_cost / totalSpend) * 100).toFixed(1) : '0';
                return new CostTreeItem(f.feature, vscode.TreeItemCollapsibleState.None, `$${f.total_cost.toFixed(4)} (${pct}% | ${f.call_count} calls)`, 'ruby');
            });
        }
        if (element.contextValue === 'section_warnings') {
            const warnings = await this.apiClient.getWarnings();
            if (!warnings || warnings.length === 0) {
                return [
                    new CostTreeItem('Spend Nominal', vscode.TreeItemCollapsibleState.None, 'No budget overruns or runaway loops', 'shield-check')
                ];
            }
            return warnings.map(w => new CostTreeItem(w.title, vscode.TreeItemCollapsibleState.None, w.message, w.severity === 'WARNING' ? 'warning' : 'info'));
        }
        return [];
    }
}
exports.CostTreeDataProvider = CostTreeDataProvider;
//# sourceMappingURL=costTreeDataProvider.js.map