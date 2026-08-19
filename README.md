# CostOpt — Developer-Native LLM Cost Intelligence & Optimization ⚡

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/costopt_logo.png" width="140" alt="CostOpt Logo" />
</p>

<p align="center">
  <strong>Developer-native LLM cost intelligence, local response caching, circuit breaker protection, and observability directly in VS Code.</strong>
  <br />
  Stop waiting for a $500 monthly cloud bill to figure out where your LLM budget went.
</p>

<p align="center">
  <a href="https://pypi.org/project/costopt/"><img src="https://img.shields.io/pypi/v/costopt?color=blue&style=flat-square" alt="PyPI"></a>
  <a href="https://github.com/khusshdesai/CostOpt/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/VS%20Code-1.80%2B-purple.svg?style=flat-square" alt="VS Code Version">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/costopt_dashboard.png" width="900" alt="CostOpt Dashboard Console" />
</p>

---

## 🔌 1-Line Zero-Churn Integration

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

## ⚡ Core Features

- **🔍 Live CodeLens Cost Inlines**: Real-time cost per request, average tokens, and call counts directly above your Python code lines.
- **💬 Rich Hover Panels**: Instant cost breakdown, MD5 prompt hash, vector cache hit status, and response latency when hovering over LLM calls.
- **🛡️ Silent Infinite Loop Circuit Breaker**: Detects rapid call loops (>15 calls in 30s) and trips a local exception before burning your API key.
- **🔄 Zero-Downtime Outage Failover (429/503)**: Reroutes queries to configured fallback models (`gpt-4o` → `claude-3-5-sonnet` or local `ollama/llama3`) on rate limits or outages.
- **📊 Native VS Code Sidebar Views**: Spend forecast, feature attribution (`feature="rag_summarizer"`), and cost drift warnings in the VS Code Activity Bar.
- **📌 Status Bar Widget**: Compact daily spend tracker (`CostOpt: $8.42 today`) in the status bar.
- **🔒 100% Local & Private**: Telemetry, vector embeddings, and pricing catalogs run strictly on your local PC via SQLite.

---

## 🚀 Quickstart Guide

### 1. Install Python SDK
```bash
pip install costopt
```

### 2. Wrap your OpenAI Client
```python
from openai import OpenAI
from costopt import CostOpt

client = CostOpt(OpenAI())

# Make requests as usual
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum mechanics"}],
    feature="customer_support"
)
```

### 3. Launch Observability Dashboard
```bash
costopt dashboard
```
Open **`http://localhost:8000`** in your browser to view real-time spend analytics, trace logs, and policy rules!

---

## 📦 Integration with Popular Frameworks

**LangChain**:
```python
from langchain_openai import ChatOpenAI
from costopt import CostOpt
from openai import OpenAI

llm = ChatOpenAI(client=CostOpt(OpenAI()).client)
```

**LlamaIndex**:
```python
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from costopt import CostOpt
from openai import OpenAI

llm = LlamaOpenAI(client=CostOpt(OpenAI()).client)
```

**FastAPI Middleware**:
```python
from fastapi import FastAPI
from openai import OpenAI
from costopt import CostOpt

app = FastAPI()
ai_client = CostOpt(OpenAI())
```

---

## 🔧 Configuration & Custom Models

Track custom, fine-tuned, or local Ollama models by dropping a `.yaml` file into your project:

```yaml
provider: "ollama"
models:
  deepseek-r1:
    input_cost_per_1m: 0.0
    output_cost_per_1m: 0.0
```

---

## ❓ Frequently Asked Questions (FAQ)

**Q: Does CostOpt send my prompt data or code to external servers?**  
*No. CostOpt is 100% private and runs locally on your PC. All telemetry logs, similarity vectors, and pricing catalogs are stored locally in SQLite database files (`costopt_telemetry.db`, `costopt_cache.db`). Zero data leaves your machine.*

**Q: Does wrapping my client add latency overhead to my LLM calls?**  
*No. CostOpt computes prompt hashes and cache checks in under 1ms. Telemetry records are written asynchronously in a non-blocking background worker thread.*

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

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
