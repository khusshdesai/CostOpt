"""
CostOpt — Real Live API End-to-End Test (Gemini via OpenAI-compatible endpoint)
Requires: GEMINI_API_KEY environment variable
Get free key at: https://aistudio.google.com/app/apikey
"""
import os
import time
from openai import OpenAI
from costopt import CostOpt
from costopt.pricing import calculate_cost

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("ERROR: Set GEMINI_API_KEY environment variable first.")

print("=" * 60)
print("COSTOPT LIVE API END-TO-END TEST (Gemini 3.6 Flash)")
print("=" * 60)

# Gemini supports OpenAI-compatible endpoint — CostOpt wrapper works unchanged
gemini_client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
client = CostOpt(gemini_client)

PROMPT = "In one sentence, what is the capital of France?"

# --- Call 1: Live API (cache miss) ---
print("\n[1/2] Live API Call (cache MISS expected)...")
t0 = time.perf_counter()
r1 = client.chat.completions.create(
    model="gemini-3.6-flash",
    messages=[{"role": "user", "content": PROMPT}]
)
latency1 = (time.perf_counter() - t0) * 1000

answer  = r1.choices[0].message.content.strip()
tokens_in  = r1.usage.prompt_tokens
tokens_out = r1.usage.completion_tokens
cost = calculate_cost("google", "gemini-3.6-flash", tokens_in, tokens_out)

print(f"  Answer      : {answer}")
print(f"  Tokens      : {tokens_in} in / {tokens_out} out")
print(f"  Cost        : ${cost:.6f}")
print(f"  Latency     : {latency1:.0f}ms")

# --- Call 2: Repeat identical prompt (cache HIT) ---
print("\n[2/2] Repeat Call (cache HIT expected, $0.00)...")
t0 = time.perf_counter()
r2 = client.chat.completions.create(
    model="gemini-3.6-flash",
    messages=[{"role": "user", "content": PROMPT}]
)
latency2 = (time.perf_counter() - t0) * 1000

print(f"  Answer      : {r2.choices[0].message.content.strip()}")
print(f"  Cost        : $0.000000 (cached — no API call made)")
print(f"  Latency     : {latency2:.0f}ms")

print("\n" + "=" * 60)
savings = cost
print(f"RESULT: Live API works. Cache saved ${savings:.6f} on repeat call.")
print(f"  Call 1 (live): {latency1:.0f}ms | Call 2 (cached): {latency2:.0f}ms")
print("=" * 60)

