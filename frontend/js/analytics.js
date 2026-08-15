/* Analytics.

   Three charts, each answering a question a planner would actually ask. The
   priority doughnut that used to sit here is gone: it showed the mix of a
   categorical field nobody acts on, which is the definition of a chart filling
   dashboard space (§10). */

const CHART_INK = '#9AA6BC';
const CHART_GRID = 'rgba(255,255,255,.06)';
const CHART_FONT = "'Inter', system-ui, sans-serif";
const charts = {};

function initChartDefaults() {
  if (!window.Chart) return;
  Chart.defaults.color = CHART_INK;
  Chart.defaults.borderColor = CHART_GRID;
  Chart.defaults.font.family = CHART_FONT;
  Chart.defaults.font.size = 11;
  Chart.defaults.animation.duration = 180;
  Chart.defaults.plugins.legend.labels.boxWidth = 9;
  Chart.defaults.plugins.legend.labels.boxHeight = 9;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.maintainAspectRatio = false;
}

function swap(key, canvasId, config) {
  if (charts[key]) charts[key].destroy();
  const el = document.getElementById(canvasId);
  if (!el) return;
  charts[key] = new Chart(el.getContext('2d'), config);
}

/* ── key metrics strip (below the map, per §3) ───────────────────────────── */

function renderMetrics() {
  const el = document.getElementById('metrics-strip');
  if (!el || !App.stats) return;
  const s = App.stats;

  const items = [
    { v: s.n.toLocaleString(), k: 'Cells in scope' },
    { v: degrees(s.meanTemp), k: 'Mean surface temp' },
    { v: degrees(s.maxTemp), k: 'Peak' },
    { v: s.eligible.toLocaleString(), k: 'Eligible for action' },
    { v: s.fundedCount.toLocaleString(), k: 'Funded at this budget', hi: true },
    { v: signedDrop(s.meanDrop), k: 'Mean reduction, all cells', hi: true },
    { v: inrCrore(s.fundedCost), k: 'Committed cost' },
    { v: inrCrore(s.eligibleCost), k: 'Cost if all treated' }
  ];

  el.innerHTML = items.map(i =>
    `<div class="metric${i.hi ? ' is-key' : ''}"><b>${i.v}</b><span>${i.k}</span></div>`
  ).join('');
}

/* ── charts ──────────────────────────────────────────────────────────────── */

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

/* Least-squares fit plus Pearson r. The line is only drawn when the
   relationship is strong enough to mean anything — a trend line through noise
   is a decorative diagonal that implies a finding the data does not support. */
function linearFit(points) {
  const n = points.length;
  if (n < 30) return null;
  let sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
  for (const p of points) {
    sx += p.x; sy += p.y; sxx += p.x * p.x; syy += p.y * p.y; sxy += p.x * p.y;
  }
  const den = n * sxx - sx * sx;
  if (!den) return null;
  const slope = (n * sxy - sx * sy) / den;
  const intercept = (sy - slope * sx) / n;
  const r = (n * sxy - sx * sy) /
    Math.sqrt(den * (n * syy - sy * sy));
  return { slope, intercept, r };
}

function renderCharts() {
  if (!window.Chart || !App.stats) return;

  const cells = App.scopeCells;
  const after = applyIntervention(cells, App.funded);

  /* 1 — distribution, current vs mitigation ------------------------------- */
  const BINS = 20;
  const lo = TEMP_DOMAIN.min, hi = TEMP_DOMAIN.max;
  const hBefore = histogram(cells, BINS, lo, hi);
  const hAfter = histogram(after, BINS, lo, hi);

  swap('dist', 'chart-dist', {
    type: 'bar',
    data: {
      labels: hBefore.counts.map((_, i) => (lo + i * hBefore.width).toFixed(1)),
      datasets: [
        { label: 'Current', data: hBefore.counts, backgroundColor: 'rgba(154,166,188,.45)' },
        { label: 'After plan', data: hAfter.counts, backgroundColor: 'rgba(94,158,126,.85)' }
      ]
    },
    options: {
      plugins: {
        tooltip: {
          callbacks: {
            title: it => `${it[0].label}–${(+it[0].label + hBefore.width).toFixed(1)} °C`
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 8, maxRotation: 0 },
             title: { display: true, text: 'Surface temperature (°C)' } },
        y: { grid: { color: CHART_GRID }, title: { display: true, text: 'cells' } }
      }
    }
  });

  /* 2 — vegetation against temperature ------------------------------------ */
  const step = Math.max(1, Math.ceil(cells.length / 1400));
  const pts = [];
  for (let i = 0; i < cells.length; i += step) {
    const c = cells[i];
    if (c.ndvi === null) continue;
    pts.push({ x: c.ndvi, y: c.temp });
  }
  const fit = linearFit(pts);
  const strong = fit && Math.abs(fit.r) >= 0.3;
  const xs = pts.length ? [Math.min(...pts.map(p => p.x)), Math.max(...pts.map(p => p.x))] : [0, 1];

  swap('ndvi', 'chart-ndvi', {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Grid cells',
          data: pts,
          backgroundColor: 'rgba(154,166,188,.4)',
          pointRadius: 2,
          pointHoverRadius: 4
        },
        ...(strong ? [{
          label: `Least-squares fit (r = ${fit.r.toFixed(2)})`,
          type: 'line',
          data: xs.map(x => ({ x, y: fit.intercept + fit.slope * x })),
          borderColor: '#E0A23C',
          borderWidth: 1.6,
          pointRadius: 0,
          fill: false
        }] : [])
      ]
    },
    options: {
      plugins: {
        tooltip: { callbacks: { label: it => ` NDVI ${it.parsed.x.toFixed(3)} · ${it.parsed.y.toFixed(1)} °C` } },
        subtitle: {
          display: !strong && !!fit,
          text: `No trend line drawn — r = ${fit ? fit.r.toFixed(2) : 'n/a'} is too weak to plot`,
          color: CHART_INK
        }
      },
      scales: {
        x: { grid: { color: CHART_GRID }, title: { display: true, text: 'NDVI' } },
        y: { grid: { color: CHART_GRID }, title: { display: true, text: '°C' } }
      }
    }
  });

  /* 3 — cost against cooling efficiency ----------------------------------- */
  /* The chart that explains the plan: cooling bought per crore, by measure.
     This is the ratio the optimiser actually sorts on, so it is the honest
     answer to "why did it pick those?". */
  const rows = (App.plan ? App.plan.rows : []).filter(r => r.available > 0);
  const eff = rows.map(r => {
    const meta = interventionMeta(r.action);
    const unitCost = r.availableCost / r.available;
    const unitCooling = INTERVENTIONS[r.action] ? interventionMeta(r.action).cooling : 0;
    return {
      label: meta.label,
      tint: meta.tint,
      /* °C per ₹ crore, at one cell's cost — comparable across measures. */
      perCrore: unitCost ? (unitCooling / unitCost) * 1e7 : 0,
      funded: r.count,
      available: r.available
    };
  }).sort((a, b) => b.perCrore - a.perCrore);

  swap('efficiency', 'chart-efficiency', {
    type: 'bar',
    data: {
      labels: eff.map(e => e.label),
      datasets: [{
        label: '°C per ₹1 Cr',
        data: eff.map(e => +e.perCrore.toFixed(1)),
        backgroundColor: eff.map(e => e.tint + 'd0'),
        borderWidth: 0
      }]
    },
    options: {
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: it => {
              const e = eff[it.dataIndex];
              return ` ${e.funded.toLocaleString()} of ${e.available.toLocaleString()} sites funded`;
            }
          }
        }
      },
      scales: {
        x: { grid: { color: CHART_GRID }, title: { display: true, text: '°C of cooling per ₹1 Cr' } },
        y: { grid: { display: false } }
      }
    }
  });
}

function renderAnalytics() {
  renderMetrics();
  const scope = document.getElementById('analytics-scope');
  if (scope && App.stats) {
    scope.textContent = `${scopeLabel()} · ${App.stats.n.toLocaleString()} cells`;
  }
  const panel = document.getElementById('analytics');
  if (panel && !panel.hidden) renderCharts();
}
