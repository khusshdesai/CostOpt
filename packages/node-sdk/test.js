const assert = require('assert');
const { CostOpt, CostOptCircuitBreakerError } = require('./index.js');

async function runTests() {
  console.log('🧪 Running CostOpt Node.js SDK test suite...');

  // Test 1: Interface preservation
  const mockOpenAI = {
    chat: {
      completions: {
        create: async (params) => ({
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
  console.log('✅ Test 1 Passed: Client interface wrapper initialized successfully');

  // Test 2: Circuit Breaker Interception
  const mockLoopClient = {
    chat: {
      completions: {
        create: async () => ({ id: 'test', choices: [] }),
      },
    },
  };

  const loopClient = CostOpt(mockLoopClient, { maxCalls: 3, timeWindowSeconds: 10 });
  await loopClient.chat.completions.create({ model: 'gpt-4o', messages: [] });
  await loopClient.chat.completions.create({ model: 'gpt-4o', messages: [] });
  await loopClient.chat.completions.create({ model: 'gpt-4o', messages: [] });

  let tripped = false;
  try {
    await loopClient.chat.completions.create({ model: 'gpt-4o', messages: [] });
  } catch (err) {
    if (err instanceof CostOptCircuitBreakerError) {
      tripped = true;
    }
  }
  assert.strictEqual(tripped, true);
  console.log('✅ Test 2 Passed: Circuit breaker tripped on runaway loop');

  // Test 3: Local Memory Cache Hit
  let callCount = 0;
  const mockCacheClient = {
    chat: {
      completions: {
        create: async () => {
          callCount++;
          return { id: `test-${callCount}`, choices: [{ message: { content: 'hello' } }] };
        },
      },
    },
  };

  const cacheClient = CostOpt(mockCacheClient, { enableCircuitBreaker: false });
  const r1 = await cacheClient.chat.completions.create({ model: 'gpt-4o', messages: [{ role: 'user', content: 'hello' }] });
  const r2 = await cacheClient.chat.completions.create({ model: 'gpt-4o', messages: [{ role: 'user', content: 'hello' }] });

  assert.strictEqual(callCount, 1);
  assert.deepStrictEqual(r1, r2);
  console.log('✅ Test 3 Passed: Cache hit served duplicate prompt without hitting API');

  console.log('🎉 All CostOpt Node.js SDK tests PASSED cleanly!');
}

runTests().catch((err) => {
  console.error('❌ Test failed:', err);
  process.exit(1);
});
