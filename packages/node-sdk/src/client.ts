/**
 * CostOpt Node.js/TypeScript Wrapper
 * 1-Line Drop-in Client for OpenAI Node.js SDK
 */

import { CircuitBreaker } from './circuit_breaker.js';
import { TelemetryLogger, TelemetryRecord } from './telemetry.js';
import { MemoryCache } from './cache.js';

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

export function CostOpt<T extends object>(
  rawClient: T,
  options: CostOptOptions = {}
): T {
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

  // Helper to extract calling line for circuit breaker
  function getCallSite(): string {
    const err = new Error();
    const stack = err.stack?.split('\n') || [];
    for (let i = 2; i < stack.length; i++) {
      const line = stack[i];
      if (!line.includes('CostOpt') && !line.includes('node_modules')) {
        const match = line.match(/\((.+):(\d+):(\d+)\)/) || line.match(/at\s+(.+):(\d+):(\d+)/);
        if (match) {
          return `${match[1]}:${match[2]}`;
        }
      }
    }
    return 'unknown:0';
  }

  // Intercept client.chat.completions.create
  const handler: ProxyHandler<any> = {
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
                    return async function (params: any, reqOptions?: any) {
                      const startTime = Date.now();
                      const callSite = getCallSite();

                      // 1. Circuit Breaker Check
                      if (enableCircuitBreaker) {
                        circuitBreaker.checkAndRecord(callSite);
                      }

                      const modelRequested = params.model || 'gpt-4o';
                      let modelUsed = modelRequested;

                      // Extract prompt text
                      let promptText = '';
                      if (Array.isArray(params.messages)) {
                        promptText = params.messages
                          .map((m: any) => `${m.role}: ${m.content}`)
                          .join('\n');
                      }

                      // 2. Local Cache Check
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

                      // 3. Smart Model Rerouting (simple classification -> gpt-4o-mini)
                      if (
                        enableRouting &&
                        modelRequested === 'gpt-4o' &&
                        /\b(classify|sentiment|yes\/no|label|category)\b/i.test(promptText)
                      ) {
                        modelUsed = 'gpt-4o-mini';
                        params.model = 'gpt-4o-mini';
                      }

                      // Execute original LLM call
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
                      } catch (err: any) {
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
