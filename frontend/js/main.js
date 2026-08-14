/* Bootstrap. */

const DATA_SOURCES = ['data/grid.geojson', 'mock_data/grid.geojson'];

initChartDefaults();

loadGrid(DATA_SOURCES)
  .then(data => {
    initCompareView(data);
    renderLegend('legend');
    renderTopbarStats(data.cells);
    setupFilters(data.cells, renderCompareLayers);
    setupAnalyticsToggle(data.cells);
    updateAnalytics(data.cells, 'Whole study area');
    dismissBoot();
  })
  .catch(err => {
    console.error(err);
    const sub = document.getElementById('boot-sub');
    sub.textContent = 'Could not load the thermal grid. Serve this folder over HTTP, then reload.';
    sub.classList.add('is-error');
  });

function dismissBoot() {
  requestAnimationFrame(() => document.getElementById('boot').classList.add('is-done'));
}

function renderTopbarStats(cells) {
  const s = summarize(cells);
  document.getElementById('topbar-stats').innerHTML = `
    <div class="tstat"><b>${s.n.toLocaleString()}</b><span>grid cells</span></div>
    <div class="tstat"><b>${s.meanTemp.toFixed(1)}°C</b><span>mean LST</span></div>
    <div class="tstat"><b>${s.maxTemp.toFixed(1)}°C</b><span>hotspot peak</span></div>
    <div class="tstat"><b>${s.meanNdvi.toFixed(3)}</b><span>mean NDVI</span></div>`;
}

function setupAnalyticsToggle() {
  const btn = document.getElementById('btn-analytics');
  const panel = document.getElementById('analytics');
  const close = document.getElementById('btn-analytics-close');

  function set(open) {
    panel.hidden = !open;
    btn.setAttribute('aria-expanded', String(open));
    if (open) panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    setTimeout(() => {
      view.mapBefore && view.mapBefore.invalidateSize();
      view.mapAfter && view.mapAfter.invalidateSize();
    }, 340);
  }

  btn.addEventListener('click', () => set(panel.hidden));
  close.addEventListener('click', () => set(false));
}
