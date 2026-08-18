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

### 3. 📊 Activity Bar Sidebar Views
Access native tree views in the VS Code sidebar:
- 📈 **Spend Forecast**: Monthly budget run rate & projected spend.
- 🏷️ **Feature Attribution**: Spend broken down by feature (`feature="rag_summarizer"`).
- ⚠️ **Cost Drift Warnings**: Real-time alerts for budget overruns or runaway loops.

### 4. 📌 Status Bar Widget
Displays your current daily spend directly in the bottom status bar (`CostOpt: $8.42 today`).

### 5. 🚨 Problems Panel Integration
Pushes budget overrun warnings and infinite loop trip alerts directly into the VS Code Problems tab.

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

# Wrap standard client (Zero refactoring required!)
client = CostOpt(OpenAI())

# Calls are automatically tracked, cached ($0.00 cost on hits), and guarded!
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum computing simply"}],
    feature="customer_support"  # Optional feature tagging!
)
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

**Q: Does CostOpt send my prompt data to external servers?**  
*No. CostOpt is 100% local. All telemetry, vector caching, and pricing logic run strictly on your local machine using SQLite.*

**Q: What if the status bar says `CostOpt: Offline`?**  
*Run `costopt dashboard` in your terminal to start the local service.*

---

## 📄 License
Licensed under the [MIT License](https://github.com/khusshdesai/CostOpt/blob/main/LICENSE).
