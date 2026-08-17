<p align="center">
  <br />
  <img src="docs/images/costopt_logo.png" width="140" alt="CostOpt Logo Badge" />
  <br />
  <br />
  <p align="center">
    <strong>Drop-in LLM API cost optimization SDK & local developer observability platform.</strong>
    <br />
    Stop paying for redundant LLM calls. Intercept, route, cache, and optimize prompt spend <em>before</em> requests hit paid APIs.
  </p>
</p>

<p align="center">
  <a href="https://github.com/khusshdesai/CostOpt/actions"><img src="https://img.shields.io/badge/build-passing-brightgreen.svg?style=flat-square" alt="Build Status"></a>
  <a href="https://github.com/khusshdesai/CostOpt/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License"></a>
  <a href="https://pypi.org/project/costopt/"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg?style=flat-square" alt="Python Versions"></a>
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square" alt="Code Style"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/OpenAI-supported-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Anthropic-supported-D97706?style=for-the-badge&logo=anthropic&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Gemini-supported-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/Hugging_Face-supported-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" />
  <img src="https://img.shields.io/badge/Ollama_(Local)-supported-000000?style=for-the-badge&logo=ollama&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-supported-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
</p>

---

## 📌 Key Capabilities

- **Zero-Churn 1-Line SDK Interception**: Drop-in wrapper patches standard completion clients (`client = CostOpt(OpenAI())`) with zero modifications to existing calling code.
- **Automated Cost Optimization**: Intelligent intent detection automatically routes lightweight queries (like sentiment or text formatting) from expensive models (`gpt-4o`) to low-cost models (`gpt-4o-mini` or local `llama3`), preserving response quality while cutting spend.
- **Lexical Similarity Cache**: High-speed token & character n-gram similarity cache returns **sub-2ms latency, $0.00 cost** on repeated or similar prompts.
- **Local & Offline Model Support**: Seamlessly route to local **Ollama** models (`llama3`, `mistral`, `deepseek-r1`, `qwen2.5`) for 100% free offline execution.
- **100% Private Local Telemetry**: Logs financial metrics, latency distributions, and MD5 trace hashes to a local SQLite database—zero data shared with third-party servers.

---

## 🖥️ Developer Observability Console

<p align="center">
  <img src="docs/images/dashboard_overview.png" width="100%" alt="CostOpt Developer Observability Console" />
</p>

<p align="center">
  <em>Live System Overview displaying spend metrics, vector cache hits, optimization recommendations, and prompt interception logs.</em>
</p>

<br />

<p align="center">
  <img src="docs/images/trace_explorer.png" width="100%" alt="Full-Screen Trace Explorer" />
</p>

<p align="center">
  <em>Dedicated Trace Explorer auditing prompt MD5 hashes, response latencies, model rerouting decisions, and status code badges.</em>
</p>

## 🏗️ Architecture & Request Flow

```mermaid
graph TD
    App["💻 Application Code"] -->|client.chat.completions.create| Interceptor["⚡ CostOpt Middleware"]
    
    Interceptor -->|1. Vector Cosine Lookup| Cache{"💾 SQLite Vector Cache"}
    Cache -->|Cache HIT 0ms / $0.0| App
    
    Cache -->|Cache MISS| Router{"🧠 Complexity Router"}
    Router -->|Simple Query| MiniModel["🚀 Mini / Local Ollama ($0.0)"]
    Router -->|Complex Query| OriginalModel["🌐 Cloud Provider API ($$$)"]
    
    MiniModel --> Telemetry["📊 Local SQLite Telemetry Logger"]
    OriginalModel --> Telemetry
    Telemetry --> Dashboard["🖥️ Local Observability Dashboard (Port 8000)"]
```

---

## 🚀 Quickstart

### 1. Installation

```bash
pip install costopt
```

### 2. Basic Integration

```python
from openai import OpenAI
from costopt import CostOpt

# Wrap standard client in one line
client = CostOpt(OpenAI(api_key="your-api-key"))

# Requests are automatically intercepted, cached, and optimized!
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Classify sentiment: I love python!"}]
)
```

### 3. Launch Observability Dashboard

```bash
costopt dashboard
```

Open **`http://localhost:8000`** in your browser to view real-time spend analytics, trace logs, and policy rules!

### 4. Integration with Popular Frameworks

CostOpt wraps standard OpenAI-compatible client instances in 1 line:

**LangChain**:
```python
from langchain_openai import ChatOpenAI
from costopt import CostOpt

# Wrap underlying client
llm = ChatOpenAI(client=CostOpt(OpenAI()).client)
```

**LlamaIndex**:
```python
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from costopt import CostOpt

llm = LlamaOpenAI(client=CostOpt(OpenAI()).client)
```

**FastAPI Middleware Integration**:
```python
from fastapi import FastAPI
from openai import OpenAI
from costopt import CostOpt

app = FastAPI()
ai_client = CostOpt(OpenAI())
```

---

## 🔧 Configuration Guide

### Custom Models & User Local Overrides

Track custom, fine-tuned, or local models by dropping a `.yaml` file into your project:

```yaml
provider: "ollama"
models:
  deepseek-r1:
    input_cost_per_1m: 0.0
    output_cost_per_1m: 0.0
```

Pass the pricing directory:

```python
client = CostOpt(OpenAI(), pricing_dir="./my_pricing")
```

---

## 🛡️ Security Audit

CostOpt has undergone automated penetration testing for SQL injections, CORS misconfigurations, and rate-limiting DB locks. See the full audit report at [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md).

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
