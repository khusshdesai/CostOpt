"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CostCodeLensProvider = void 0;
const vscode = require("vscode");
class CostCodeLensProvider {
    apiClient;
    _onDidChangeCodeLenses = new vscode.EventEmitter();
    onDidChangeCodeLenses = this._onDidChangeCodeLenses.event;
    constructor(apiClient) {
        this.apiClient = apiClient;
    }
    refresh() {
        this._onDidChangeCodeLenses.fire();
    }
    async provideCodeLenses(document, token) {
        const isEnabled = vscode.workspace.getConfiguration('costopt').get('enabled', true);
        if (!isEnabled) {
            return [];
        }
        const lenses = [];
        const text = document.getText();
        // Regex matching LLM call sites in Python, JS, TS
        const llmCallRegex = /(?:chat\.completions\.create|completions\.create|client\.create|llm\.invoke|generate_content|\bCostOpt\b|@costopt\.track)/g;
        const fileStats = await this.apiClient.getFileStats(document.fileName);
        let match;
        while ((match = llmCallRegex.exec(text)) !== null) {
            const position = document.positionAt(match.index);
            const lineNumber = position.line + 1; // 1-indexed
            const range = new vscode.Range(position, position);
            // Check if line telemetry exists
            const lineStat = fileStats?.line_stats.find(s => s.line_number === lineNumber) || null;
            let title;
            if (lineStat && lineStat.call_count > 0) {
                const avgCost = lineStat.avg_cost_per_call > 0 ? `$${lineStat.avg_cost_per_call.toFixed(4)}` : '$0.00 (cached)';
                const avgTokens = lineStat.avg_input_tokens + lineStat.avg_output_tokens;
                title = `CostOpt: ~${avgCost} / request | Avg tokens: ${avgTokens.toLocaleString()} | Calls: ${lineStat.call_count}`;
            }
            else {
                title = `CostOpt: No telemetry recorded yet for this LLM call`;
            }
            lenses.push(new vscode.CodeLens(range, {
                title: title,
                command: 'costopt.showCurrentFileCost',
                arguments: [document.fileName, lineNumber]
            }));
        }
        return lenses;
    }
}
exports.CostCodeLensProvider = CostCodeLensProvider;
//# sourceMappingURL=costCodeLensProvider.js.map