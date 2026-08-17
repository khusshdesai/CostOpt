# Contributing to CostOpt

Thank you for your interest in contributing to **CostOpt**! We welcome contributions from developers of all skill levels.

---

## 🚀 Quickstart for Local Development

1. **Fork & Clone the Repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/CostOpt.git
   cd CostOpt
   ```

2. **Set Up Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies in Editable Mode**:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run Unit Tests**:
   ```bash
   python -m pytest tests/unit/
   ```

---

## 🧩 Architectural Extension Points

CostOpt is built around modular abstractions. Here is where you can contribute new features:

- **Adding Pricing Catalogs**: Drop a new YAML configuration under `pricing/providers/<provider_name>.yaml`.
- **Custom Cache Backends**: Drop-in replacement for `SQLiteCache` in `src/costopt/cache.py` (e.g. Redis, Qdrant) by implementing `get(prompt, model)` and `set(prompt, model, response)` methods.
- **Custom Routing Strategies**: Implement custom complexity rules in `src/costopt/router.py`.
- **Telemetry Exporters**: Add OpenTelemetry or Datadog exporter adapters in `src/costopt/telemetry.py`.

---

## 📜 Pull Request Guidelines

1. Create a feature branch (`git checkout -b feat/my-new-feature`).
2. Ensure all unit tests (`pytest`) pass locally.
3. Keep pull requests focused on a single responsibility.
4. Commit your changes using conventional commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
