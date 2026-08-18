import * as vscode from 'vscode';
import { CostOptApiClient } from '../api/client';

export class CostDiagnosticsManager {
  private diagnosticCollection: vscode.DiagnosticCollection;

  constructor(private apiClient: CostOptApiClient) {
    this.diagnosticCollection = vscode.languages.createDiagnosticCollection('costopt');
  }

  public async updateDiagnostics(): Promise<void> {
    const isEnabled = vscode.workspace.getConfiguration('costopt').get<boolean>('enabled', true);
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
    const diagnostics: vscode.Diagnostic[] = [];

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

  public dispose(): void {
    this.diagnosticCollection.clear();
    this.diagnosticCollection.dispose();
  }
}
