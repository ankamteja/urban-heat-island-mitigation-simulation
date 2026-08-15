/* Bootstrap. */

/* One source. There used to be a fallback to a hand-written mock grid of 900
   synthetic cells spanning a fabricated 28-42 C. If the real fetch ever failed
   the dashboard would quietly render invented numbers as though they were
   measurements, which is worse than showing nothing. The mock is gone; a failed
   fetch now surfaces the error below. */
const RELEASE_MANIFEST = 'data/release.json';

initChartDefaults();

loadCurrentGrid()
  .then(data => {
    initCompareView(data);
    renderLegend('legend', setHeatMode, view.heatMode);
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

async function loadCurrentGrid() {
  const manifestResponse = await fetch(RELEASE_MANIFEST, { cache: 'no-store' });
  if (!manifestResponse.ok) {
    throw new Error(`Could not load release manifest (${manifestResponse.status})`);
  }
  const release = await manifestResponse.json();
  if (!release.grid_sha256 || !/^[a-f0-9]{64}$/.test(release.grid_sha256)) {
    throw new Error('Release manifest has no valid grid checksum');
  }
  const data = await loadGrid(`data/grid.geojson?release=${release.grid_sha256}`);
  data.release = release;
  document.body.dataset.gridRelease = release.release_id || release.grid_sha256.slice(0, 12);
  return data;
}

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
