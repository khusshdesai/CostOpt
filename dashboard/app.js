/**
 * CostOpt Enterprise FinOps Console — App Logic (All 5 Phases Completed)
 */

let overviewChart = null;
let spendTimeChart = null;
let currentSortColumn = 'spend';
let currentSortDirection = 'desc';
let lastModelData = [];

let currentRequestSearch = '';
let currentRequestOutcome = 'all';

let initialYamlConfig = '';

/**
 * Shared Adaptive Currency Formatter
 * Rules:
 * value >= 0.01  -> 2 decimal places (e.g. $1.24, $1,240.00)
 * value >= 0.001 -> 4 decimal places (e.g. $0.0023)
 * value < 0.001  -> 4 decimal places (e.g. $0.0001)
 */
function formatCurrency(val) {
  if (val === undefined || val === null || isNaN(val)) return '$0.00';
  const num = Number(val);
  const abs = Math.abs(num);
  if (abs === 0) return '$0.00';
  if (abs >= 0.01) {
    return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (abs >= 0.001) {
    return '$' + num.toFixed(4);
  }
  return '$' + num.toFixed(4);
}

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initRefreshButton();
  initSortableHeaders();
  initRequestFilters();
  initPolicyEditor();
  initDestructiveActions();
  
  // Load Phase 1 Overview Data by default
  loadOverviewData();
});

/**
 * 1. Tab Router Handler
 */
function initTabs() {
  const navItems = document.querySelectorAll('.nav-item');
  const tabPanels = document.querySelectorAll('.tab-panel');
  const titleHeading = document.getElementById('page-title-heading');
  const subtitleText = document.getElementById('page-subtitle-text');

  const headers = {
    overview: { title: 'Optimization Overview', sub: 'Monitor your LLM spend, savings, and optimization decision activity' },
    spend: { title: 'Spend Analytics', sub: 'Financial usage breakdown across models and provider endpoints' },
    optimizations: { title: 'Optimization Engine', sub: 'Decision strategy breakdown and real-time optimization audit log' },
    requests: { title: 'Requests Explorer', sub: 'Full transaction log, search, filters, and decision intelligence traces' },
    policies: { title: 'Policy Configuration', sub: 'Configure cost optimization routing rules and model fallbacks' }
  };

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetTab = item.getAttribute('data-tab');

      navItems.forEach(nav => nav.classList.remove('active'));
      tabPanels.forEach(panel => panel.classList.remove('active'));

      item.classList.add('active');
      const targetPanel = document.getElementById(`view-${targetTab}`);
      if (targetPanel) {
        targetPanel.classList.add('active');
      }

      if (headers[targetTab]) {
        if (titleHeading) titleHeading.textContent = headers[targetTab].title;
        if (subtitleText) subtitleText.textContent = headers[targetTab].sub;
      }

      if (targetTab === 'overview') {
        loadOverviewData();
      } else if (targetTab === 'spend') {
        loadSpendData();
      } else if (targetTab === 'optimizations') {
        loadOptimizationsData();
      } else if (targetTab === 'requests') {
        loadRequestsData();
      } else if (targetTab === 'policies') {
        loadPoliciesData();
      }
    });
  });

  const brandHome = document.getElementById('btn-brand-home');
  if (brandHome) {
    brandHome.addEventListener('click', () => {
      const overviewTab = document.querySelector('.nav-item[data-tab="overview"]');
      if (overviewTab) overviewTab.click();
    });
  }
}

function initRefreshButton() {
  const refreshBtn = document.getElementById('btn-refresh');
  const syncLabel = document.getElementById('last-synced-label');

  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.textContent = 'Syncing...';
      refreshBtn.disabled = true;

      const activeTab = document.querySelector('.nav-item.active');
      const currentTab = activeTab ? activeTab.getAttribute('data-tab') : 'overview';
      
      if (currentTab === 'spend') {
        await loadSpendData();
      } else if (currentTab === 'optimizations') {
        await loadOptimizationsData();
      } else if (currentTab === 'requests') {
        await loadRequestsData();
      } else if (currentTab === 'policies') {
        await loadPoliciesData();
      } else {
        await loadOverviewData();
      }

      refreshBtn.textContent = 'Sync Analytics';
      refreshBtn.disabled = false;
      
      if (syncLabel) {
        const now = new Date();
        syncLabel.textContent = `Last synced: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      }
    });
  }
}

/**
 * 2. Phase 1 Overview Data Orchestrator
 */
async function loadOverviewData() {
  try {
    const [overviewRes, chartRes, recsRes, anomaliesRes, recentRes] = await Promise.all([
      fetch('/api/overview').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/charts/savings').then(r => r.ok ? r.json() : []).catch(() => []),
      fetch('/api/recommendations').then(r => r.ok ? r.json() : []).catch(() => []),
      fetch('/api/anomalies?z_score=2.0').then(r => r.ok ? r.json() : []).catch(() => []),
      fetch('/api/telemetry/recent?limit=5').then(r => r.ok ? r.json() : []).catch(() => [])
    ]);

    renderOverviewKPIs(overviewRes, recsRes);
    renderOverviewChart(chartRes);
    renderTopRecommendation(recsRes);
    renderAnomalies(anomaliesRes);
    renderActivityFeed(recentRes);
  } catch (err) {
    console.error('Failed to load Overview data:', err);
  }
}

function renderOverviewKPIs(overviewData, recsData) {
  const actualSpendEl = document.getElementById('kpi-total-spend');
  const baselineSpendEl = document.getElementById('kpi-baseline-spend');
  const totalSavingsEl = document.getElementById('kpi-total-savings');
  const savingsRateEl = document.getElementById('kpi-savings-rate');
  const savingsContextEl = document.getElementById('kpi-savings-context');
  const opportunitiesEl = document.getElementById('kpi-opportunities');

  if (!overviewData) return;

  const actualCost = overviewData.cost_actual || 0.0;
  const baselineCost = overviewData.cost_baseline || 0.0;
  const totalSavings = overviewData.total_savings || 0.0;

  let savingsRate = 0.0;
  if (baselineCost > 0) {
    savingsRate = (totalSavings / baselineCost) * 100;
  }

  let unrealizedSavings = 0.0;
  if (Array.isArray(recsData)) {
    unrealizedSavings = recsData.reduce((sum, r) => sum + (r.estimated_savings || 0.0), 0.0);
  }

  const bentoSpendEl = document.getElementById('kpi-total-spend-bento');

  if (actualSpendEl) actualSpendEl.textContent = formatCurrency(actualCost);
  if (bentoSpendEl) bentoSpendEl.textContent = formatCurrency(actualCost);
  if (baselineSpendEl) baselineSpendEl.textContent = formatCurrency(baselineCost);
  if (totalSavingsEl) totalSavingsEl.textContent = formatCurrency(totalSavings);
  if (savingsRateEl) savingsRateEl.textContent = `${savingsRate.toFixed(1)}%`;
  if (savingsContextEl) savingsContextEl.textContent = `${savingsRate.toFixed(1)}% (${formatCurrency(totalSavings)})`;
  if (opportunitiesEl) opportunitiesEl.textContent = formatCurrency(unrealizedSavings);
}

function renderOverviewChart(chartData) {
  const canvas = document.getElementById('overview-spend-chart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  
  const hasData = Array.isArray(chartData) && chartData.length > 0;
  const labels = hasData ? chartData.map(d => d.date) : ['No Data'];
  const baselineSeries = hasData ? chartData.map(d => d.baseline_cost) : [0];
  const actualSeries = hasData ? chartData.map(d => d.actual_cost) : [0];
  const dataCount = hasData ? chartData.length : 0;

  if (overviewChart) {
    overviewChart.destroy();
  }

  const gradient = ctx.createLinearGradient(0, 0, 0, 260);
  gradient.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
  gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

  overviewChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Baseline Spend',
          data: baselineSeries,
          borderColor: '#64748B',
          borderDash: [4, 4],
          borderWidth: 1.5,
          pointRadius: dataCount < 3 ? 5 : 2,
          pointHoverRadius: 6,
          fill: false,
          tension: 0.4
        },
        {
          label: 'Actual Spend (CostOpt)',
          data: actualSeries,
          borderColor: '#10B981',
          borderWidth: 2.5,
          pointRadius: dataCount < 3 ? 6 : 3,
          pointHoverRadius: 7,
          backgroundColor: gradient,
          fill: true,
          tension: 0.4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            color: '#94A3B8',
            font: { family: 'Inter', size: 11 },
            boxWidth: 12,
            usePointStyle: true
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: '#0E131F',
          titleColor: '#F8FAFC',
          bodyColor: '#94A3B8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${formatCurrency(context.parsed.y)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.03)' },
          ticks: { color: '#64748B', font: { family: 'Inter', size: 10 } }
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: {
            color: '#64748B',
            font: { family: 'Inter', size: 10 },
            callback: value => formatCurrency(value)
          }
        }
      }
    }
  });
}

function renderTopRecommendation(recsData) {
  const container = document.getElementById('overview-top-recommendation');
  if (!container) return;

  if (!Array.isArray(recsData) || recsData.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-weight: 500; color: var(--text-secondary);">No optimization opportunities detected</div>
        <div style="font-size: 11px; margin-top: 2px;">Current request traffic is being optimized effectively.</div>
      </div>
    `;
    return;
  }

  const topRec = recsData.slice().sort((a, b) => (b.estimated_savings || 0) - (a.estimated_savings || 0))[0];

  container.innerHTML = `
    <div style="display:flex; flex-direction:column; gap: var(--space-2);">
      <div style="display:flex; justify-content:space-between; align-items:flex-start;">
        <span class="badge badge-warning">${topRec.strategy || 'Recommendation'}</span>
        <span class="text-success font-weight-600 mono-text">+${formatCurrency(topRec.estimated_savings)} potential</span>
      </div>
      <div style="font-weight:600; font-size:13px; color:var(--text-primary);">${topRec.title || 'Optimization Opportunity'}</div>
      <div style="font-size:12px; color:var(--text-secondary); line-height:1.4;">${topRec.description || ''}</div>
      <div style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono); margin-top:4px;">${topRec.evidence || ''}</div>
    </div>
  `;
}

function renderAnomalies(anomaliesData) {
  const container = document.getElementById('overview-anomalies-list');
  if (!container) return;

  if (!Array.isArray(anomaliesData) || anomaliesData.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-weight: 500; color: var(--text-secondary);">No active anomalies</div>
        <div style="font-size: 11px; margin-top: 2px;">Recent spend is within expected range.</div>
      </div>
    `;
    return;
  }

  const itemsHtml = anomaliesData.slice(0, 3).map(a => `
    <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px solid var(--border-subtle);">
      <div>
        <span class="badge badge-danger">${a.date || 'Anomaly'}</span>
        <span style="font-size:12px; color:var(--text-secondary); margin-left:8px;">Cost: ${formatCurrency(a.cost)}</span>
      </div>
      <span class="mono-text text-danger" style="font-size:11px;">Variance flag</span>
    </div>
  `).join('');

  container.innerHTML = `<div style="display:flex; flex-direction:column;">${itemsHtml}</div>`;
}

function renderActivityFeed(recentLogs) {
  const tbody = document.getElementById('overview-activity-table');
  if (!tbody) return;

  if (!Array.isArray(recentLogs) || recentLogs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No telemetry data recorded yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = recentLogs.map(log => {
    const isCache = log.cache_hit === 1;
    const isSuccess = log.success === 1;
    
    let statusBadge = isSuccess ? `<span class="badge badge-success">200 OK</span>` : `<span class="badge badge-danger">FAILED</span>`;
    if (isCache) {
      statusBadge = `<span class="badge badge-success">CACHED</span>`;
    }

    const shortHash = log.prompt_hash ? log.prompt_hash.substring(0, 10) + '...' : 'n/a';
    const fullHash = log.prompt_hash || 'n/a';
    const timeStr = log.timestamp ? log.timestamp.split('T')[1] || log.timestamp : 'n/a';

    return `
      <tr>
        <td class="mono-text text-muted">${timeStr}</td>
        <td class="mono-text" title="${fullHash}">${shortHash}</td>
        <td>${log.model_requested || '-'}</td>
        <td class="mono-text">${log.model_used || '-'}</td>
        <td class="mono-text">${log.latency_ms ? log.latency_ms.toFixed(0) + 'ms' : '-'}</td>
        <td class="mono-text">${log.cost_actual !== undefined ? formatCurrency(log.cost_actual) : '-'}</td>
        <td>${statusBadge}</td>
      </tr>
    `;
  }).join('');
}

/**
 * ==========================================================================
 * 3. PHASE 2: SPEND PAGE DATA ORCHESTRATOR & RENDERING
 * ==========================================================================
 */
async function loadSpendData() {
  try {
    const [overviewRes, timeChartRes, modelsRes] = await Promise.all([
      fetch('/api/overview').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/charts/savings').then(r => r.ok ? r.json() : []).catch(() => []),
      fetch('/api/charts/models').then(r => r.ok ? r.json() : []).catch(() => [])
    ]);

    lastModelData = modelsRes;

    renderSpendKPIs(overviewRes);
    renderSpendTimeChart(timeChartRes);
    renderSpendDistribution(modelsRes);
    renderModelCostTable(modelsRes);
  } catch (err) {
    console.error('Failed to load Spend page data:', err);
  }
}

function renderSpendKPIs(data) {
  const baselineEl = document.getElementById('spend-kpi-baseline');
  const actualEl = document.getElementById('spend-kpi-actual');
  const savingsEl = document.getElementById('spend-kpi-savings');
  const rateEl = document.getElementById('spend-kpi-rate');

  if (!data) return;

  const baselineCost = data.cost_baseline || 0.0;
  const actualCost = data.cost_actual || 0.0;
  const savings = data.total_savings || 0.0;

  let savingsRate = 0.0;
  if (baselineCost > 0) {
    savingsRate = (savings / baselineCost) * 100;
  }

  if (baselineEl) baselineEl.textContent = formatCurrency(baselineCost);
  if (actualEl) actualEl.textContent = formatCurrency(actualCost);
  if (savingsEl) savingsEl.textContent = formatCurrency(savings);
  if (rateEl) rateEl.textContent = `${savingsRate.toFixed(1)}%`;
}

function renderSpendTimeChart(chartData) {
  const canvas = document.getElementById('spend-time-chart');
  if (!canvas) return;

  const parent = canvas.parentElement;
  const hasData = Array.isArray(chartData) && chartData.length > 0;
  const dataCount = hasData ? chartData.length : 0;

  if (parent) {
    if (dataCount < 3) {
      parent.style.height = '180px';
    } else {
      parent.style.height = '300px';
    }
  }

  const labels = hasData ? chartData.map(d => d.date) : ['No Data'];
  const baselineSeries = hasData ? chartData.map(d => d.baseline_cost) : [0];
  const actualSeries = hasData ? chartData.map(d => d.actual_cost) : [0];

  if (spendTimeChart) {
    spendTimeChart.destroy();
  }

  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 280);
  gradient.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
  gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

  spendTimeChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Baseline Spend',
          data: baselineSeries,
          borderColor: '#64748B',
          borderDash: [4, 4],
          borderWidth: 1.5,
          pointRadius: dataCount < 3 ? 6 : 2,
          pointHoverRadius: 7,
          fill: false,
          tension: 0.4
        },
        {
          label: 'Actual Spend (CostOpt)',
          data: actualSeries,
          borderColor: '#10B981',
          borderWidth: 2.5,
          pointRadius: dataCount < 3 ? 6 : 3,
          pointHoverRadius: 8,
          backgroundColor: gradient,
          fill: true,
          tension: 0.4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            color: '#94A3B8',
            font: { family: 'Inter', size: 11 },
            boxWidth: 12,
            usePointStyle: true
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: '#0E131F',
          titleColor: '#F8FAFC',
          bodyColor: '#94A3B8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${formatCurrency(context.parsed.y)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.03)' },
          ticks: { color: '#64748B', font: { family: 'Inter', size: 10 } }
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: {
            color: '#64748B',
            font: { family: 'Inter', size: 10 },
            callback: value => formatCurrency(value)
          }
        }
      }
    }
  });
}

function renderSpendDistribution(modelsData) {
  const modelContainer = document.getElementById('spend-by-model-container');
  const providerContainer = document.getElementById('spend-by-provider-container');

  if (!Array.isArray(modelsData) || modelsData.length === 0) {
    if (modelContainer) modelContainer.innerHTML = `<div class="empty-state">No model spend data recorded.</div>`;
    if (providerContainer) providerContainer.innerHTML = `<div class="empty-state">No provider spend data recorded.</div>`;
    return;
  }

  const totalSpend = modelsData.reduce((sum, item) => sum + (item.spend || 0.0), 0.0);

  if (modelContainer) {
    const sortedModels = modelsData.slice().sort((a, b) => (b.spend || 0) - (a.spend || 0));
    const modelRows = sortedModels.map(m => {
      const spend = m.spend || 0.0;
      const share = totalSpend > 0 ? (spend / totalSpend * 100) : 0.0;
      return `
        <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:12px;">
          <div style="display:flex; justify-content:space-between; font-size:12px;">
            <span style="font-weight:600; color:var(--text-primary);">${m.model_used || 'Unknown'}</span>
            <span class="mono-text" style="color:var(--text-secondary);">${formatCurrency(spend)} (${share.toFixed(1)}%)</span>
          </div>
          <div style="width:100%; height:6px; background:var(--bg-app); border-radius:3px; overflow:hidden;">
            <div style="width:${Math.max(share, 2).toFixed(1)}%; height:100%; background:var(--color-info); border-radius:3px;"></div>
          </div>
        </div>
      `;
    }).join('');
    modelContainer.innerHTML = `<div style="display:flex; flex-direction:column;">${modelRows}</div>`;
  }

  if (providerContainer) {
    const providerMap = {};
    modelsData.forEach(item => {
      const p = item.provider || 'unknown';
      providerMap[p] = (providerMap[p] || 0.0) + (item.spend || 0.0);
    });

    const uniqueProviders = Object.keys(providerMap);

    if (uniqueProviders.length === 1) {
      const singleProv = uniqueProviders[0];
      const spend = providerMap[singleProv];
      providerContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap: var(--space-2); padding: var(--space-2);">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:600; font-size:14px; color:var(--text-primary); text-transform:uppercase;">${singleProv}</span>
            <span class="badge badge-success">100% SHARE</span>
          </div>
          <div class="mono-text" style="font-size:18px; font-weight:700; color:var(--text-primary);">${formatCurrency(spend)}</div>
          <div style="font-size:11px; color:var(--text-muted);">Only 1 provider observed in current dataset.</div>
        </div>
      `;
    } else {
      const sortedProviders = uniqueProviders.map(p => ({
        provider: p,
        spend: providerMap[p],
        share: totalSpend > 0 ? (providerMap[p] / totalSpend * 100) : 0.0
      })).sort((a, b) => b.spend - a.spend);

      const providerRows = sortedProviders.map(p => `
        <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:12px;">
          <div style="display:flex; justify-content:space-between; font-size:12px;">
            <span style="font-weight:600; color:var(--text-primary); text-transform:uppercase;">${p.provider}</span>
            <span class="mono-text" style="color:var(--text-secondary);">${formatCurrency(p.spend)} (${p.share.toFixed(1)}%)</span>
          </div>
          <div style="width:100%; height:6px; background:var(--bg-app); border-radius:3px; overflow:hidden;">
            <div style="width:${Math.max(p.share, 2).toFixed(1)}%; height:100%; background:var(--color-success); border-radius:3px;"></div>
          </div>
        </div>
      `).join('');

      providerContainer.innerHTML = `<div style="display:flex; flex-direction:column;">${providerRows}</div>`;
    }
  }
}

function renderModelCostTable(modelsData) {
  const tbody = document.getElementById('spend-model-table-body');
  if (!tbody) return;

  if (!Array.isArray(modelsData) || modelsData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No model usage recorded.</td></tr>`;
    return;
  }

  const items = modelsData.map(m => {
    const baseline = m.baseline_cost || 0.0;
    const actual = m.spend || 0.0;
    const savings = m.savings || 0.0;
    const rate = baseline > 0 ? (savings / baseline * 100) : 0.0;
    return {
      model_used: m.model_used || '-',
      provider: m.provider || '-',
      count: m.count || 0,
      baseline_cost: baseline,
      spend: actual,
      savings: savings,
      savings_rate: rate
    };
  });

  items.sort((a, b) => {
    let valA = a[currentSortColumn];
    let valB = b[currentSortColumn];
    if (typeof valA === 'string') valA = valA.toLowerCase();
    if (typeof valB === 'string') valB = valB.toLowerCase();

    if (valA < valB) return currentSortDirection === 'asc' ? -1 : 1;
    if (valA > valB) return currentSortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  tbody.innerHTML = items.map(m => {
    const hasSavings = m.savings > 0;
    const savingsClass = hasSavings ? 'text-success font-weight-600' : 'text-muted';

    return `
      <tr>
        <td class="mono-text" style="font-weight:600; color:var(--text-primary);">${m.model_used}</td>
        <td style="text-transform:uppercase; font-size:11px;">${m.provider}</td>
        <td class="mono-text" style="text-align: right;">${m.count}</td>
        <td class="mono-text" style="text-align: right;">${formatCurrency(m.baseline_cost)}</td>
        <td class="mono-text" style="text-align: right; font-weight:600;">${formatCurrency(m.spend)}</td>
        <td class="mono-text ${savingsClass}" style="text-align: right;">${hasSavings ? '+' : ''}${formatCurrency(m.savings)}</td>
        <td class="mono-text ${savingsClass}" style="text-align: right;">${m.savings_rate.toFixed(1)}%</td>
      </tr>
    `;
  }).join('');
}

function initSortableHeaders() {
  const table = document.querySelector('#view-spend .data-table');
  if (!table) return;

  const headers = table.querySelectorAll('th');
  const sortMap = ['model_used', 'provider', 'count', 'baseline_cost', 'spend', 'savings', 'savings_rate'];

  headers.forEach((th, idx) => {
    const colKey = sortMap[idx];
    if (!colKey) return;

    th.classList.add('sortable');
    th.addEventListener('click', () => {
      if (currentSortColumn === colKey) {
        currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
      } else {
        currentSortColumn = colKey;
        currentSortDirection = 'desc';
      }

      headers.forEach(h => h.classList.remove('sort-active'));
      th.classList.add('sort-active');

      if (lastModelData.length > 0) {
        renderModelCostTable(lastModelData);
      }
    });
  });
}

/**
 * ==========================================================================
 * 4. PHASE 3: OPTIMIZATIONS PAGE DATA ORCHESTRATOR & RENDERING
 * ==========================================================================
 */
async function loadOptimizationsData() {
  try {
    const [optSummaryRes, recsRes, recentLogsRes, intelRes] = await Promise.all([
      fetch('/api/optimizations/summary').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/recommendations').then(r => r.ok ? r.json() : []).catch(() => []),
      fetch('/api/telemetry/recent?limit=30').then(r => r.ok ? r.json() : []).catch(() => []),
      fetch('/api/intelligence/distribution').then(r => r.ok ? r.json() : null).catch(() => null)
    ]);

    renderOptKPIs(optSummaryRes);
    renderIntelligenceDistributions(intelRes);
    renderOptStrategies(optSummaryRes);
    renderOptActivity(recentLogsRes);
    renderOptUnrealized(recsRes);
  } catch (err) {
    console.error('Failed to load Optimizations page data:', err);
  }
}

function renderIntelligenceDistributions(intelData) {
  const decContainer = document.getElementById('opt-decision-dist-container');
  const taskContainer = document.getElementById('opt-task-dist-container');

  if (!intelData) return;

  if (decContainer) {
    const d = intelData.decisions || {};
    const total = (d.cache_hits || 0) + (d.reroutes || 0) + (d.direct_requests || 0);

    if (total === 0) {
      decContainer.innerHTML = `<div class="empty-state">No decision telemetry recorded yet.</div>`;
    } else {
      const cachePct = (d.cache_hits / total * 100).toFixed(1);
      const reroutePct = (d.reroutes / total * 100).toFixed(1);
      const directPct = (d.direct_requests / total * 100).toFixed(1);

      decContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div>
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
              <span class="text-success" style="font-weight:600;">CACHE HITS</span>
              <span class="mono-text">${d.cache_hits} (${cachePct}%)</span>
            </div>
            <div style="width:100%; height:6px; background:var(--bg-app); border-radius:3px; overflow:hidden;">
              <div style="width:${cachePct}%; height:100%; background:var(--color-success);"></div>
            </div>
          </div>

          <div>
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
              <span class="text-warning" style="font-weight:600;">MODEL REROUTES</span>
              <span class="mono-text">${d.reroutes} (${reroutePct}%)</span>
            </div>
            <div style="width:100%; height:6px; background:var(--bg-app); border-radius:3px; overflow:hidden;">
              <div style="width:${reroutePct}%; height:100%; background:var(--color-warning);"></div>
            </div>
          </div>

          <div>
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
              <span class="text-muted" style="font-weight:600;">DIRECT EXECUTION</span>
              <span class="mono-text">${d.direct_requests} (${directPct}%)</span>
            </div>
            <div style="width:100%; height:6px; background:var(--bg-app); border-radius:3px; overflow:hidden;">
              <div style="width:${directPct}%; height:100%; background:var(--border-subtle);"></div>
            </div>
          </div>

          <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">
            Avg Optimization Confidence: <strong class="mono-text text-primary">${d.avg_confidence ? (d.avg_confidence * 100).toFixed(0) + '%' : '100%'}</strong>
          </div>
        </div>
      `;
    }
  }

  if (taskContainer) {
    const tasks = intelData.task_distribution || [];
    if (tasks.length === 0) {
      taskContainer.innerHTML = `<div class="empty-state">No task classification data recorded.</div>`;
    } else {
      const totalTasks = tasks.reduce((sum, t) => sum + (t.count || 0), 0);
      const rowsHtml = tasks.map(t => {
        const pct = totalTasks > 0 ? (t.count / totalTasks * 100).toFixed(1) : 0;
        return `
          <div style="display:flex; justify-content:space-between; font-size:12px; padding:4px 0; border-bottom:1px solid var(--border-subtle);">
            <span style="font-weight:500; color:var(--text-primary); text-transform:capitalize;">${t.task_type.replace('_', ' ')}</span>
            <span class="mono-text text-muted">${t.count} (${pct}%)</span>
          </div>
        `;
      }).join('');
      taskContainer.innerHTML = `<div style="display:flex; flex-direction:column;">${rowsHtml}</div>`;
    }
  }
}

function renderOptKPIs(summary) {
  const totalSavingsEl = document.getElementById('opt-kpi-total-savings');
  const cacheSavingsEl = document.getElementById('opt-kpi-cache-savings');
  const cacheCountEl = document.getElementById('opt-kpi-cache-count');
  const rerouteSavingsEl = document.getElementById('opt-kpi-reroute-savings');
  const rerouteCountEl = document.getElementById('opt-kpi-reroute-count');
  const rateEl = document.getElementById('opt-kpi-rate');
  const optCountEl = document.getElementById('opt-kpi-optimized-count');
  const totalCountEl = document.getElementById('opt-kpi-total-count');

  if (!summary) return;

  if (totalSavingsEl) totalSavingsEl.textContent = formatCurrency(summary.total_savings);
  if (cacheSavingsEl) cacheSavingsEl.textContent = formatCurrency(summary.cache_savings);
  if (cacheCountEl) cacheCountEl.textContent = summary.cache_count || 0;
  if (rerouteSavingsEl) rerouteSavingsEl.textContent = formatCurrency(summary.reroute_savings);
  if (rerouteCountEl) rerouteCountEl.textContent = summary.reroute_count || 0;
  if (rateEl) rateEl.textContent = `${(summary.optimization_rate || 0.0).toFixed(1)}%`;
  if (optCountEl) optCountEl.textContent = summary.optimized_requests || 0;
  if (totalCountEl) totalCountEl.textContent = summary.total_requests || 0;
}

function renderOptStrategies(summary) {
  const container = document.getElementById('opt-strategies-container');
  if (!container) return;

  if (!summary || summary.total_requests === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-weight: 500; color: var(--text-secondary);">No optimization engines activated yet</div>
        <div style="font-size: 11px; margin-top: 2px;">Send requests via CostOpt SDK to activate local SQLite caching and model rerouting.</div>
      </div>
    `;
    return;
  }

  const cachePct = summary.total_requests > 0 ? (summary.cache_count / summary.total_requests * 100) : 0.0;
  const reroutePct = summary.total_requests > 0 ? (summary.reroute_count / summary.total_requests * 100) : 0.0;

  container.innerHTML = `
    <div style="background:var(--bg-app); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:var(--space-3); display:flex; flex-direction:column; gap:8px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="badge badge-success">ACTIVE</span>
          <span style="font-weight:600; font-size:13px; color:var(--text-primary);">Local SQLite Prompt Cache</span>
        </div>
        <span class="mono-text text-success" style="font-weight:600;">+${formatCurrency(summary.cache_savings)} saved</span>
      </div>
      <div style="font-size:12px; color:var(--text-secondary);">
        Interception engine hashes prompts to replay exact matches locally in &lt;15ms at $0.00 cost.
      </div>
      <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted);">
        <span>Requests affected: <strong class="mono-text text-primary">${summary.cache_count}</strong> (${cachePct.toFixed(1)}% of total)</span>
        <span>Status: <strong class="text-success">Operational</strong></span>
      </div>
    </div>

    <div style="background:var(--bg-app); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:var(--space-3); display:flex; flex-direction:column; gap:8px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="badge badge-warning">ACTIVE</span>
          <span style="font-weight:600; font-size:13px; color:var(--text-primary);">Rule-Based Model Rerouting</span>
        </div>
        <span class="mono-text text-success" style="font-weight:600;">+${formatCurrency(summary.reroute_savings)} saved</span>
      </div>
      <div style="font-size:12px; color:var(--text-secondary);">
        Auto-routes simple queries from expensive premium models to cost-efficient mini/haiku equivalents via costopt.yaml rules.
      </div>
      <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted);">
        <span>Requests affected: <strong class="mono-text text-primary">${summary.reroute_count}</strong> (${reroutePct.toFixed(1)}% of total)</span>
        <span>Status: <strong class="text-success">Operational</strong></span>
      </div>
    </div>
  `;
}

function renderOptActivity(recentLogs) {
  const tbody = document.getElementById('opt-activity-table-body');
  if (!tbody) return;

  if (!Array.isArray(recentLogs) || recentLogs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-state">
          <div style="font-weight: 500; color: var(--text-secondary);">No optimization events recorded yet</div>
          <div style="font-size: 11px; margin-top: 2px;">Send requests through the CostOpt SDK to begin tracking activity.</div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = recentLogs.map(log => {
    const isCache = log.cache_hit === 1;
    const isReroute = !isCache && (log.model_requested !== log.model_used);
    
    let optTypeBadge = `<span class="badge badge-neutral">DIRECT REQUEST</span>`;
    if (isCache) {
      optTypeBadge = `<span class="badge badge-success">CACHE HIT</span>`;
    } else if (isReroute) {
      optTypeBadge = `<span class="badge badge-warning">MODEL REROUTE</span>`;
    }

    const costBefore = log.cost_original || 0.0;
    const costAfter = log.cost_actual || 0.0;
    const savings = log.savings || 0.0;
    const hasSavings = savings > 0;
    const timeStr = log.timestamp ? log.timestamp.split('T')[1] || log.timestamp : 'n/a';

    return `
      <tr>
        <td class="mono-text text-muted">${timeStr}</td>
        <td class="mono-text">${log.model_requested || '-'}</td>
        <td class="mono-text" style="font-weight:600; color:var(--text-primary);">${log.model_used || '-'}</td>
        <td>${optTypeBadge}</td>
        <td class="mono-text" style="text-align: right;">${formatCurrency(costBefore)}</td>
        <td class="mono-text" style="text-align: right;">${formatCurrency(costAfter)}</td>
        <td class="mono-text ${hasSavings ? 'text-success font-weight-600' : 'text-muted'}" style="text-align: right;">
          ${hasSavings ? '+' : ''}${formatCurrency(savings)}
        </td>
      </tr>
    `;
  }).join('');
}

function renderOptUnrealized(recsData) {
  const container = document.getElementById('opt-unrealized-container');
  if (!container) return;

  if (!Array.isArray(recsData) || recsData.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-weight: 500; color: var(--text-secondary);">No optimization opportunities detected</div>
        <div style="font-size: 11px; margin-top: 2px;">Current request traffic is being optimized effectively.</div>
      </div>
    `;
    return;
  }

  const html = recsData.map(r => `
    <div style="background:var(--bg-app); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:var(--space-3); margin-bottom:var(--space-3); display:flex; flex-direction:column; gap:6px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span class="badge badge-warning">${r.strategy || 'Recommendation'}</span>
          <span style="font-weight:600; font-size:13px; color:var(--text-primary);">${r.title || 'Optimization Opportunity'}</span>
        </div>
        <span class="mono-text text-success" style="font-weight:600;">+${formatCurrency(r.estimated_savings)} potential</span>
      </div>
      <div style="font-size:12px; color:var(--text-secondary); line-height:1.4;">${r.description || ''}</div>
      <div style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono); margin-top:2px;">Evidence: ${r.evidence || ''}</div>
    </div>
  `).join('');

  container.innerHTML = `<div style="display:flex; flex-direction:column;">${html}</div>`;
}

/**
 * ==========================================================================
 * 5. PHASE 4: REQUESTS EXPLORER DATA ORCHESTRATOR & RENDERING
 * ==========================================================================
 */
async function loadRequestsData() {
  try {
    const summaryRes = await fetch('/api/requests/summary').then(r => r.ok ? r.json() : null).catch(() => null);
    renderRequestsKPIs(summaryRes);

    await fetchAndRenderRequestsTable();
  } catch (err) {
    console.error('Failed to load Requests page data:', err);
  }
}

function renderRequestsKPIs(summary) {
  const totalEl = document.getElementById('req-kpi-total');
  const optEl = document.getElementById('req-kpi-optimized');
  const cacheEl = document.getElementById('req-kpi-cache-hits');
  const latEl = document.getElementById('req-kpi-avg-latency');

  if (!summary) return;

  if (totalEl) totalEl.textContent = summary.total_requests || 0;
  if (optEl) optEl.textContent = summary.optimized_requests || 0;
  if (cacheEl) cacheEl.textContent = summary.cache_hits || 0;
  if (latEl) latEl.textContent = `${(summary.avg_latency || 0.0).toFixed(0)} ms`;
}

function initRequestFilters() {
  const searchInput = document.getElementById('req-search-input');
  const outcomeSelect = document.getElementById('req-filter-outcome');
  const clearBtn = document.getElementById('btn-clear-filters');

  let debounceTimer = null;

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentRequestSearch = e.target.value.trim();
        fetchAndRenderRequestsTable();
      }, 250);
    });
  }

  if (outcomeSelect) {
    outcomeSelect.addEventListener('change', (e) => {
      currentRequestOutcome = e.target.value;
      fetchAndRenderRequestsTable();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (searchInput) searchInput.value = '';
      if (outcomeSelect) outcomeSelect.value = 'all';
      currentRequestSearch = '';
      currentRequestOutcome = 'all';
      fetchAndRenderRequestsTable();
    });
  }
}

async function fetchAndRenderRequestsTable() {
  const tbody = document.getElementById('req-table-body');
  const countLabel = document.getElementById('req-count-label');
  const badgeContainer = document.getElementById('req-filter-badge-container');

  if (!tbody) return;

  try {
    let queryParams = new URLSearchParams();
    if (currentRequestSearch) queryParams.append('search', currentRequestSearch);
    if (currentRequestOutcome !== 'all') queryParams.append('outcome', currentRequestOutcome);
    queryParams.append('limit', '100');

    const res = await fetch(`/api/requests/list?${queryParams.toString()}`);
    if (!res.ok) throw new Error('API fetch failed');
    const data = await res.json();

    const items = data.items || [];
    const totalCount = data.total_count || 0;

    if (countLabel) countLabel.textContent = totalCount;

    if (badgeContainer) {
      const activeBadges = [];
      if (currentRequestSearch) activeBadges.push(`<span class="badge badge-info">Search: "${currentRequestSearch}"</span>`);
      if (currentRequestOutcome !== 'all') activeBadges.push(`<span class="badge badge-warning">Outcome: ${currentRequestOutcome}</span>`);
      badgeContainer.innerHTML = activeBadges.join(' ');
    }

    if (items.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" class="empty-state">
            <div style="font-weight: 500; color: var(--text-secondary);">No matching request records found</div>
            <div style="font-size: 11px; margin-top: 2px;">Try clearing search filters or sending SDK traffic.</div>
          </td>
        </tr>
      `;
      return;
    }

    window._requestLogsMap = window._requestLogsMap || {};

    tbody.innerHTML = items.map((log, idx) => {
      const id = log.request_id || `req_${idx}`;
      window._requestLogsMap[id] = log;

      const isCache = log.cache_hit === 1;
      const isReroute = !isCache && (log.model_requested !== log.model_used);
      
      let outcomeBadge = `<span class="badge badge-neutral">DIRECT</span>`;
      if (isCache) {
        outcomeBadge = `<span class="badge badge-success">CACHE HIT</span>`;
      } else if (isReroute) {
        outcomeBadge = `<span class="badge badge-warning">REROUTE</span>`;
      }

      const shortHash = log.prompt_hash ? log.prompt_hash.substring(0, 10) + '...' : 'n/a';
      const fullHash = log.prompt_hash || 'n/a';
      const timeStr = log.timestamp ? log.timestamp.split('T')[1] || log.timestamp : 'n/a';
      const savings = log.savings || 0.0;
      const hasSavings = savings > 0;

      return `
        <tr style="cursor: pointer;" onclick="openRequestDetailModalById('${id}')">
          <td class="mono-text text-muted">${timeStr}</td>
          <td class="mono-text" title="${fullHash}">${shortHash}</td>
          <td class="mono-text">${log.model_requested || '-'}</td>
          <td class="mono-text" style="font-weight:600; color:var(--text-primary);">${log.model_used || '-'}</td>
          <td>${outcomeBadge}</td>
          <td class="mono-text" style="text-align: right;">${log.latency_ms ? log.latency_ms.toFixed(0) + 'ms' : '-'}</td>
          <td class="mono-text" style="text-align: right;">${formatCurrency(log.cost_actual)}</td>
          <td class="mono-text ${hasSavings ? 'text-success font-weight-600' : 'text-muted'}" style="text-align: right;">
            ${hasSavings ? '+' : ''}${formatCurrency(savings)}
          </td>
          <td style="text-align: center;">
            <button class="btn" style="padding: 2px 8px; font-size: 10px;" onclick="event.stopPropagation(); openRequestDetailModalById('${id}');">Inspect</button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error rendering requests table:', err);
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state text-danger">Failed to load request log.</td></tr>`;
  }
}

function openRequestDetailModalById(reqId) {
  const modal = document.getElementById('global-modal');
  if (!modal) return;

  const log = window._requestLogsMap ? window._requestLogsMap[reqId] : null;
  if (!log) return;

    const isCache = log.cache_hit === 1;
    const isReroute = !isCache && (log.model_requested !== log.model_used);
    
    let outcomeBadge = `<span class="badge badge-neutral">DIRECT REQUEST</span>`;
    if (isCache) {
      outcomeBadge = `<span class="badge badge-success">CACHE HIT (0ms API)</span>`;
    } else if (isReroute) {
      outcomeBadge = `<span class="badge badge-warning">MODEL REROUTE</span>`;
    }

    modal.innerHTML = `
      <div class="modal-content">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; border-bottom:1px solid var(--border-subtle); padding-bottom:var(--space-3); margin-bottom:var(--space-3);">
          <div>
            <h3 style="font-size:15px; font-weight:700; color:var(--text-primary); margin:0;">Request Inspection</h3>
            <span style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${log.request_id || 'ID N/A'}</span>
          </div>
          <button class="btn btn-secondary" style="padding:4px 8px; font-size:12px;" onclick="closeModal()">✕ Close</button>
        </div>

        <div style="display:flex; flex-direction:column; gap:var(--space-3); font-size:12px;">
          
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:var(--space-3);">
            <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span class="text-muted" style="font-size:11px; display:block;">Requested Model</span>
              <strong class="mono-text" style="color:var(--text-primary); font-size:13px;">${log.model_requested || '-'}</strong>
            </div>

            <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span class="text-muted" style="font-size:11px; display:block;">Executed Model</span>
              <strong class="mono-text" style="color:var(--color-info); font-size:13px;">${log.model_used || '-'}</strong>
            </div>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
            <span class="text-muted" style="font-size:11px;">Optimization Outcome</span>
            <div>${outcomeBadge}</div>
          </div>

          <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:var(--space-2); text-align:center;">
            <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span class="text-muted" style="font-size:10px; display:block;">Input Tokens</span>
              <strong class="mono-text">${log.input_tokens || 0}</strong>
            </div>
            <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span class="text-muted" style="font-size:10px; display:block;">Output Tokens</span>
              <strong class="mono-text">${log.output_tokens || 0}</strong>
            </div>
            <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span class="text-muted" style="font-size:10px; display:block;">Latency</span>
              <strong class="mono-text">${log.latency_ms ? log.latency_ms.toFixed(0) + ' ms' : '0 ms'}</strong>
            </div>
          </div>

          <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:var(--space-2); text-align:center;">
            <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span class="text-muted" style="font-size:10px; display:block;">Baseline Cost</span>
              <strong class="mono-text">${formatCurrency(log.cost_original)}</strong>
            </div>
            <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span class="text-muted" style="font-size:10px; display:block;">Actual Cost</span>
              <strong class="mono-text" style="color:var(--text-primary);">${formatCurrency(log.cost_actual)}</strong>
            </div>
            <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle);">
              <span class="text-muted" style="font-size:10px; display:block;">Net Savings</span>
              <strong class="mono-text text-success">+${formatCurrency(log.savings)}</strong>
            </div>
          </div>

          <div style="background:var(--bg-app); padding:var(--space-2); border-radius:var(--radius-sm); border:1px solid var(--border-subtle); display:flex; flex-direction:column; gap:4px; font-size:11px;">
            <div style="display:flex; justify-content:space-between;">
              <span class="text-muted">Prompt Hash:</span>
              <span class="mono-text" style="color:var(--text-primary);">${log.prompt_hash || 'n/a'}</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
              <span class="text-muted">Timestamp:</span>
              <span class="mono-text">${log.timestamp || 'n/a'}</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
              <span class="text-muted">Environment / App / Region:</span>
              <span class="mono-text">${log.environment || 'dev'} / ${log.application || 'app'} / ${log.region || 'us-east-1'}</span>
            </div>
          </div>

          <div style="background:var(--bg-app); padding:var(--space-3); border-radius:var(--radius-sm); border:1px solid var(--border-subtle); display:flex; flex-direction:column; gap:6px;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-subtle); padding-bottom:4px;">
              <span style="font-size:11px; font-weight:700; color:var(--text-primary); text-transform:uppercase;">Decision Intelligence Trace</span>
              <span class="badge badge-info" style="font-size:10px;">${(log.task_type || 'general_chat').replace('_', ' ')} | ${(log.complexity || 'medium').toUpperCase()}</span>
            </div>

            <div style="display:flex; flex-direction:column; gap:4px; margin-top:4px; font-size:11px; font-family:var(--font-mono); color:var(--text-secondary);">
              ${(() => {
                let traceArr = [];
                try {
                  if (log.decision_trace) {
                    traceArr = typeof log.decision_trace === 'string' ? JSON.parse(log.decision_trace) : log.decision_trace;
                  }
                } catch(e){}

                if (!traceArr || traceArr.length === 0) {
                  traceArr = [
                    `Request Intercepted: requested_model='${log.model_requested}'`,
                    `Task Analysis: task_type='${log.task_type || 'general_chat'}', complexity='${log.complexity || 'medium'}', confidence=${(log.confidence || 0.90).toFixed(2)}`,
                    `Cache Evaluation: ${log.cache_hit ? 'HIT (Exact Match)' : 'MISS'}`,
                    `Routing Evaluation: ${log.decision_reason || 'Standard execution rule'}`,
                    `Final Decision: ${log.cache_hit ? 'CACHE' : (log.model_requested !== log.model_used ? 'REROUTE' : 'DIRECT')} -> Executed '${log.model_used}'`
                  ];
                }

                return traceArr.map(step => `
                  <div style="display:flex; align-items:flex-start; gap:6px;">
                    <span style="color:var(--color-info);">↓</span>
                    <span>${step}</span>
                  </div>
                `).join('');
              })()}
            </div>
          </div>

        </div>
      </div>
    `;

    modal.classList.add('active-modal');
  } catch (err) {
    console.error('Failed to open request detail modal:', err);
  }
}

function closeModal() {
  const modal = document.getElementById('global-modal');
  if (modal) {
    modal.classList.remove('active-modal');
  }
}

/**
 * ==========================================================================
 * 6. PHASE 5: POLICIES PAGE DATA ORCHESTRATOR & RENDERING
 * ==========================================================================
 */
async function loadPoliciesData() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) throw new Error('Failed fetching config');
    const data = await res.json();

    if (data.status === 'success') {
      initialYamlConfig = data.content;
      const editor = document.getElementById('pol-yaml-editor');
      if (editor) {
        editor.value = data.content;
      }
      updatePolicyConfigState(false);
    }
  } catch (err) {
    console.error('Failed to load Policies data:', err);
  }
}

function initPolicyEditor() {
  const editor = document.getElementById('pol-yaml-editor');
  const saveBtn = document.getElementById('btn-save-config');
  const revertBtn = document.getElementById('btn-revert-config');
  const feedbackEl = document.getElementById('pol-editor-feedback');

  if (!editor) return;

  editor.addEventListener('input', () => {
    const isModified = editor.value !== initialYamlConfig;
    updatePolicyConfigState(isModified);
  });

  if (revertBtn) {
    revertBtn.addEventListener('click', () => {
      editor.value = initialYamlConfig;
      updatePolicyConfigState(false);
      if (feedbackEl) feedbackEl.style.display = 'none';
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      if (feedbackEl) {
        feedbackEl.style.display = 'none';
        feedbackEl.className = '';
      }

      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: editor.value })
        });

        const data = await res.json();

        if (res.ok && data.status === 'success') {
          initialYamlConfig = editor.value;
          updatePolicyConfigState(false);
          
          if (feedbackEl) {
            feedbackEl.className = 'text-success';
            feedbackEl.textContent = 'Configuration saved and active in costopt.yaml.';
            feedbackEl.style.display = 'block';
          }
        } else {
          throw new Error(data.detail || data.message || 'Failed saving configuration');
        }
      } catch (err) {
        console.error('Error saving config:', err);
        if (feedbackEl) {
          feedbackEl.className = 'text-danger';
          feedbackEl.textContent = `Error: ${err.message}`;
          feedbackEl.style.display = 'block';
        }
      } finally {
        saveBtn.textContent = 'Save Configuration';
      }
    });
  }
}

function updatePolicyConfigState(isModified) {
  const badge = document.getElementById('pol-config-unsaved-badge');
  const saveBtn = document.getElementById('btn-save-config');
  const revertBtn = document.getElementById('btn-revert-config');
  const stateKPI = document.getElementById('pol-kpi-config-state');

  if (badge) badge.style.display = isModified ? 'inline-flex' : 'none';
  if (saveBtn) saveBtn.disabled = !isModified;
  if (revertBtn) revertBtn.disabled = !isModified;
  if (stateKPI) {
    if (isModified) {
      stateKPI.textContent = 'Unsaved Changes';
      stateKPI.className = 'kpi-value text-warning';
    } else {
      stateKPI.textContent = 'Synced';
      stateKPI.className = 'kpi-value text-success';
    }
  }
}

/**
 * Destructive Operations Handlers (Clear Cache & Reset Telemetry)
 */
function initDestructiveActions() {
  const clearCacheBtn = document.getElementById('btn-clear-cache');
  const resetTelemetryBtn = document.getElementById('btn-reset-telemetry');

  if (clearCacheBtn) {
    clearCacheBtn.addEventListener('click', () => {
      openConfirmModal(
        'Clear Local Cache Database',
        'Are you sure you want to wipe all prompt completion entries from the local SQLite cache? Subsequent calls will miss cache and hit upstream APIs.',
        'Clear Cache',
        async () => {
          try {
            const res = await fetch('/api/cache/clear', { method: 'POST' });
            const data = await res.json();
            closeModal();
            alert(data.message || 'Cache database cleared successfully.');
          } catch (err) {
            alert(`Failed clearing cache: ${err.message}`);
          }
        }
      );
    });
  }

  if (resetTelemetryBtn) {
    resetTelemetryBtn.addEventListener('click', () => {
      openConfirmModal(
        'Reset Telemetry Analytics',
        'Are you sure you want to delete ALL logged telemetry records? All spend, baseline, and savings analytics will be reset to zero. This action cannot be undone.',
        'Reset Telemetry',
        async () => {
          try {
            const res = await fetch('/api/telemetry/reset', { method: 'POST' });
            const data = await res.json();
            closeModal();
            alert(data.message || 'Telemetry database reset successfully.');
            loadOverviewData();
          } catch (err) {
            alert(`Failed resetting telemetry: ${err.message}`);
          }
        }
      );
    });
  }
}

function openConfirmModal(title, description, confirmBtnText, onConfirm) {
  const modal = document.getElementById('global-modal');
  if (!modal) return;

  modal.innerHTML = `
    <div class="modal-content">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; border-bottom:1px solid var(--border-subtle); padding-bottom:var(--space-3); margin-bottom:var(--space-3);">
        <h3 style="font-size:15px; font-weight:700; color:var(--color-danger); margin:0;">${title}</h3>
        <button class="btn btn-secondary" style="padding:4px 8px; font-size:12px;" onclick="closeModal()">✕ Cancel</button>
      </div>

      <div style="font-size:12px; color:var(--text-secondary); line-height:1.5; margin-bottom:var(--space-4);">
        ${description}
      </div>

      <div style="display:flex; justify-content:flex-end; gap:var(--space-2);">
        <button class="btn btn-secondary" style="font-size:12px;" onclick="closeModal()">Cancel</button>
        <button id="modal-btn-confirm" class="btn btn-danger" style="font-size:12px;">${confirmBtnText}</button>
      </div>
    </div>
  `;

  modal.classList.add('active-modal');

  const confirmBtn = document.getElementById('modal-btn-confirm');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', onConfirm);
  }
}
