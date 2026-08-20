# CostOpt — Cost Intelligence While You Code ⚡

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/costopt_logo.png" width="120" alt="CostOpt Logo" />
</p>

<p align="center">
  <strong>Developer-native LLM cost intelligence directly inside VS Code.</strong>
  <br />
  Stop waiting for a $500 monthly cloud bill to figure out where your LLM budget went.
</p>

<p align="center">
  <a href="https://pypi.org/project/costopt/"><img src="https://img.shields.io/pypi/v/costopt?color=blue&style=flat-square" alt="PyPI"></a>
  <a href="https://github.com/khusshdesai/CostOpt/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/VS%20Code-1.80%2B-purple.svg?style=flat-square" alt="VS Code Version">
  <img src="https://img.shields.io/badge/Open%20VSX-1K%2B%20installs-orange?style=flat-square" alt="Installs">
  <img src="https://img.shields.io/badge/VS%20Marketplace-v0.1.7-blue?style=flat-square" alt="VS Marketplace">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/dashboard_overview.png" width="900" alt="CostOpt Dashboard Console" />
</p>

---

## 💡 What is CostOpt?

CostOpt puts **real-time LLM cost metrics, feature spend attribution, and runaway billing circuit breakers** directly into your VS Code editor — giving you full visibility as you write code, *before* shipping to production.

### 🔌 1-Line Code Change:

```python
# ─── BEFORE ─────────────────────────────────────────────────────────────────
from openai import OpenAI
client = OpenAI()

# ─── AFTER (with CostOpt) ───────────────────────────────────────────────────
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(OpenAI())  # 👈 Instant caching, cost inlines & loop protection!

# All your existing API calls remain 100% identical:
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Classify customer feedback"}]
)
```

---

## ⚡ Key Features

### 1. 🔍 Live CodeLens Cost Inlines
See real-time cost per request, average token usage, and total call volume directly above your `client.chat.completions.create()` code lines:
```python
# CostOpt: ~$0.012 / request | Avg tokens: 3,421 | Calls: 184
response = client.chat.completions.create(model="gpt-4o", messages=...)
```

### 2. 💬 Rich Hover Cost Intelligence
Hover over any LLM call to inspect a compact cost breakdown, prompt MD5 hash, vector cache hit status, and response latency.

### 3. 🛡️ Silent Infinite Loop Circuit Breaker
Automatically detects rapid call loops (>15 calls in 30s) from the same line of code and trips `CostOptCircuitBreakerError` locally to kill runaway billing leaks before they burn your API key.

### 4. 🔄 Zero-Downtime Outage Failover (429/503)
Automatically reroutes queries to configured fallback models (`gpt-4o` → `claude-3-5-sonnet` or local `ollama/llama3`) when primary providers hit rate limits or outages.

### 5. 📊 Activity Bar Sidebar Views
Access native tree views in the VS Code sidebar:
- 📈 **Spend Forecast**: Monthly budget run rate & projected spend.
- 🏷️ **Feature Attribution**: Spend broken down by feature (`feature="rag_summarizer"`).
- ⚠️ **Cost Drift Warnings**: Real-time alerts for budget overruns or runaway loops.

### 6. 📌 Status Bar Widget
Displays your current daily spend directly in the bottom status bar (`CostOpt: $8.42 today`).

---

## 📊 Dashboard

The full observability dashboard includes 4 views:

| Tab | What it shows |
|---|---|
| **Overview** | Live telemetry stream, SDK sim, YAML policy rules, anomaly alerts |
| **Analytics** | Token volumes by provider, cache efficiency, latency comparison |
| **Traces** | Full searchable trace explorer with cost, latency, model routing per call |
| **Settings** | Configure similarity threshold, TTL, budget, and reset telemetry |

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/dashboard_analytics.png" width="880" alt="Analytics Tab" />
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/dashboard_traces.png" width="880" alt="Traces Tab" />
</p>

---

## 🚀 3-Step Setup Guide

### Step 1: Install Python SDK
```bash
pip install costopt
```

### Step 2: Wrap your OpenAI client in 1 line
```python
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(OpenAI())
```

### Step 3: Launch Local Service
```bash
python -m costopt.main dashboard
```
*Your VS Code extension will automatically connect to `http://localhost:8000`!*

---

## ⌨️ Available Commands

Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS) and type **`CostOpt`**:

| Command | Description |
| :--- | :--- |
| **`CostOpt: Show Cost Summary`** | Opens a quick-pick popup with total spend, daily avg, and forecast. |
| **`CostOpt: Show Feature Costs`** | Displays spend breakdown per feature tag. |
| **`CostOpt: Show Active Warnings`** | Lists active budget overruns and drift warnings. |
| **`CostOpt: Open Dashboard`** | Launches the web console at `http://localhost:8000`. |
| **`CostOpt: Refresh Analytics`** | Instantly syncs status bar and sidebar views. |

---

## ❓ Frequently Asked Questions

**Q: Does CostOpt send my prompts or code to external servers?**
> No. 100% local. All telemetry, cache, and pricing data is stored in local SQLite files. Zero data leaves your machine.

**Q: Does wrapping my client add latency overhead to my LLM calls?**
> No. Prompt hashing and cache checks take under 1ms. Telemetry is written asynchronously in a background thread.

**Q: How does the local cache work and what does a cache hit cost?**
> `$0.00`. When a repeat or highly similar prompt is detected, CostOpt replays the cached response locally in <2ms without hitting paid provider APIs.

**Q: Works with LangChain, LlamaIndex, or custom frameworks?**
> Yes. Pass the wrapped client `CostOpt(OpenAI()).client` into any framework like LangChain (`ChatOpenAI(client=...)`) or LlamaIndex.

**Q: What if the status bar displays `CostOpt: Offline`?**
> Start the local background service: `python -m costopt.main dashboard`

**Q: How do I track custom, fine-tuned, or local Ollama models?**
> Drop a `.yaml` file into your project or `pricing/providers/` directory with model costs (e.g. `input_cost_per_1m: 0.0` for local Ollama models).

---

## 📄 License
Licensed under the [MIT License](https://github.com/khusshdesai/CostOpt/blob/main/LICENSE).
