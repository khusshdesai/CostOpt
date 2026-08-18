import * as vscode from 'vscode';
import { CostOptApiClient } from '../api/client';

export class CostCodeLensProvider implements vscode.CodeLensProvider {
  private _onDidChangeCodeLenses: vscode.EventEmitter<void> = new vscode.EventEmitter<void>();
  public readonly onDidChangeCodeLenses: vscode.Event<void> = this._onDidChangeCodeLenses.event;

  constructor(private apiClient: CostOptApiClient) {}

  public refresh(): void {
    this._onDidChangeCodeLenses.fire();
  }

  public async provideCodeLenses(
    document: vscode.TextDocument,
    token: vscode.CancellationToken
  ): Promise<vscode.CodeLens[]> {
    const isEnabled = vscode.workspace.getConfiguration('costopt').get<boolean>('enabled', true);
    if (!isEnabled) {
      return [];
    }

    const lenses: vscode.CodeLens[] = [];
    const text = document.getText();

    // Regex matching LLM call sites in Python, JS, TS
    const llmCallRegex = /(?:chat\.completions\.create|completions\.create|client\.create|llm\.invoke|generate_content|\bCostOpt\b|@costopt\.track)/g;

    const fileStats = await this.apiClient.getFileStats(document.fileName);

    let match: RegExpExecArray | null;
    while ((match = llmCallRegex.exec(text)) !== null) {
      const position = document.positionAt(match.index);
      const lineNumber = position.line + 1; // 1-indexed

      const range = new vscode.Range(position, position);

      // Check if line telemetry exists
      const lineStat = fileStats?.line_stats.find(s => s.line_number === lineNumber) || 
                       (fileStats?.line_stats.length ? fileStats.line_stats[0] : null);

      let title: string;
      if (lineStat && lineStat.call_count > 0) {
        const avgCost = lineStat.avg_cost_per_call > 0 ? `$${lineStat.avg_cost_per_call.toFixed(4)}` : '$0.00 (cached)';
        const avgTokens = lineStat.avg_input_tokens + lineStat.avg_output_tokens;
        title = `CostOpt: ~${avgCost} / request | Avg tokens: ${avgTokens.toLocaleString()} | Calls: ${lineStat.call_count}`;
      } else {
        title = `CostOpt: No telemetry recorded yet for this LLM call`;
      }

      lenses.push(
        new vscode.CodeLens(range, {
          title: title,
          command: 'costopt.showCurrentFileCost',
          arguments: [document.fileName, lineNumber]
        })
      );
    }

    return lenses;
  }
}
