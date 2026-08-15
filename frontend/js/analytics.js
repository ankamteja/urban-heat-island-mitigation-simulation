/* Analytics panel — KPIs plus four Chart.js views over the active cell set. */

const CHART_INK = '#94A3B8';
const CHART_GRID = 'rgba(255,255,255,.07)';
const charts = {};

function initChartDefaults() {
  if (!window.Chart) return;
  Chart.defaults.color = CHART_INK;
  Chart.defaults.borderColor = CHART_GRID;
  Chart.defaults.font.family = "'Fira Sans', system-ui, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.animation.duration = 420;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.maintainAspectRatio = false;
}

function swap(key, canvasId, config) {
  if (charts[key]) charts[key].destroy();
  const el = document.getElementById(canvasId);
  if (!el) return;
  charts[key] = new Chart(el.getContext('2d'), config);
}

function renderKpis(containerId, stats) {
  const el = document.getElementById(containerId);
  const cards = [
    { cls: '', v: stats.n.toLocaleString(), k: 'Cells analysed' },
    { cls: 'k-hot', v: stats.meanTemp.toFixed(1) + '°C', k: 'Mean surface temp' },
    { cls: 'k-hot', v: stats.maxTemp.toFixed(1) + '°C', k: 'Peak hotspot' },
    // Every cooling and cost card below names its denominator. The previous
    // labels did not, so "Modelled mean drop -0.50°C" sat beside "Programme
    // cost ₹167 Cr" and read as the price of half a degree. They are not the
    // same population: the cost treats 4,157 cells, the drop is averaged over
    // all 8,144.
    { cls: 'k-cool', v: '−' + stats.meanDropTreated.toFixed(2) + '°C', k: 'Mean drop, treated cells' },
    { cls: 'k-cool', v: '−' + stats.meanDrop.toFixed(2) + '°C', k: 'Mean drop, whole grid' },
    { cls: 'k-cool', v: stats.meanAfter.toFixed(1) + '°C', k: 'Projected grid mean' },
    { cls: '', v: stats.treated.toLocaleString(), k: 'Actionable cells' },
    { cls: 'k-cost', v: inrShort(stats.cost), k: 'Cost if all treated' }
  ];
  el.innerHTML = cards.map(c => `<div class="kpi ${c.cls}"><b>${c.v}</b><span>${c.k}</span></div>`).join('');
}

function histogram(cells, bins, lo, hi) {
  const out = new Array(bins).fill(0);
  const w = (hi - lo) / bins;
  for (const c of cells) {
    let i = Math.floor((c.temp - lo) / w);
    if (i < 0) i = 0;
    if (i >= bins) i = bins - 1;
    out[i]++;
  }
  return { counts: out, width: w };
}

function renderCharts(cells) {
  if (!window.Chart) return;

  const after = applyIntervention(cells);
  const BINS = 18;
  const lo = TEMP_DOMAIN.min, hi = TEMP_DOMAIN.max;
  const hBefore = histogram(cells, BINS, lo, hi);
  const hAfter = histogram(after, BINS, lo, hi);
  const labels = hBefore.counts.map((_, i) => (lo + i * hBefore.width).toFixed(1));

  swap('dist', 'chart-dist', {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Current', data: hBefore.counts, backgroundColor: 'rgba(239,68,68,.72)', borderRadius: 2 },
        { label: 'After mitigation', data: hAfter.counts, backgroundColor: 'rgba(52,211,153,.66)', borderRadius: 2 }
      ]
    },
    options: {
      plugins: { tooltip: { callbacks: { title: it => `${it[0].label}–${(+it[0].label + hBefore.width).toFixed(1)}°C` } } },
      scales: {
        x: {
          grid: { display: false },
          title: { display: true, text: '°C', color: CHART_INK },
          ticks: { maxTicksLimit: 7, maxRotation: 0, autoSkip: true }
        },
        y: { grid: { color: CHART_GRID }, title: { display: true, text: 'cells', color: CHART_INK } }
      }
    }
  });

  const pOrder = ['High', 'Medium', 'Low'];
  const stats = summarize(cells);
  swap('priority', 'chart-priority', {
    type: 'doughnut',
    data: {
      labels: pOrder,
      datasets: [{
        data: pOrder.map(p => stats.byPriority[p] || 0),
        backgroundColor: pOrder.map(p => PRIORITY_COLOR[p]),
        borderColor: '#131C2E',
        borderWidth: 2
      }]
    },
    options: {
      cutout: '58%',
      plugins: {
        legend: { position: 'right' },
        tooltip: {
          callbacks: {
            label: it => {
              const total = it.dataset.data.reduce((a, b) => a + b, 0) || 1;
              return ` ${it.label}: ${it.raw.toLocaleString()} (${(it.raw / total * 100).toFixed(1)}%)`;
            }
          }
        }
      }
    }
  });

  const step = Math.max(1, Math.ceil(cells.length / 1200));
  const pts = [];
  for (let i = 0; i < cells.length; i += step) {
    const c = cells[i];
    if (c.ndvi === null) continue;
    pts.push({ x: c.ndvi, y: c.temp, p: c.priority });
  }
  swap('ndvi', 'chart-ndvi', {
    type: 'scatter',
    data: {
      datasets: pOrder.map(p => ({
        label: p,
        data: pts.filter(d => d.p === p),
        backgroundColor: (PRIORITY_COLOR[p] || '#64748B') + 'aa',
        pointRadius: 2.2,
        pointHoverRadius: 5
      }))
    },
    options: {
      plugins: {
        tooltip: { callbacks: { label: it => ` NDVI ${it.parsed.x.toFixed(3)} · ${it.parsed.y.toFixed(1)}°C` } }
      },
      scales: {
        x: { grid: { color: CHART_GRID }, title: { display: true, text: 'NDVI', color: CHART_INK } },
        y: { grid: { color: CHART_GRID }, title: { display: true, text: '°C', color: CHART_INK } }
      }
    }
  });

  const actions = Object.keys(stats.byAction);
  swap('action', 'chart-action', {
    type: 'bar',
    data: {
      labels: actions.length ? actions : ['No action'],
      datasets: [
        {
          label: 'Total cooling (°C·cells)',
          data: actions.map(a => +stats.byAction[a].cooling.toFixed(1)),
          backgroundColor: actions.map(a => (INTERVENTIONS[a] || INTERVENTIONS.None).color + 'cc'),
          borderRadius: 3,
          yAxisID: 'y'
        },
        {
          label: 'Cost (₹ Cr)',
          data: actions.map(a => +(stats.byAction[a].cost / 1e7).toFixed(2)),
          backgroundColor: 'rgba(251,191,36,.55)',
          borderRadius: 3,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      scales: {
        x: { grid: { display: false } },
        y: { position: 'left', grid: { color: CHART_GRID }, title: { display: true, text: '°C·cells', color: CHART_INK } },
        y1: { position: 'right', grid: { display: false }, title: { display: true, text: '₹ Cr', color: CHART_INK } }
      }
    }
  });
}

function updateAnalytics(cells, scopeLabel) {
  const stats = summarize(cells);
  renderKpis('kpi-row', stats);
  renderCharts(cells);
  const el = document.getElementById('analytics-scope');
  if (el) el.textContent = `${scopeLabel} · ${stats.n.toLocaleString()} cells`;
}
