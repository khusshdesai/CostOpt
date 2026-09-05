/**
 * CostOpt Node.js & TypeScript SDK
 * Developer-Native LLM Cost Intelligence
 */

const http = require('http');
const crypto = require('crypto');

class CostOptCircuitBreakerError extends Error {
  constructor(message) {
    super(message);
    this.name = 'CostOptCircuitBreakerError';
  }
}

class CircuitBreaker {
  constructor(maxCalls = 15, timeWindowSeconds = 30) {
    this.maxCalls = maxCalls;
    this.timeWindowMs = timeWindowSeconds * 1000;
    this.history = new Map();
  }

  checkAndRecord(locationKey) {
    if (!locationKey) return;
    const now = Date.now();
    const cutoff = now - this.timeWindowMs;
    const timestamps = (this.history.get(locationKey) || []).filter(t => t >= cutoff);
    timestamps.push(now);
    this.history.set(locationKey, timestamps);

    if (timestamps.length > this.maxCalls) {
      throw new CostOptCircuitBreakerError(
        `CostOpt Circuit Breaker TRIPPED for [${locationKey}]: Exceeded ${this.maxCalls} calls in ${this.timeWindowMs / 1000}s. Intercepted to prevent runaway billing leak.`
      );
    }
  }
}

class TelemetryLogger {
  constructor(endpointUrl = 'http://127.0.0.1:8400/api/telemetry') {
    this.endpointUrl = endpointUrl;
  }

  log(record) {
    if (!record.timestamp) record.timestamp = new Date().toISOString();
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
        (res) => res.on('data', () => {})
      );
      req.on('error', () => {});
      req.write(data);
      req.end();
    } catch (e) {}
  }
}

class MemoryCache {
  constructor() {
    this.cache = new Map();
  }

  getHash(text) {
    return crypto.createHash('md5').update(text || '').digest('hex');
  }

  get(promptText, model) {
    const key = `${this.getHash(promptText)}||${model}`;
    const item = this.cache.get(key);
    return item ? item.response : null;
  }

  set(promptText, model, response) {
    const key = `${this.getHash(promptText)}||${model}`;
    this.cache.set(key, { response, createdAt: Date.now() });
  }
}

function CostOpt(rawClient, options = {}) {
  const circuitBreaker = new CircuitBreaker(
    options.maxCalls ?? 15,
    options.timeWindowSeconds ?? 30
  );
  const telemetry = new TelemetryLogger(options.dashboardUrl);
  const memoryCache = new MemoryCache();

  const enableCircuitBreaker = options.enableCircuitBreaker ?? true;
  const enableCache = options.enableCache ?? true;
  const enableRouting = options.enableRouting ?? true;
  const appName = options.application ?? 'node_app';
  const envName = options.environment ?? 'development';

  function getCallSite() {
    const err = new Error();
    const stack = err.stack?.split('\n') || [];
    for (let i = 2; i < stack.length; i++) {
      const line = stack[i];
      if (!line.includes('CostOpt') && !line.includes('node_modules')) {
        const match = line.match(/\((.+):(\d+):(\d+)\)/) || line.match(/at\s+(.+):(\d+):(\d+)/);
        if (match) return `${match[1]}:${match[2]}`;
      }
    }
    return 'unknown:0';
  }

  const handler = {
    get(target, prop, receiver) {
      if (prop === 'chat') {
        const chatTarget = target.chat;
        return new Proxy(chatTarget, {
          get(cTarget, cProp) {
            if (cProp === 'completions') {
              const compTarget = cTarget.completions;
              return new Proxy(compTarget, {
                get(compT, compP) {
                  if (compP === 'create') {
                    return async function (params, reqOptions) {
                      const startTime = Date.now();
                      const callSite = getCallSite();

                      if (enableCircuitBreaker) {
                        circuitBreaker.checkAndRecord(callSite);
                      }

                      const modelRequested = params.model || 'gpt-4o';
                      let modelUsed = modelRequested;
                      let promptText = '';
                      if (Array.isArray(params.messages)) {
                        promptText = params.messages.map((m) => `${m.role}: ${m.content}`).join('\n');
                      }

                      if (enableCache) {
                        const cached = memoryCache.get(promptText, modelRequested);
                        if (cached) {
                          const latency = Date.now() - startTime;
                          telemetry.log({
                            request_id: `req_${Math.random().toString(36).slice(2, 11)}`,
                            provider: 'openai',
                            model_requested: modelRequested,
                            model_used: modelRequested,
                            input_tokens: Math.max(1, Math.floor(promptText.length / 4)),
                            output_tokens: 15,
                            latency_ms: latency,
                            status_code: 200,
                            success: true,
                            cache_hit: true,
                            cost_original: 0.0001,
                            cost_actual: 0.0,
                            savings: 0.0001,
                            prompt_hash: memoryCache.getHash(promptText),
                            environment: envName,
                            application: appName,
                            region: 'local',
                            retry_count: 0,
                            decision_reason: 'Served from local Node.js memory cache',
                          });
                          return cached;
                        }
                      }

                      if (
                        enableRouting &&
                        modelRequested === 'gpt-4o' &&
                        /\b(classify|sentiment|yes\/no|label|category)\b/i.test(promptText)
                      ) {
                        modelUsed = 'gpt-4o-mini';
                        params.model = 'gpt-4o-mini';
                      }

                      try {
                        const response = await compT.create.call(compTarget, params, reqOptions);
                        const latency = Date.now() - startTime;

                        if (enableCache) {
                          memoryCache.set(promptText, modelRequested, response);
                        }

                        const usage = response.usage || {};
                        const inTokens = usage.prompt_tokens || Math.max(1, Math.floor(promptText.length / 4));
                        const outTokens = usage.completion_tokens || 30;

                        telemetry.log({
                          request_id: response.id || `req_${Math.random().toString(36).slice(2, 11)}`,
                          provider: 'openai',
                          model_requested: modelRequested,
                          model_used: modelUsed,
                          input_tokens: inTokens,
                          output_tokens: outTokens,
                          latency_ms: latency,
                          status_code: 200,
                          success: true,
                          cache_hit: false,
                          cost_original: (inTokens * 0.0025 + outTokens * 0.01) / 1000,
                          cost_actual: (inTokens * 0.00015 + outTokens * 0.0006) / 1000,
                          savings: modelRequested !== modelUsed ? 0.0001 : 0.0,
                          prompt_hash: memoryCache.getHash(promptText),
                          environment: envName,
                          application: appName,
                          region: 'local',
                          retry_count: 0,
                          decision_reason: modelRequested !== modelUsed ? 'Rerouted simple task to gpt-4o-mini' : 'Direct request execution',
                        });

                        return response;
                      } catch (err) {
                        const latency = Date.now() - startTime;
                        telemetry.log({
                          request_id: `err_${Math.random().toString(36).slice(2, 11)}`,
                          provider: 'openai',
                          model_requested: modelRequested,
                          model_used: modelUsed,
                          input_tokens: 0,
                          output_tokens: 0,
                          latency_ms: latency,
                          status_code: err.status || 500,
                          success: false,
                          error_type: err.name || 'Error',
                          cache_hit: false,
                          cost_original: 0,
                          cost_actual: 0,
                          savings: 0,
                          prompt_hash: memoryCache.getHash(promptText),
                          environment: envName,
                          application: appName,
                          region: 'local',
                          retry_count: 0,
                          decision_reason: `API Call Failed: ${err.message}`,
                        });
                        throw err;
                      }
                    };
                  }
                  return Reflect.get(compT, compP, receiver);
                },
              });
            }
            return Reflect.get(cTarget, cProp, receiver);
          },
        });
      }
      return Reflect.get(target, prop, receiver);
    },
  };

  return new Proxy(rawClient, handler);
}

module.exports = {
  CostOpt,
  CostOptCircuitBreakerError,
  CircuitBreaker,
  MemoryCache,
  TelemetryLogger,
};
