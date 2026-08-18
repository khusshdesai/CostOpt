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
</p>

---

## 💡 What is CostOpt?

CostOpt puts **real-time LLM cost metrics, feature spend attribution, and runaway billing circuit breakers** directly into your VS Code editor—giving you full visibility as you write code, *before* shipping to production.

### 🔌 How it works (1-Line Code Change):

```python
# ---------------------------------------------------------
# BEFORE (Standard OpenAI Client)
# ---------------------------------------------------------
from openai import OpenAI
client = OpenAI()

# ---------------------------------------------------------
# AFTER (With CostOpt Cost Intelligence)
# ---------------------------------------------------------
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(OpenAI())  # 👈 1-line wrapper gives you instant caching, cost inlines & loop protection!

# Your API calls remain 100% identical:
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
Hover your cursor over any LLM call to inspect a compact cost breakdown, prompt MD5 hash, vector cache hit status, and response latency.

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
costopt dashboard
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
*No. CostOpt is 100% private and runs locally on your PC. All telemetry logs, similarity vectors, and pricing catalogs are stored locally in an SQLite database. Zero data leaves your computer.*

**Q: Does wrapping my client add latency overhead to my LLM calls?**  
*No. CostOpt computes prompt hashes and cache checks in under 1ms. Telemetry records are written asynchronously in a non-blocking background thread.*

**Q: How does the local cache work and what does a cache hit cost?**  
*When a repeat or highly similar prompt is detected, CostOpt replays the cached response locally in <2ms with **$0.00 cost** without hitting paid provider APIs.*

**Q: Works with LangChain, LlamaIndex, or custom frameworks?**  
*Yes. Pass the wrapped client `CostOpt(OpenAI()).client` into any framework like LangChain (`ChatOpenAI(client=...)`) or LlamaIndex.*

**Q: What if the status bar displays `CostOpt: Offline`?**  
*Start the local background service by running `costopt dashboard` in your terminal.*

**Q: How do I track custom, fine-tuned, or local Ollama models?**  
*Drop a `.yaml` file into your project or pricing directory with model costs (e.g. `input_cost_per_1m: 0.0` for local Ollama models).*

---

## 📄 License
Licensed under the [MIT License](https://github.com/khusshdesai/CostOpt/blob/main/LICENSE).
