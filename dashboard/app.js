// LLM CostOpt — Interactive Control Console Logic

document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "/api";

  // Elements
  const btnRefresh = document.getElementById("btn-refresh");
  const btnClearCache = document.getElementById("btn-clear-cache");
  const btnGenerateSim = document.getElementById("btn-generate-sim");
  
  const valActualCost = document.getElementById("val-actual-cost");
  const valBaselineCost = document.getElementById("val-baseline-cost");
  const valSavings = document.getElementById("val-savings");
  const valSavingsPct = document.getElementById("val-savings-pct");
  const valCacheRate = document.getElementById("val-cache-rate");
  const valCacheHits = document.getElementById("val-cache-hits");
  const valErrorRate = document.getElementById("val-error-rate");
  const valTotalRequests = document.getElementById("val-total-requests");

  const listRecommendations = document.getElementById("recommendations-list");
  const listAnomalies = document.getElementById("anomalies-list");

  // Console Explorer
  const telemetryLogRows = document.getElementById("telemetry-log-rows");
  const configCodeBlock = document.getElementById("config-code-block");

  // Simulator Elements
  const simPrompt = document.getElementById("sim-prompt");
  const simModel = document.getElementById("sim-model");
  const btnRunSim = document.getElementById("btn-run-sim");
  const simTerminal = document.getElementById("sim-terminal");
  const simStatusBadge = document.getElementById("sim-status-badge");
  const simCostOrig = document.getElementById("sim-cost-orig");
  const simCostAct = document.getElementById("sim-cost-act");
  const simSavings = document.getElementById("sim-savings");

  // Chart variables
  let savingsChart = null;

  // Initialize
  refreshDashboard();
  fetchConfig();
  fetchModels();

  // Event Listeners
  if (btnRefresh) btnRefresh.addEventListener("click", refreshDashboard);
  if (btnClearCache) btnClearCache.addEventListener("click", clearCache);
  if (btnGenerateSim) btnGenerateSim.addEventListener("click", injectSimulationData);
  if (btnRunSim) btnRunSim.addEventListener("click", executeSimulation);

  // Tab View Switcher Logic
  const navLinks = document.querySelectorAll(".nav-links a[data-tab]");
  const viewTitle = document.getElementById("view-title");
  const tabViews = document.querySelectorAll(".tab-view");

  const titleMap = {
    dashboard: "System Overview",
    analytics: "Analytics & Performance Metrics",
    costs: "FinOps Cost Breakdown & Savings Analysis",
    traces: "Trace Explorer & Log Audit",
    settings: "System Configuration & Engine Controls"
  };

  navLinks.forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const targetTab = link.getAttribute("data-tab");
      
      navLinks.forEach(l => l.classList.remove("active"));
      link.classList.add("active");

      tabViews.forEach(v => v.classList.add("hidden-tab"));
      const targetView = document.getElementById(`view-${targetTab}`);
      if (targetView) targetView.classList.remove("hidden-tab");

      if (viewTitle && titleMap[targetTab]) {
        viewTitle.textContent = titleMap[targetTab];
      }

      if (targetTab === "traces") {
        updateFullTraceTable();
      }
    });
  });

  // Modal Helper Functions
  const modalOverlay = document.getElementById("modal-overlay");
  const modalTitle = document.getElementById("modal-title");
  const modalBody = document.getElementById("modal-body");
  const modalClose = document.getElementById("modal-close");

  function openModal(title, contentHtml) {
    if (!modalOverlay) return;
    modalTitle.textContent = title;
    modalBody.innerHTML = contentHtml;
    modalOverlay.classList.remove("hidden-modal");
  }

  function closeModal() {
    if (modalOverlay) modalOverlay.classList.add("hidden-modal");
  }

  if (modalClose) modalClose.addEventListener("click", closeModal);
  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) closeModal();
    });
  }

  // Header Button Event Listeners
  const btnDeploySdk = document.getElementById("btn-deploy-sdk");
  if (btnDeploySdk) {
    btnDeploySdk.addEventListener("click", () => {
      openModal("🚀 Deploy CostOpt SDK", `
        <p style="margin-bottom:12px; color:var(--text-secondary);">Install the Python package from PyPI:</p>
        <div class="code-copy-box">
          <code>pip install costopt</code>
          <button class="btn-copy" onclick="navigator.clipboard.writeText('pip install costopt'); this.textContent='Copied!';">Copy</button>
        </div>
        <p style="margin-top:20px; margin-bottom:12px; color:var(--text-secondary);">One-Line Client Interception Wrapper:</p>
        <pre class="fira-code" style="background:var(--bg-terminal); padding:16px; border-radius:8px; border:1px solid var(--border-color); color:var(--text-primary); font-size:0.85rem; overflow-x:auto;">from openai import OpenAI
from costopt import CostOpt

# Wrap client in one line
client = CostOpt(OpenAI(api_key="your-api-key"))

# All completion requests are automatically cached, rerouted & logged!
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello world!"}]
)</pre>
      `);
    });
  }

  const btnNotifications = document.getElementById("btn-notifications");
  if (btnNotifications) {
    btnNotifications.addEventListener("click", () => {
      openModal("🔔 System Notifications & Alerts", `
        <div style="display:flex; flex-direction:column; gap:12px;">
          <div style="background:rgba(16,185,129,0.1); border:1px solid var(--accent-emerald); padding:14px; border-radius:8px;">
            <strong style="color:var(--accent-emerald); display:block; margin-bottom:4px;">[SYSTEM] Lexical Similarity Cache Active</strong>
            <p style="font-size:0.85rem; color:var(--text-secondary);">Cosine vector threshold set to 0.70. Saved 154 requests locally in SQLite database.</p>
          </div>
          <div style="background:rgba(79,70,229,0.1); border:1px solid var(--accent-indigo); padding:14px; border-radius:8px;">
            <strong style="color:var(--accent-indigo); display:block; margin-bottom:4px;">[FINOPS] Cost Reroute Success</strong>
            <p style="font-size:0.85rem; color:var(--text-secondary);">34 requests automatically rerouted from gpt-4o -> gpt-4o-mini, saving $0.2400 USD.</p>
          </div>
        </div>
      `);
    });
  }

  const btnSettingsGear = document.getElementById("btn-settings-gear");
  if (btnSettingsGear) {
    btnSettingsGear.addEventListener("click", () => {
      const settingsTabLink = document.querySelector('.nav-links a[data-tab="settings"]');
      if (settingsTabLink) settingsTabLink.click();
    });
  }

  // Dynamic Logo & Brand Click Handler
  const btnBrandHome = document.getElementById("btn-brand-home");
  const headerLogo = document.getElementById("header-logo");
  if (btnBrandHome) {
    btnBrandHome.addEventListener("click", (e) => {
      e.preventDefault();
      if (headerLogo) {
        headerLogo.style.transform = "rotate(360deg)";
        setTimeout(() => { headerLogo.style.transform = "none"; }, 500);
      }
      const dashboardTabLink = document.querySelector('.nav-links a[data-tab="dashboard"]');
      if (dashboardTabLink) dashboardTabLink.click();
      refreshDashboard();
    });
  }

  const btnProfileAvatar = document.getElementById("btn-profile-avatar");
  if (btnProfileAvatar) {
    btnProfileAvatar.addEventListener("click", () => {
      openModal("👤 Developer Profile & Workspace", `
        <div style="display:flex; align-items:center; gap:16px; margin-bottom:16px;">
          <div style="width:50px; height:50px; border-radius:50%; background:linear-gradient(135deg, var(--accent-indigo), var(--accent-cyan)); display:flex; align-items:center; justify-content:center; font-size:1.5rem;">👨‍💻</div>
          <div>
            <h3 style="color:var(--text-primary);">Khussh Desai</h3>
            <p style="color:var(--text-secondary); font-size:0.85rem;">Workspace: <code class="fira-code" style="color:var(--accent-cyan);">khusshdesai/CostOpt</code></p>
          </div>
        </div>
        <hr style="border:none; border-top:1px solid var(--border-color); margin:16px 0;">
        <p style="margin-bottom:10px;">Environment: <span class="badge-status active">production</span></p>
        <p style="margin-bottom:10px;">Telemetry Engine: <span class="fira-code">SQLite Local Store</span></p>
        <p>GitHub Repository: <a href="https://github.com/khusshdesai/CostOpt" target="_blank" style="color:var(--accent-cyan);">github.com/khusshdesai/CostOpt</a></p>
      `);
    });
  }

  // Live Trace Table Search Filter Handler
  const traceSearch = document.getElementById("trace-search");
  if (traceSearch) {
    traceSearch.addEventListener("input", () => {
      const query = traceSearch.value.toLowerCase().trim();
      const rows = document.querySelectorAll("#full-trace-table-rows tr");
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(query)) {
          row.style.display = "";
        } else {
          row.style.display = "none";
        }
      });
    });
  }

  const btnSettingsClearCache = document.getElementById("btn-settings-clear-cache");
  if (btnSettingsClearCache) btnSettingsClearCache.addEventListener("click", clearCache);

  const btnSettingsClearTelemetry = document.getElementById("btn-settings-clear-telemetry");
  if (btnSettingsClearTelemetry) {
    btnSettingsClearTelemetry.addEventListener("click", () => {
      if (confirm("Are you sure you want to clear telemetry records?")) {
        refreshDashboard();
      }
    });
  }

  async function updateFullTraceTable() {
    const fullTraceTableRows = document.getElementById("full-trace-table-rows");
    if (!fullTraceTableRows) return;

    try {
      const res = await fetch(`${API_BASE}/telemetry/recent`);
      if (!res.ok) return;
      const logs = await res.json();

      fullTraceTableRows.innerHTML = "";
      if (logs.length === 0) {
        fullTraceTableRows.innerHTML = '<tr><td colspan="7" class="text-center muted">No logged traces found in SQLite database.</td></tr>';
        return;
      }

      logs.forEach(log => {
        const row = document.createElement("tr");
        const timeStr = new Date(log.timestamp).toLocaleTimeString();
        row.innerHTML = `
          <td class="muted">${timeStr}</td>
          <td><code class="fira-code">${log.prompt_hash}</code></td>
          <td><code>${log.model_requested}</code></td>
          <td><code>${log.model_used}</code></td>
          <td class="fira-code">${log.latency_ms}ms</td>
          <td class="text-green">$${log.cost_actual.toFixed(4)}</td>
          <td><span class="badge-status ${log.success ? 'active' : 'text-rose'}">${log.status_code || 200}</span></td>
        `;
        fullTraceTableRows.appendChild(row);
      });
    } catch (e) {
      console.error("Error updating full trace table: ", e);
    }
  }

  // Functions
  async function refreshDashboard() {
    console.log("Syncing costopt telemetry analytics...");
    
    listRecommendations.innerHTML = '<div class="loading-state">Evaluating telemetry logs...</div>';
    listAnomalies.innerHTML = '<div class="loading-state">Checking baseline thresholds...</div>';

    try {
      await Promise.all([
        updateOverview(),
        updateSavingsChart(),
        updateRecommendations(),
        updateAnomalies(),
        updateRecentLogs()
      ]);
    } catch (e) {
      console.error("Failed syncing dashboard telemetry: ", e);
    }
  }

  async function fetchConfig() {
    try {
      const res = await fetch(`${API_BASE}/config`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === "success") {
          configCodeBlock.textContent = data.content;
        } else {
          configCodeBlock.textContent = "Error loading costopt.yaml: " + data.message;
        }
      }
    } catch (e) {
      configCodeBlock.textContent = "Error fetching active configurations.";
    }
  }

  async function updateOverview() {
    const res = await fetch(`${API_BASE}/overview`);
    if (!res.ok) throw new Error("Overview query failed");
    const data = await res.json();

    valActualCost.textContent = `$${data.cost_actual.toFixed(4)}`;
    valBaselineCost.textContent = `$${data.cost_baseline.toFixed(4)}`;
    valSavings.textContent = `$${data.total_savings.toFixed(4)}`;
    valCacheRate.textContent = `${data.cache_hit_rate.toFixed(1)}%`;
    if (valErrorRate) valErrorRate.textContent = `${data.error_rate.toFixed(1)}%`;
    if (valTotalRequests) valTotalRequests.textContent = data.total_requests.toLocaleString();

    const base = data.cost_baseline;
    const savingsPct = base > 0 ? (data.total_savings / base) * 100 : 0.0;
    valSavingsPct.textContent = `${savingsPct.toFixed(1)}%`;

    const hits = Math.round(data.total_requests * (data.cache_hit_rate / 100));
    if (valCacheHits) valCacheHits.textContent = hits.toLocaleString();
  }

  async function updateSavingsChart() {
    const res = await fetch(`${API_BASE}/charts/savings`);
    if (!res.ok) return;
    const data = await res.json();

    const dates = data.map(item => item.date);
    const baselineCosts = data.map(item => item.baseline_cost);
    const actualCosts = data.map(item => item.actual_cost);
    const savings = data.map(item => item.savings);

    const ctx = document.getElementById("savingsChart").getContext("2d");
    
    if (savingsChart) {
      savingsChart.destroy();
    }

    savingsChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: dates,
        datasets: [
          {
            label: "Baseline Spend",
            data: baselineCosts,
            borderColor: "rgba(148, 163, 184, 0.4)",
            borderWidth: 2,
            borderDash: [4, 4],
            fill: false,
            tension: 0.2
          },
          {
            label: "Actual Spend",
            data: actualCosts,
            borderColor: "#6366F1",
            backgroundColor: "rgba(99, 102, 241, 0.03)",
            borderWidth: 2.5,
            fill: true,
            tension: 0.2
          },
          {
            label: "Cost Savings",
            data: savings,
            borderColor: "#10B981",
            backgroundColor: "rgba(16, 185, 129, 0.03)",
            borderWidth: 2,
            fill: true,
            tension: 0.2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: "#E2E8F0",
              font: { family: "Inter", size: 10 }
            }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.02)" },
            ticks: { color: "#64748B", font: { size: 9 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.02)" },
            ticks: { color: "#64748B", font: { size: 9 } }
          }
        }
      }
    });
  }

  function formatTimestamp(ts) {
    if (!ts) return new Date().toLocaleTimeString();
    const isoTs = ts.toString().replace(" ", "T");
    const d = new Date(isoTs);
    if (isNaN(d.getTime())) return new Date().toLocaleTimeString();
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function formatConfidence(conf) {
    if (!conf) return "High Priority";
    const clean = conf.toString().replace(/_/g, " ").toLowerCase();
    const titleCase = clean.split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
    return `${titleCase}`;
  }

  async function updateRecentLogs() {
    const res = await fetch(`${API_BASE}/telemetry/recent`);
    if (!res.ok) return;
    const logs = await res.json();

    telemetryLogRows.innerHTML = "";
    if (logs.length === 0) {
      telemetryLogRows.innerHTML = '<tr><td colspan="7" class="text-center muted">No logged events found in SQLite.</td></tr>';
      return;
    }

    logs.forEach(log => {
      const row = document.createElement("tr");
      
      let statusBadge = "";
      if (log.cache_hit) {
        statusBadge = '<span class="log-badge badge-hit">CACHE HIT</span>';
      } else if (log.model_requested !== log.model_used) {
        statusBadge = '<span class="log-badge badge-route">ROUTED</span>';
      } else {
        statusBadge = '<span class="log-badge badge-direct">DIRECT</span>';
      }

      const timeStr = formatTimestamp(log.timestamp);

      row.innerHTML = `
        <td class="muted">${timeStr}</td>
        <td><code>${log.prompt_hash}</code></td>
        <td><code>${log.model_requested}</code></td>
        <td><code>${log.model_used}</code></td>
        <td class="muted">$${log.cost_original.toFixed(4)} / $${log.cost_actual.toFixed(4)}</td>
        <td class="text-green">${log.savings > 0 ? '+$' + log.savings.toFixed(4) : '-'}</td>
        <td>${statusBadge}</td>
      `;
      telemetryLogRows.appendChild(row);
    });
  }

  async function updateRecommendations() {
    const res = await fetch(`${API_BASE}/recommendations`);
    if (!res.ok) return;
    const recommendations = await res.json();

    listRecommendations.innerHTML = "";

    if (recommendations.length === 0) {
      listRecommendations.innerHTML = `
        <div class="loading-state">
          All optimization strategies active. Excellent system cost health!
        </div>
      `;
      return;
    }

    recommendations.forEach(reco => {
      const item = document.createElement("div");
      item.className = "reco-item";
      const confRaw = reco.confidence || "HIGH";
      const confidenceClass = `confidence-${confRaw.toLowerCase().replace(/_/g, "-")}`;
      const confLabel = formatConfidence(confRaw);
      
      item.innerHTML = `
        <div class="reco-header">
          <span class="reco-title">${reco.title}</span>
          <span class="reco-savings">+$${reco.estimated_savings.toFixed(3)}/mo</span>
        </div>
        <p class="reco-desc">${reco.description}</p>
        <div class="reco-footer">
          <span class="reco-evidence">${reco.evidence}</span>
          <span class="badge-confidence ${confidenceClass}">${confLabel}</span>
        </div>
      `;
      listRecommendations.appendChild(item);
    });
  }

  async function updateAnomalies() {
    const res = await fetch(`${API_BASE}/anomalies`);
    if (!res.ok) return;
    const anomalies = await res.json();

    listAnomalies.innerHTML = "";

    if (anomalies.length === 0) {
      listAnomalies.innerHTML = `
        <div class="loading-state">
          No cost anomalies detected. Telemetry spend is within normal bounds.
        </div>
      `;
      return;
    }

    anomalies.forEach(anom => {
      const item = document.createElement("div");
      item.className = "anomaly-item";
      
      item.innerHTML = `
        <div class="anomaly-meta">
          <h4>Cost spike on ${anom.date}</h4>
          <p>${anom.request_count} runs. Expected: $${anom.expected_mean.toFixed(3)}</p>
        </div>
        <div class="anomaly-data">
          <div class="anomaly-cost">$${anom.actual_cost.toFixed(3)}</div>
          <div class="anomaly-zscore">Z-Score: +${anom.z_score.toFixed(1)}</div>
        </div>
      `;
      listAnomalies.appendChild(item);
    });
  }

  async function clearCache() {
    if (!confirm("Are you sure you want to flush all cached LLM responses?")) return;
    try {
      const res = await fetch(`${API_BASE}/cache/clear`, { method: "POST" });
      const data = await res.json();
      alert(data.message);
      refreshDashboard();
    } catch (e) {
      alert("Error clearing cache: " + e);
    }
  }

  async function injectSimulationData() {
    try {
      const res = await fetch(`${API_BASE}/telemetry/generate`, { method: "POST" });
      const data = await res.json();
      refreshDashboard();
    } catch (e) {
      alert("Failed to inject simulation data: " + e);
    }
  }

  // SDK Simulator execution with custom typewriter logs
  async function executeSimulation() {
    const prompt = simPrompt.value.strip ? simPrompt.value.strip() : simPrompt.value.trim();
    const model = simModel.value;

    if (!prompt) {
      alert("Please enter a mock prompt for the simulator.");
      return;
    }

    // Toggle active state
    simStatusBadge.textContent = "INTERCEPTING";
    simStatusBadge.className = "badge-status active";
    simTerminal.innerHTML = '<div class="terminal-line">// Interceptor client wrapping active...</div>';

    // Simulated step timings to match real trace logging visual feel
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
    
    await sleep(250);
    const line2 = document.createElement("div");
    line2.className = "terminal-line";
    line2.textContent = `> Intercepting ChatCompletion call for model='${model}'...`;
    simTerminal.appendChild(line2);
    simTerminal.scrollTop = simTerminal.scrollHeight;

    await sleep(350);
    const line3 = document.createElement("div");
    line3.className = "terminal-line";
    line3.textContent = `> Step 1: Computing MD5 hash and checking local SQLite cache...`;
    simTerminal.appendChild(line3);
    simTerminal.scrollTop = simTerminal.scrollHeight;

    // Run backend request
    try {
      const response = await fetch(`${API_BASE}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, model })
      });

      if (!response.ok) throw new Error("Simulation endpoint failed");
      const data = await response.json();

      await sleep(400);
      
      // Print backend outputs sequentially
      data.logs.slice(2).forEach(logLine => {
        const trace = document.createElement("div");
        trace.className = "terminal-line";
        if (logLine.includes("HIT")) {
          trace.className = "terminal-line success";
        } else if (logLine.includes("match!")) {
          trace.className = "terminal-line warning";
        }
        trace.textContent = `> ${logLine}`;
        simTerminal.appendChild(trace);
      });

      const lineEnd = document.createElement("div");
      lineEnd.className = "terminal-line muted";
      lineEnd.textContent = `> Interception complete. Returning completion object.`;
      simTerminal.appendChild(lineEnd);
      simTerminal.scrollTop = simTerminal.scrollHeight;

      // Update simulator cost metrics
      simCostOrig.textContent = `$${data.cost_original.toFixed(4)}`;
      simCostAct.textContent = `$${data.cost_actual.toFixed(4)}`;
      simSavings.textContent = `$${data.savings.toFixed(4)}`;

      // Update general observability elements
      refreshDashboard();

    } catch (e) {
      const errLine = document.createElement("div");
      errLine.className = "terminal-line text-rose";
      errLine.textContent = `> Error executing interception pipeline: ${e.message}`;
      simTerminal.appendChild(errLine);
    } finally {
      simStatusBadge.textContent = "COMPLETED";
      simStatusBadge.className = "badge-status";
    }
  }

  async function fetchModels() {
    try {
      const res = await fetch(`${API_BASE}/models`);
      if (res.ok) {
        const models = await res.json();
        if (simModel) {
          simModel.innerHTML = "";
          models.forEach(m => {
            const opt = document.createElement("option");
            // Set value to target model name
            opt.value = m.model;
            opt.textContent = `${m.model} (${m.provider})`;
            simModel.appendChild(opt);
          });
        }
      }
    } catch (e) {
      console.error("Failed loading model registry: ", e);
    }
  }
});
