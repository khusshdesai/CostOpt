/**
 * Circuit Breaker for CostOpt Node.js SDK
 * Intercepts rapid unthrottled call loops to prevent runaway LLM billing leaks.
 */

export class CostOptCircuitBreakerError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CostOptCircuitBreakerError';
    Object.setPrototypeOf(this, CostOptCircuitBreakerError.prototype);
  }
}

export class CircuitBreaker {
  private maxCalls: number;
  private timeWindowMs: number;
  private history: Map<string, number[]>;

  constructor(maxCalls: number = 15, timeWindowSeconds: number = 30.0) {
    this.maxCalls = maxCalls;
    this.timeWindowMs = timeWindowSeconds * 1000;
    this.history = new Map();
  }

  public checkAndRecord(locationKey: string): void {
    if (!locationKey) return;

    const now = Date.now();
    const cutoff = now - this.timeWindowMs;

    const timestamps = this.history.get(locationKey) || [];
    const recentTimestamps = timestamps.filter(t => t >= cutoff);
    recentTimestamps.push(now);

    this.history.set(locationKey, recentTimestamps);

    if (recentTimestamps.length > this.maxCalls) {
      const msg = `CostOpt Circuit Breaker TRIPPED for [${locationKey}]: ` +
        `Exceeded ${this.maxCalls} calls in ${this.timeWindowMs / 1000}s window (${recentTimestamps.length} calls recorded). ` +
        `Intercepted to prevent runaway LLM billing leak.`;
      throw new CostOptCircuitBreakerError(msg);
    }
  }

  public reset(locationKey?: string): void {
    if (locationKey) {
      this.history.delete(locationKey);
    } else {
      this.history.clear();
    }
  }
}
