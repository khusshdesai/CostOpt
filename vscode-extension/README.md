# CostOpt — Cost Intelligence While You Code ⚡

<p align="center">
  <img src="https://raw.githubusercontent.com/khusshdesai/CostOpt/main/docs/images/costopt_logo.png" width="120" alt="CostOpt Logo" />
</p>

> **Developer-native LLM cost intelligence directly inside VS Code.**
> Stop waiting for a $500 monthly cloud bill. CostOpt puts real-time LLM cost metrics, feature-level spend attribution, and runaway billing circuit breakers into your local editor loop.

---

## ✨ Features

### 1. Live CodeLens Cost Inlines
See real-time cost, token count, and call volume directly above your `client.chat.completions.create()` lines:
```python
# CostOpt: ~$0.012 / request | Avg tokens: 3,421 | Calls: 184
response = client.chat.completions.create(model="gpt-4o", messages=...)
```

### 2. Rich Hover Intelligence
Hover over any LLM call to inspect a compact cost breakdown, prompt MD5 hash, and average response latency.

### 3. Native Sidebar Tree View
Audits your project's spend directly from the VS Code Activity Bar:
- 📊 **Monthly Spend Forecast**: Real-time run rate vs budget limits.
- 🏷️ **Feature Attribution**: Spend grouped by feature tag (`feature="rag_summarizer"`).
- ⚠️ **Cost Drift Warnings**: Active alerts for budget overruns or cache under-utilization.

### 4. Status Bar Spend Widget
Displays your current daily spend directly in the VS Code status bar (`CostOpt: $8.42 today`).

### 5. Problems Panel Diagnostics
Pushes budget overruns and runaway loop warnings directly into the VS Code Problems panel.

---

## 🚀 Quickstart

1. **Install CostOpt Python SDK**:
   ```bash
   pip install costopt
   ```

2. **Wrap your client in 1 line**:
   ```python
   from openai import OpenAI
   from costopt import CostOpt

   client = CostOpt(OpenAI())
   ```

3. **Start the local service**:
   ```bash
   costopt dashboard
   ```

---

## 📄 License
Licensed under the [MIT License](https://github.com/khusshdesai/CostOpt/blob/main/LICENSE).
