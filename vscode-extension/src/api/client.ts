import * as http from 'http';
import * as https from 'https';
import * as vscode from 'vscode';
import { FileStatsResponse, ForecastResponse, WarningItem, FeatureResponse } from '../types';

export class CostOptApiClient {
  private getEndpoint(): string {
    return vscode.workspace.getConfiguration('costopt').get<string>('endpoint', 'http://127.0.0.1:8400');
  }

  private getBudget(): number {
    return vscode.workspace.getConfiguration('costopt').get<number>('budget', 50.0);
  }

  private async httpGet<T>(path: string): Promise<T | null> {
    const baseUrl = this.getEndpoint();
    const urlString = `${baseUrl}${path}`;

    return new Promise((resolve) => {
      try {
        const parsedUrl = new URL(urlString);
        const transport = parsedUrl.protocol === 'https:' ? https : http;

        const req = transport.get(parsedUrl, (res) => {
          if (res.statusCode !== 200) {
            resolve(null);
            return;
          }

          let body = '';
          res.on('data', (chunk) => { body += chunk; });
          res.on('end', () => {
            try {
              resolve(JSON.parse(body) as T);
            } catch {
              resolve(null);
            }
          });
        });

        req.on('error', () => {
          resolve(null);
        });

        req.setTimeout(5000, () => {
          req.destroy();
          resolve(null);
        });
      } catch {
        resolve(null);
      }
    });
  }

  async checkHealth(): Promise<boolean> {
    const data = await this.httpGet<{ status: string }>('/api/vscode/health');
    return data !== null && data.status === 'ok';
  }

  async getFileStats(filePath: string): Promise<FileStatsResponse | null> {
    const encodedPath = encodeURIComponent(filePath);
    return this.httpGet<FileStatsResponse>(`/api/vscode/file-stats?file_path=${encodedPath}`);
  }

  async getForecast(): Promise<ForecastResponse | null> {
    const budget = this.getBudget();
    return this.httpGet<ForecastResponse>(`/api/vscode/forecast?budget=${budget}`);
  }

  async getWarnings(): Promise<WarningItem[]> {
    const budget = this.getBudget();
    const res = await this.httpGet<WarningItem[]>(`/api/vscode/warnings?budget=${budget}`);
    return res || [];
  }

  async getFeatures(): Promise<FeatureResponse | null> {
    return this.httpGet<FeatureResponse>('/api/vscode/features');
  }
}
