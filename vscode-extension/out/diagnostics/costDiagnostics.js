"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CostDiagnosticsManager = void 0;
const vscode = require("vscode");
class CostDiagnosticsManager {
    apiClient;
    diagnosticCollection;
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.diagnosticCollection = vscode.languages.createDiagnosticCollection('costopt');
    }
    async updateDiagnostics() {
        const isEnabled = vscode.workspace.getConfiguration('costopt').get('enabled', true);
        if (!isEnabled) {
            this.diagnosticCollection.clear();
            return;
        }
        const warnings = await this.apiClient.getWarnings();
        if (!warnings || warnings.length === 0) {
            this.diagnosticCollection.clear();
            return;
        }
        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor) {
            return;
        }
        const doc = activeEditor.document;
        const diagnostics = [];
        for (const w of warnings) {
            const severity = w.severity === 'WARNING'
                ? vscode.DiagnosticSeverity.Warning
                : vscode.DiagnosticSeverity.Information;
            const range = new vscode.Range(0, 0, 0, doc.lineAt(0).text.length);
            const diagnostic = new vscode.Diagnostic(range, `[CostOpt] ${w.title}: ${w.message}`, severity);
            diagnostic.code = w.code;
            diagnostic.source = 'CostOpt Intelligence';
            diagnostics.push(diagnostic);
        }
        this.diagnosticCollection.set(doc.uri, diagnostics);
    }
    dispose() {
        this.diagnosticCollection.clear();
        this.diagnosticCollection.dispose();
    }
}
exports.CostDiagnosticsManager = CostDiagnosticsManager;
//# sourceMappingURL=costDiagnostics.js.map