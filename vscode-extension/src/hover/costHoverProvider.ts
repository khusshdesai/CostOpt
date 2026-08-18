import * as vscode from 'vscode';
import { CostOptApiClient } from '../api/client';

export class CostHoverProvider implements vscode.HoverProvider {
  constructor(private apiClient: CostOptApiClient) {}

  public async provideHover(
    document: vscode.TextDocument,
    position: vscode.Position,
    token: vscode.CancellationToken
  ): Promise<vscode.Hover | null> {
    const isEnabled = vscode.workspace.getConfiguration('costopt').get<boolean>('enabled', true);
    if (!isEnabled) {
      return null;
    }

    const lineText = document.lineAt(position.line).text;
    const isLlmCall = /(?:chat\.completions\.create|completions\.create|client\.create|llm\.invoke|generate_content|\bCostOpt\b|@costopt\.track)/.test(lineText);

    if (!isLlmCall) {
      return null;
    }

    const fileStats = await this.apiClient.getFileStats(document.fileName);
    const forecast = await this.apiClient.getForecast();
    const lineNumber = position.line + 1;

    const lineStat = fileStats?.line_stats.find(s => s.line_number === lineNumber) || 
                     (fileStats?.line_stats.length ? fileStats.line_stats[0] : null);

    const md = new vscode.MarkdownString();
    md.isTrusted = true;

    md.appendMarkdown(`### ⚡ CostOpt Intelligence\n\n`);

    if (lineStat && lineStat.call_count > 0) {
      const avgCostStr = lineStat.avg_cost_per_call > 0 ? `$${lineStat.avg_cost_per_call.toFixed(4)}` : '$0.0000 (cached)';
      const cacheHitRate = ((lineStat.cache_hits / lineStat.call_count) * 100).toFixed(1);

      md.appendMarkdown(`**Model**: \`${lineStat.model}\`  \n`);
      md.appendMarkdown(`**Observed Average**: \`${avgCostStr}/request\`  \n`);
      md.appendMarkdown(`**Input Tokens**: \`${lineStat.avg_input_tokens.toLocaleString()} avg\`  \n`);
      md.appendMarkdown(`**Output Tokens**: \`${lineStat.avg_output_tokens.toLocaleString()} avg\`  \n`);
      md.appendMarkdown(`**Avg Latency**: \`${lineStat.avg_latency_ms}ms\`  \n`);
      md.appendMarkdown(`**Calls Recorded**: \`${lineStat.call_count}\` (\`${cacheHitRate}%\` cache hits)  \n\n`);
    } else {
      md.appendMarkdown(`*No telemetry recorded for this call yet.*  \n\n`);
    }

    md.appendMarkdown(`---\n\n`);
    md.appendMarkdown(`**Estimated Application Spend**:  \n`);

    if (forecast && forecast.has_enough_data) {
      md.appendMarkdown(`- **Today**: \`$${forecast.spend_today.toFixed(2)}\`  \n`);
      md.appendMarkdown(`- **Projected Monthly**: \`$${forecast.projected_monthly.toFixed(2)}\` / \`$${forecast.budget.toFixed(2)}\` budget  \n`);
    } else {
      md.appendMarkdown(`- *Not enough usage data for monthly forecast.*  \n`);
    }

    return new vscode.Hover(md);
  }
}
