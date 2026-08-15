/* Bootstrap and wiring.

   One source of data. There used to be a fallback to a hand-written mock grid;
   if the real fetch failed the dashboard quietly rendered invented numbers as
   though they were measurements, which is worse than showing nothing. A failed
   fetch now surfaces the error. */

const RELEASE_MANIFEST = 'data/release.json';

initChartDefaults();

loadCurrentGrid()
  .then(data => {
    App.allCells = data.cells;
    App.bounds = data.bounds;
    App.center = data.center;

    initMap('map', data.center);
    mapView.map.fitBounds(L.latLngBounds(data.bounds), { padding: [24, 24] });
    initSurfaces(data.cells);
    addGeocoder(mapView.map);

    setupScopeControls();
    setupSelector();
    setupDrawers();
    setupMapInteraction();
    initCompareControl('compare-handle', 'map');
    renderLayerControl('layer-control');
    renderMethodology('method-body');

    /* One subscription drives the whole interface: state changes, everything
       re-reads. No panel keeps its own copy of a number. */
    onStateChange(renderAll);

    refresh('boot');
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
  App.release = release;
  document.body.dataset.gridRelease = release.release_id || release.grid_sha256.slice(0, 12);
  return data;
}

function dismissBoot() {
  requestAnimationFrame(() => document.getElementById('boot').classList.add('is-done'));
}

/* ── the single render pass ──────────────────────────────────────────────── */

function renderAll(reason) {
  /* The compare divider moves far more often than anything else and only needs
     the clip recomputed — repainting 8,144 cells per drag frame would not hold
     a frame budget. */
  if (reason === 'compare') { applyCompareClip(); return; }

  renderSurfaces();
  renderPlanner();
  renderScope();
  renderAnalytics();
  renderLegend('legend');
  updateAppbar();
}

function updateAppbar() {
  const cells = document.getElementById('meta-cells');
  if (cells && App.stats) cells.textContent = App.stats.n.toLocaleString();

  const scenario = document.getElementById('meta-scenario');
  if (scenario) {
    const preset = BUDGET_PRESETS.find(p => p.value === App.budget);
    scenario.textContent = App.plan && App.plan.count
      ? `Plan · ${preset ? preset.label : inrCrore(App.budget)}`
      : 'Current';
  }
}

/* ── map interaction ─────────────────────────────────────────────────────── */

function setupMapInteraction() {
  mapView.map.on('click', e => {
    if (mapView.selector && mapView.selector.isArmed()) return;
    /* Hit-test against whichever surface owns the clicked side of the divider,
       so a click always inspects the cell the user is actually looking at. */
    const container = mapView.map.getContainer().getBoundingClientRect();
    const onMitigatedSide =
      (e.originalEvent.clientX - container.left) / container.width > App.compare;
    const field = onMitigatedSide ? mapView.mitigated : mapView.current;
    const hit = field.cellAt(e.latlng);
    if (!hit) return;
    /* The mitigated field holds modified copies, so resolve back to the real
       record before anything reads a cost or a rank off it. */
    const cell = App.allCells.find(c => c.id === hit.id) || hit;
    openInspector(cell);
  });

  window.addEventListener('resize', debounce(() => {
    mapView.map.invalidateSize();
    applyCompareClip();
  }, 180));

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeInspector();
  });
}

function setupSelector() {
  const btn = document.getElementById('btn-select');
  const label = document.getElementById('btn-select-label');
  const region = document.getElementById('map-region');

  mapView.selector = createAreaSelector(mapView.map, region, {
    onStateChange(armed) {
      btn.classList.toggle('is-armed', armed);
      region.classList.toggle('is-arming', armed);
      label.textContent = armed ? 'Drag a box…' : (App.selection ? 'New area' : 'Select area');
    },
    onSelect(bounds) {
      const picked = cellsInBounds(App.allCells, bounds);
      if (picked.length < 4) {
        alertInline('That area holds too few grid cells — try a larger box.');
        return;
      }
      setSelection(bounds);
      mapView.map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 });
    }
  });

  btn.addEventListener('click', () => mapView.selector.toggle());
}

/* ── drawers ─────────────────────────────────────────────────────────────── */

function setupDrawers() {
  const wire = (btnId, panelId, closeId, onOpen) => {
    const btn = document.getElementById(btnId);
    const panel = document.getElementById(panelId);
    const close = document.getElementById(closeId);
    if (!btn || !panel) return;

    const set = open => {
      panel.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
      if (open && onOpen) onOpen();
      if (open) panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      setTimeout(() => {
        mapView.map.invalidateSize();
        applyCompareClip();
      }, 260);
    };

    btn.addEventListener('click', () => set(panel.hidden));
    if (close) close.addEventListener('click', () => set(false));
  };

  wire('btn-analytics', 'analytics', 'btn-analytics-close', renderCharts);
  wire('btn-method', 'method', 'btn-method-close', null);

  const exportBtn = document.getElementById('btn-export');
  if (exportBtn) exportBtn.addEventListener('click', exportReport);
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
