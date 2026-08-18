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
            if (!forecast || !forecast.has_enough_data) {
                return [
                    new CostTreeItem('Status', vscode.TreeItemCollapsibleState.None, 'Not enough usage data for forecast', 'info')
                ];
            }
            return [
                new CostTreeItem('Current Spend', vscode.TreeItemCollapsibleState.None, `$${forecast.total_spend.toFixed(4)}`, 'account'),
                new CostTreeItem('Spend Today', vscode.TreeItemCollapsibleState.None, `$${forecast.spend_today.toFixed(4)}`, 'history'),
                new CostTreeItem('Daily Average', vscode.TreeItemCollapsibleState.None, `$${forecast.daily_average.toFixed(4)}`, 'calculator'),
                new CostTreeItem('Projected Monthly', vscode.TreeItemCollapsibleState.None, `$${forecast.projected_monthly.toFixed(2)}`, forecast.over_budget ? 'error' : 'pulse'),
                new CostTreeItem('Budget Limit', vscode.TreeItemCollapsibleState.None, `$${forecast.budget.toFixed(2)}`, 'target'),
                new CostTreeItem('Budget Remaining', vscode.TreeItemCollapsibleState.None, `$${forecast.budget_remaining.toFixed(2)}`, 'pass')
            ];
        }
        if (element.contextValue === 'section_features') {
            const featRes = await this.apiClient.getFeatures();
            if (!featRes || !featRes.features || featRes.features.length === 0) {
                return [
                    new CostTreeItem('No features recorded', vscode.TreeItemCollapsibleState.None, 'Pass feature="name" in client.create()', 'info')
                ];
            }
            const totalSpend = featRes.features.reduce((acc, f) => acc + f.total_cost, 0);
            return featRes.features.map(f => {
                const pct = totalSpend > 0 ? ((f.total_cost / totalSpend) * 100).toFixed(1) : '0';
                return new CostTreeItem(f.feature, vscode.TreeItemCollapsibleState.None, `$${f.total_cost.toFixed(4)} (${pct}% | ${f.call_count} calls)`, 'symbol-method');
            });
        }
        if (element.contextValue === 'section_warnings') {
            const warnings = await this.apiClient.getWarnings();
            if (!warnings || warnings.length === 0) {
                return [
                    new CostTreeItem('All systems nominal', vscode.TreeItemCollapsibleState.None, 'No cost drift warnings detected', 'check-all')
                ];
            }
            return warnings.map(w => new CostTreeItem(w.title, vscode.TreeItemCollapsibleState.None, w.message, w.severity === 'WARNING' ? 'warning' : 'info'));
        }
        return [];
    }
}
exports.CostTreeDataProvider = CostTreeDataProvider;
//# sourceMappingURL=costTreeDataProvider.js.map