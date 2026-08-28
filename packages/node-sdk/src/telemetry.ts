/**
 * Async Non-Blocking Telemetry Logger for CostOpt Node.js SDK
 */

import http from 'http';
declare var Buffer: any;

export interface TelemetryRecord {
  timestamp?: string;
  request_id: string;
  provider: string;
  model_requested: string;
  model_used: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  status_code: number;
  success: boolean;
  error_type?: string;
  cache_hit: boolean;
  cost_original: number;
  cost_actual: number;
  savings: number;
  prompt_hash: string;
  environment: string;
  application: string;
  region: string;
  retry_count: number;
  file_path?: string;
  line_number?: number;
  task_type?: string;
  complexity?: string;
  confidence?: number;
  decision_reason?: string;
  decision_trace?: string;
}

export class TelemetryLogger {
  private endpointUrl: string;

  constructor(endpointUrl: string = 'http://127.0.0.1:8000/api/telemetry') {
    this.endpointUrl = endpointUrl;
  }

  public log(record: TelemetryRecord): void {
    if (!record.timestamp) {
      record.timestamp = new Date().toISOString();
    }

    // Non-blocking fire-and-forget HTTP POST to local CostOpt telemetry server
    try {
      const url = new URL(this.endpointUrl);
      const data = JSON.stringify(record);

      const req = http.request(
        {
          hostname: url.hostname,
          port: url.port || 80,
          path: url.pathname,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data),
          },
          timeout: 2000,
        },
        (res) => {
          res.on('data', () => {}); // Consume response stream
        }
      );

      req.on('error', () => {
        // Silent failure if local CostOpt dashboard is not running
      });

      req.write(data);
      req.end();
    } catch {
      // Ignore network errors in fire-and-forget telemetry
    }
  }
}
