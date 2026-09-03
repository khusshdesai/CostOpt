<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/costopt_logo.png" width="120" alt="CostOpt Logo" />
</p>

<h1 align="center">CostOpt — Developer-Native LLM Cost Intelligence ⚡</h1>

<p align="center">
  <strong>Drop-in wrapper for OpenAI, Anthropic & Gemini clients that adds automatic caching, smart model routing, circuit breaker protection, and a real-time observability dashboard — all 100% local.</strong><br>
  <em>Stop waiting for a $500 monthly cloud bill to figure out where your LLM budget went.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/costopt/"><img src="https://img.shields.io/badge/pypi-v0.1.9-blue" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/costopt/"><img src="https://img.shields.io/badge/downloads-2K%2B-brightgreen" alt="Downloads"></a>
  <a href="https://open-vsx.org/extension/khusshdesai/costopt-vscode"><img src="https://img.shields.io/badge/Open%20VSX-2K%2B%20installs-purple" alt="Open VSX Installs"></a>
  <a href="https://marketplace.visualstudio.com/items?itemName=khusshdesai.costopt-vscode"><img src="https://img.shields.io/badge/VS%20Marketplace-v0.2.6-blue" alt="VS Marketplace"></a>
  <a href="https://github.com/khusshdesai/CostOpt/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-brightgreen" alt="License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9%2B-blue" alt="Python"></a>
  <a href="https://marketplace.visualstudio.com/items?itemName=khusshdesai.costopt-vscode"><img src="https://img.shields.io/badge/VS%20Code-1.80%2B-purple" alt="VS Code"></a>
</p>

---

## ⚡ Overview

### The Problem
Generative AI applications frequently overspend by:
1. **Executing Duplicate Requests**: Re-querying upstream APIs for exact or near-identical prompts.
2. **Over-provisioning Models**: Routing simple classification, extraction, or short summarization queries to expensive flagship models (e.g., `gpt-4o`, `claude-3-5-sonnet`) when lower-cost models (`gpt-4o-mini`, `claude-3-haiku`, `llama3`, `deepseek-r1`) satisfy accuracy requirements.
3. **Lack of Cost Visibility**: Difficulty tracking net savings, model breakdown, or request-level optimization decisions.

### The CostOpt Solution
CostOpt acts as a transparent, drop-in SDK interceptor and decision engine that:
- Serves prompt hits locally in **<15ms at $0.00 cost** via an SQLite prompt cache.
- Analyzes request intent and complexity to automatically route simple tasks to cost-effective models.
- Enforces quality guardrails and automatic outage failovers.
- Records unified FinOps telemetry displayed on a real-time web console.

---

## 🔌 1-Line Zero-Churn Integration

```python
# ─── BEFORE (Standard OpenAI Client) ────────────────────────────────────────
from openai import OpenAI
client = OpenAI()

# ─── AFTER (With CostOpt — zero other changes needed) ───────────────────────
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(OpenAI())  # 👈 Intercepts transparently

# Your API calls are 100% identical — CostOpt automatically analyzes, caches, & routes:
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Classify customer feedback: Great product!"}]
)
print(response.choices[0].message.content)
```

---

## ⚡ Core Features

| Feature | Description |
|---|---|
| 🗄️ **Multi-Tier Prompt Cache** | Tier 1 exact MD5 hash matching (<15ms, $0.00) + Tier 2 local TF-IDF cosine vector similarity matching. Includes parameter hashing (`temperature`, `tools`, `response_format`, `seed`). |
| 🧠 **Intelligent Decision Engine** | Classifies prompts into 7 task categories (`simple_classification`, `extraction`, `summarization`, `coding`, `reasoning`, `creative_generation`, `general_chat`) with confidence scoring. |
| 🔀 **Policy-Aware Model Router** | Rule-based keyword and task-complexity routing — simple tasks auto-rerouted to efficient models (`gpt-4o` ➔ `gpt-4o-mini` / `deepseek-r1`). |
| 🛡️ **Circuit Breaker** | Detects call velocity loops from the same file/line location and trips `CostOptCircuitBreakerError`. |
| 🔄 **Outage Failover** | Auto-retries fallback models on 429/503 errors (`gpt-4o` ➔ `claude-3-5-sonnet` ➔ `llama3`). |
| 📊 **Observability & FinOps Console** | Premium dark-mode dashboard (`#050505` canvas, fixed left sidebar, bento grid layout) for Overview, Spend, Optimizations, Requests, and Policies. |
| 🔍 **Decision Intelligence Traces** | Step-by-step visual trace flow explaining every request analysis, cache evaluation, and routing decision. |
| 🖥️ **VS Code Extension** | Inline CodeLens cost per request, call counts, hover panels, and status bar metrics directly inside VS Code. |
| 🔒 **100% Local & Private** | Stored in local SQLite (`costopt_telemetry.db`, `costopt_cache.db`). Zero data leaves your machine. |

---

## 🏗️ Architecture

```mermaid
flowchart TD
    App["Calling Application"] -->|ChatCompletion.create| Interceptor["CostOpt SDK Client Interceptor"]
    Interceptor --> CB["Circuit Breaker Check"]
    CB --> Engine["Centralized Decision Engine"]
    
    subgraph Engine ["Intelligent Decision Pipeline"]
        Analyzer["1. Request Analyzer<br/>Task & Complexity Classification"]
        CacheLayer["2. Semantic Cache Layer<br/>Tier 1: MD5 Exact - Tier 2: TF-IDF Cosine"]
        Registry["3. Model Capability Registry<br/>Capability Scores & Token Pricing"]
        Guardrails["4. Fallback & Quality Guardrails<br/>Confidence & Outage Failover"]
        Estimator["5. Cost Estimator<br/>Baseline vs Target Cost Delta"]
    end
    
    CacheLayer -->|Cache HIT <15ms| Hit["Return Local Response $0.00"]
    CacheLayer -->|Cache MISS| Registry
    Registry --> Guardrails
    Guardrails -->|Decision: REROUTE / DIRECT| API["Upstream LLM API"]
    API -->|Outage 429/500| Failover["Failover Secondary Model"]
    
    Hit --> DB[("SQLite Telemetry & Cache DB")]
    API --> DB
    Failover --> DB
    
    DB --> Dashboard["CostOpt FinOps Dashboard<br/>http://127.0.0.1:8000"]
```

---

## 🚦 Optimization Decision Flow

Every request is evaluated by the centralized `DecisionEngine` and assigned one of four execution outcomes:

| Decision | Condition | Execution Path |
| :--- | :--- | :--- |
| **`CACHE`** | Prompt matches an existing exact or semantic entry in `costopt_cache.db`. | Returned locally in <15ms ($0.00 cost). |
| **`REROUTE`** | Cache miss; task is low/medium complexity, confidence >= 0.70, and a cheaper capable model exists. | Routed to cost-effective target model (e.g., `gpt-4o` ➔ `gpt-4o-mini`). |
| **`DIRECT`** | Cache miss; high-complexity reasoning/coding task or low confidence (<0.70). | Executed using original requested model for maximum accuracy. |
| **`FALLBACK`** | Primary model endpoint fails or circuit breaker indicates outage. | Auto-failed over to secondary fallback model. |

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
    messages=[{"role": "user", "content": "Classify sentiment: This product is outstanding!"}]
)
print(response.choices[0].message.content)
```

### Step 3 — Launch the Observability Dashboard
```bash
costopt dashboard
# Or run via Python module:
python -m costopt.main dashboard
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 📊 Observability Dashboard

The web console features a modern dark-mode aesthetic (`#050505` canvas, translucent borders, ambient glows, fixed left sidebar shell, and bento grid layout) across 5 primary navigation tabs:

### 1. Overview
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/v2_overview.png" width="880" alt="Dashboard Overview" />
</p>

> Net Financial Impact Hero Glass Card (`$0.0093` / dynamic savings), smooth spend trend area chart, bento metrics grid (Actual Spend, Efficiency Gain, Opportunities, System Health), top recommendation card, and live telemetry feed.

### 2. Spend Analytics
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/v2_spend.png" width="880" alt="Spend Tab" />
</p>

> Actual LLM spend hero card with baseline comparison, spend by model/provider bento distribution cards, and sortable model cost breakdown table.

### 3. Optimizations Engine
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/v2_optimizations.png" width="880" alt="Optimizations Tab" />
</p>

> Active optimization strategy status cards (Local SQLite Cache, Rule-Based Model Rerouting), total net savings per strategy, and real-time optimization decision activity log.

### 4. Requests Explorer & Decision Intelligence Trace
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/v2_traces.png" width="880" alt="Request Inspection Trace Modal" />
</p>

> Request explorer transaction log table with prompt search, outcome filter badges (`CACHE HIT`, `REROUTE`, `DIRECT`), and **Request Inspection Drawer** displaying step-by-step **Decision Intelligence Traces**.

### 5. Policies Configuration
<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/v2_policies.png" width="880" alt="Policies Tab" />
</p>

> Active policy rules visual cards (`Requested Model ➔ Target Model`), model routing map, live `costopt.yaml` policy editor with unsaved state detection, save/revert options, and cache/telemetry management.

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

## 🔧 Configuration & Policy Rules

Control model routing policies and fallback chains in `costopt.yaml`:

```yaml
routing:
  rules:
    - name: "Simple text classification"
      keywords: ["classify", "sentiment", "yes/no", "label"]
      max_prompt_length: 500
      original_model: "gpt-4o"
      target_model: "gpt-4o-mini"

  fallbacks:
    gpt-4o:
      - "claude-3-5-sonnet"
      - "gpt-4o-mini"
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

---

## 🧪 Testing

Run the automated Pytest test suite:

```bash
python -m pytest tests/ -v
```

**Test Status**: All 18 test cases pass cleanly (100% pass rate).

---

## ❓ FAQ

**Q: Does CostOpt send my prompts or data to external servers?**
> No. 100% local. All telemetry, cache, and pricing data is stored in local SQLite files (`costopt_telemetry.db`, `costopt_cache.db`). Zero data leaves your machine.

**Q: Does it add latency to my LLM calls?**
> No. Prompt hashing and cache checks take under 1ms. Telemetry is written asynchronously in a background thread.

**Q: What does a cache hit cost?**
> `$0.00`. Cached responses are replayed locally in under 15ms without hitting paid provider APIs.

**Q: Does it work with LangChain / LlamaIndex / FastAPI?**
> Yes. Pass the wrapped client (`CostOpt(OpenAI()).client`) into any framework that accepts a raw OpenAI client object.

**Q: How does fuzzy/semantic cache matching work?**
> CostOpt uses TF-IDF word and character n-gram cosine vector similarity. Set `similarity_threshold` in `costopt.yaml` to enable near-duplicate matching (e.g., `0.90` = 90% similar prompts return cached response).

**Q: How do I reset all telemetry to start fresh?**
> Click **Reset Telemetry Analytics** on the Policies tab in the dashboard console.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <em>Built for developers who want to ship fast and spend smart. 100% open source.</em>
</p>
