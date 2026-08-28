/**
 * CostOpt Node.js & TypeScript SDK Type Definitions
 */

export interface CostOptOptions {
  enableCircuitBreaker?: boolean;
  maxCalls?: number;
  timeWindowSeconds?: number;
  enableCache?: boolean;
  enableRouting?: boolean;
  dashboardUrl?: string;
  application?: string;
  environment?: string;
}

export class CostOptCircuitBreakerError extends Error {
  constructor(message: string);
}

export class CircuitBreaker {
  constructor(maxCalls?: number, timeWindowSeconds?: number);
  checkAndRecord(locationKey: string): void;
  reset(locationKey?: string): void;
}

export class MemoryCache {
  constructor();
  getHash(text: string): string;
  get(promptText: string, model: string): any | null;
  set(promptText: string, model: string, response: any): void;
}

export class TelemetryLogger {
  constructor(endpointUrl?: string);
  log(record: any): void;
}

export function CostOpt<T extends object>(
  rawClient: T,
  options?: CostOptOptions
): T;
