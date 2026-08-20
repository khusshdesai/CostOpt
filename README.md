# CostOpt — Developer-Native LLM Cost Intelligence ⚡

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/costopt_logo.png" width="140" alt="CostOpt Logo" />
</p>

<p align="center">
  <strong>Drop-in wrapper for OpenAI, Anthropic & Gemini clients that adds automatic caching, smart model routing, circuit breaker protection, and a real-time observability dashboard — all 100% local.</strong>
  <br />
  Stop waiting for a $500 monthly cloud bill to figure out where your LLM budget went.
</p>

<p align="center">
  <a href="https://pypi.org/project/costopt/"><img src="https://img.shields.io/pypi/v/costopt?color=blue&style=flat-square" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/costopt/"><img src="https://img.shields.io/badge/downloads-available-brightgreen?style=flat-square" alt="PyPI Downloads"></a>
  <a href="https://open-vsx.org/extension/khusshdesai/costopt-vscode"><img src="https://img.shields.io/badge/Open%20VSX-1K%2B%20installs-purple?style=flat-square" alt="Open VSX Installs"></a>
  <a href="https://marketplace.visualstudio.com/items?itemName=khusshdesai.costopt-vscode"><img src="https://img.shields.io/badge/VS%20Marketplace-v0.1.7-blue?style=flat-square" alt="VS Marketplace"></a>
  <a href="https://github.com/khusshdesai/CostOpt/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/VS%20Code-1.80%2B-purple?style=flat-square" alt="VS Code 1.80+">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/dashboard_overview.png" width="900" alt="CostOpt Dashboard — System Overview" />
</p>

---

## 📋 Table of Contents

- [What is CostOpt?](#-what-is-costopt)
- [1-Line Integration](#-1-line-zero-churn-integration)
- [Core Features](#-core-features)
- [Quickstart Guide](#-quickstart-guide)
- [Dashboard](#-observability-dashboard)
- [Multi-Provider Support](#-multi-provider-support)
- [Framework Integrations](#-integration-with-popular-frameworks)
- [Configuration](#-configuration--custom-models)
- [VS Code Extension](#-vs-code-extension)
- [FAQ](#-faq)
- [License](#-license)

---

## 💡 What is CostOpt?

CostOpt is a **developer SDK** that wraps your existing OpenAI, Anthropic, or Google Gemini client in a single line of code. Once wrapped, every LLM call is automatically:

- ✅ **Cached locally** — repeat or near-duplicate prompts return in `<2ms` at `$0.00` cost
- ✅ **Routed intelligently** — simple tasks automatically rerouted to cheaper models (e.g. `gpt-4o` → `gpt-4o-mini`)
- ✅ **Protected from runaway loops** — circuit breaker trips before silent billing explosions
- ✅ **Logged with full cost attribution** — every call recorded to SQLite with cost, latency, model used, and file/line location

No cloud, no accounts, no data leaving your machine.

---

## 🔌 1-Line Zero-Churn Integration

```python
# ─── BEFORE (Standard OpenAI Client) ────────────────────────────────────────
from openai import OpenAI
client = OpenAI()

# ─── AFTER (With CostOpt — zero other changes needed) ───────────────────────
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(OpenAI())  # 👈 That's it.

# Your API calls are 100% identical — CostOpt intercepts transparently:
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Classify customer feedback"}],
    feature="customer_support"   # optional: tag for cost attribution in dashboard
)
```

---

## ⚡ Core Features

| Feature | Description |
|---|---|
| 🗄️ **Local SQLite Cache** | Exact + fuzzy (Jaccard/TF-IDF) matching. Cache key includes model, temperature, tools, seed. |
| 🔀 **Smart Model Router** | Rule-based keyword routing — simple tasks auto-rerouted to cheaper models. |
| 🛡️ **Circuit Breaker** | Detects >15 calls in 30s from the same file:line and trips `CostOptCircuitBreakerError`. |
| 🔄 **Outage Failover** | Auto-retries fallback models on 429/503 (`gpt-4o` → `claude-3-5-sonnet` → `llama3`). |
| 📊 **Observability Dashboard** | Real-time spend metrics, trace explorer, anomaly detection, and YAML policy viewer. |
| 🔍 **VS Code CodeLens** | Cost-per-request and call counts shown inline above your code. |
| 🔒 **100% Local & Private** | Everything stored in SQLite. Zero data leaves your machine. |

---

## 🚀 Quickstart Guide

### Step 1 — Install Python SDK
```bash
pip install costopt
```

### Step 2 — Wrap your LLM client
```python
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(OpenAI())

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum mechanics simply"}],
    feature="education"
)
print(response.choices[0].message.content)
```

### Step 3 — Launch the Observability Dashboard
```bash
python -m costopt.main dashboard
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 📊 Observability Dashboard

CostOpt comes with a full-featured local dashboard running on FastAPI + vanilla JS.

### System Overview
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/dashboard_overview.png" width="880" alt="Dashboard Overview" />
</p>

> Live telemetry stream, SDK route simulator, active YAML policy rules, anomaly detection, and optimization strategies.

### Analytics & Performance
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/dashboard_analytics.png" width="880" alt="Analytics Tab" />
</p>

> Provider token volumes (OpenAI / Anthropic / Google), cache efficiency metrics, and average latency comparisons (cached vs direct).

### Trace Explorer
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/dashboard_traces.png" width="880" alt="Traces Tab" />
</p>

> Full-screen trace log with MD5 prompt hash, requested model, executed model (after routing), latency, actual cost, and status code. Searchable by hash or model name.

### Settings
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/dashboard_settings.png" width="880" alt="Settings Tab" />
</p>

> Configure similarity threshold, TTL, budget alerts, and reset telemetry data.

---

## 🌐 Multi-Provider Support

CostOpt supports wrapping **OpenAI**, **Anthropic**, and **Google Gemini** clients:

```python
# OpenAI
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(OpenAI(), provider="openai")

# Anthropic
import anthropic
from costopt import CostOpt

client = CostOpt(anthropic.Anthropic(), provider="anthropic")

# Google Gemini (via OpenAI-compatible API)
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(
    OpenAI(api_key="...", base_url="https://generativelanguage.googleapis.com/v1beta/openai/"),
    provider="google"
)
```

Supported pricing catalogs: **OpenAI**, **Anthropic**, **Google Gemini**, **HuggingFace**, **Ollama** (local, $0.00).

---

## 📦 Integration with Popular Frameworks

**LangChain:**
```python
from langchain_openai import ChatOpenAI
from costopt import CostOpt
from openai import OpenAI

llm = ChatOpenAI(client=CostOpt(OpenAI()).client)
```

**LlamaIndex:**
```python
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from costopt import CostOpt
from openai import OpenAI

llm = LlamaOpenAI(client=CostOpt(OpenAI()).client)
```

**FastAPI:**
```python
from fastapi import FastAPI
from openai import OpenAI
from costopt import CostOpt

app = FastAPI()
ai_client = CostOpt(OpenAI())
```

---

## 🔧 Configuration & Custom Models

CostOpt reads `costopt.yaml` from your project root for routing rules and fallback chains:

```yaml
routing:
  fallbacks:
    gpt-4o:
      - gpt-4o-mini
      - claude-3-5-haiku
      - llama3
  rules:
    - name: "Simple classification tasks"
      keywords: ["classify", "yes/no", "sentiment", "label", "extract"]
      route_to: "gpt-4o-mini"
    - name: "Code generation"
      keywords: ["write code", "debug", "function", "implement"]
      route_to: "gpt-4o"
```

Add custom or local Ollama models by dropping a `.yaml` into the `pricing/providers/` directory:

```yaml
provider: "ollama"
models:
  llama3:
    input_cost_per_1m: 0.0
    output_cost_per_1m: 0.0
  deepseek-r1:
    input_cost_per_1m: 0.0
    output_cost_per_1m: 0.0
```

---

## 🖥️ VS Code Extension

Install the **CostOpt** extension from the [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=khusshdesai.costopt-vscode) or [Open VSX Registry](https://open-vsx.org/extension/khusshdesai/costopt-vscode).

**Features:**
- 📍 **CodeLens Inlines** — cost per request, avg tokens, call count directly above `client.chat.completions.create()` lines
- 💬 **Hover Panels** — full cost breakdown + MD5 hash + cache status on hover
- 📈 **Sidebar Views** — Spend Forecast, Feature Attribution, Cost Drift Warnings
- 📌 **Status Bar** — `CostOpt: $8.42 today` live in VS Code bottom bar

```bash
# After installing, start the background service:
python -m costopt.main dashboard
```

---

## ❓ FAQ

**Q: Does CostOpt send my prompts or data to external servers?**
> No. 100% local. All telemetry, cache, and pricing data is stored in local SQLite files (`costopt_telemetry.db`, `costopt_cache.db`). Zero data leaves your machine.

**Q: Does it add latency to my LLM calls?**
> No. Prompt hashing and cache checks take under 1ms. Telemetry is written asynchronously in a background thread.

**Q: What does a cache hit cost?**
> `$0.00`. Cached responses are replayed locally in under 2ms without hitting the paid provider API.

**Q: Does it work with LangChain / LlamaIndex?**
> Yes. Pass the wrapped client (`CostOpt(OpenAI()).client`) into any framework that accepts a raw OpenAI client object.

**Q: What if the VS Code status bar shows `CostOpt: Offline`?**
> Start the background service: `python -m costopt.main dashboard`

**Q: How does fuzzy cache matching work?**
> CostOpt uses Jaccard similarity + TF-IDF cosine similarity. Set `similarity_threshold` in Settings to enable near-duplicate matching (e.g. `0.85` = 85% similar prompts return cached response).

**Q: How do I reset all telemetry to start fresh?**
> Click the **RESET TELEMETRY** button in the dashboard header, or run `DELETE FROM telemetry` directly on `costopt_telemetry.db`.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <em>Built for developers who want to ship fast and spend smart. 100% open source.</em>
</p>
