"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CostOptApiClient = void 0;
const http = require("http");
const https = require("https");
const vscode = require("vscode");
class CostOptApiClient {
    getEndpoint() {
        return vscode.workspace.getConfiguration('costopt').get('endpoint', 'http://127.0.0.1:8400');
    }
    getBudget() {
        return vscode.workspace.getConfiguration('costopt').get('budget', 50.0);
    }
    async httpGet(path) {
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
                            resolve(JSON.parse(body));
                        }
                        catch {
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
            }
            catch {
                resolve(null);
            }
        });
    }
    async checkHealth() {
        const data = await this.httpGet('/api/vscode/health');
        return data !== null && data.status === 'ok';
    }
    async getFileStats(filePath) {
        const encodedPath = encodeURIComponent(filePath);
        return this.httpGet(`/api/vscode/file-stats?file_path=${encodedPath}`);
    }
    async getForecast() {
        const budget = this.getBudget();
        return this.httpGet(`/api/vscode/forecast?budget=${budget}`);
    }
    async getWarnings() {
        const budget = this.getBudget();
        const res = await this.httpGet(`/api/vscode/warnings?budget=${budget}`);
        return res || [];
    }
    async getFeatures() {
        return this.httpGet('/api/vscode/features');
    }
}
exports.CostOptApiClient = CostOptApiClient;
//# sourceMappingURL=client.js.map