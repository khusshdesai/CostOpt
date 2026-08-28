/**
 * Node.js SDK Unit Tests for CostOpt
 */

import assert from 'node:assert';
import { test, describe } from 'node:test';
import { CostOpt, CostOptCircuitBreakerError } from '../src/index.js';

describe('CostOpt Node.js SDK', () => {
  test('CostOpt wraps client and preserves standard interface', () => {
    const mockOpenAI = {
      chat: {
        completions: {
          create: async (params: any) => ({
            id: 'chatcmpl-test',
            model: params.model,
            choices: [{ message: { role: 'assistant', content: 'Test response' } }],
            usage: { prompt_tokens: 10, completion_tokens: 5 },
          }),
        },
      },
    };

    const client = CostOpt(mockOpenAI);
    assert.strictEqual(typeof client.chat.completions.create, 'function');
  });

  test('Circuit Breaker trips on rapid consecutive calls', async () => {
    const mockOpenAI = {
      chat: {
        completions: {
          create: async (_params?: any) => ({ id: 'test', choices: [] }),
        },
      },
    };

    const client = CostOpt(mockOpenAI, { maxCalls: 3, timeWindowSeconds: 10 });

    // 3 calls should succeed
    await client.chat.completions.create({ model: 'gpt-4o', messages: [] });
    await client.chat.completions.create({ model: 'gpt-4o', messages: [] });
    await client.chat.completions.create({ model: 'gpt-4o', messages: [] });

    // 4th call must trip circuit breaker
    await assert.rejects(
      async () => {
        await client.chat.completions.create({ model: 'gpt-4o', messages: [] });
      },
      (err: any) => {
        assert(err instanceof CostOptCircuitBreakerError);
        assert(err.message.includes('CostOpt Circuit Breaker TRIPPED'));
        return true;
      }
    );
  });

  test('Memory Cache hits on duplicate prompt', async () => {
    let callCount = 0;
    const mockOpenAI = {
      chat: {
        completions: {
          create: async (_params?: any) => {
            callCount++;
            return { id: `test-${callCount}`, choices: [{ message: { content: 'hello' } }] };
          },
        },
      },
    };

    const client = CostOpt(mockOpenAI, { enableCircuitBreaker: false });

    const res1 = await client.chat.completions.create({
      model: 'gpt-4o',
      messages: [{ role: 'user', content: 'Classify sentiment' }],
    });

    const res2 = await client.chat.completions.create({
      model: 'gpt-4o',
      messages: [{ role: 'user', content: 'Classify sentiment' }],
    });

    assert.strictEqual(callCount, 1); // Second call served from local cache
    assert.deepStrictEqual(res1, res2);
  });
});
