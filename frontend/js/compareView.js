/* Orchestrates the two map panes.

   The planning-scenario pane stays collapsed until the user selects an area.
   It subtracts stated assumptions from LST; it is not a forecast. */

const view = {
  mapBefore: null,
  mapAfter: null,
  fieldBefore: null,
  fieldAfter: null,
  ecoLayer: null,
  selector: null,
  allCells: [],
  activeCells: [],
  selection: null,
  revealed: false,
  heatMode: 'field'
};

/* Both panes switch together — the two surfaces are only comparable while they
   are drawn the same way. */
function setHeatMode(mode) {
  view.heatMode = mode;
  if (view.fieldBefore) view.fieldBefore.setMode(mode);
  if (view.fieldAfter) view.fieldAfter.setMode(mode);
}

function initCompareView(data) {
  view.allCells = data.cells;
  view.activeCells = data.cells;

  view.mapBefore = initMap('map-before', data.center, 13);
  view.mapAfter = initMap('map-after', data.center, 13);
  view.mapBefore.fitBounds(L.latLngBounds(data.bounds), { padding: [10, 10] });

  view.fieldBefore = heatField(data.cells).addTo(view.mapBefore);
  view.fieldAfter = heatField([]).addTo(view.mapAfter);

  syncMaps(view.mapBefore, view.mapAfter);
  addGeocoder(view.mapBefore);

  view.mapBefore.on('click', e => {
    if (view.selector && view.selector.isArmed()) return;
    const cell = view.fieldBefore.cellAt(e.latlng);
    if (cell) openCellPopup(view.mapBefore, cell, { title: 'Current conditions' });
  });

  view.mapAfter.on('click', e => {
    const cell = view.fieldAfter.cellAt(e.latlng);
    if (cell) openCellPopup(view.mapAfter, cell, { title: 'Planning scenario' });
  });

  setupSelector();

  window.addEventListener('resize', debounce(() => {
    view.mapBefore.invalidateSize();
    view.mapAfter.invalidateSize();
  }, 180));
}

function setupSelector() {
  const btn = document.getElementById('btn-select');
  const label = document.getElementById('btn-select-label');
  const maps = document.getElementById('maps');

  view.selector = createAreaSelector(view.mapBefore, document.getElementById('pane-before'), {
    onStateChange(armed) {
      btn.classList.toggle('is-armed', armed);
      maps.classList.toggle('is-arming', armed);
      label.textContent = armed ? 'Drag a box…' : (view.selection ? 'New selection' : 'Select area');
    },
    onSelect(bounds) {
      applySelection(bounds);
    }
  });

  btn.addEventListener('click', () => view.selector.toggle());
}

function applySelection(bounds) {
  const picked = cellsInBounds(view.activeCells, bounds);

  if (picked.length < 4) {
    renderSelectionPanel(null, 'That area holds too few grid cells — try a larger box.');
    return;
  }

  view.selection = { bounds, cells: picked };

  const predicted = applyIntervention(picked);
  view.fieldAfter.setCells(predicted);

  revealPrediction();

  view.mapBefore.fitBounds(bounds, { padding: [24, 24], maxZoom: 16 });

  if (view.ecoLayer) { view.mapAfter.removeLayer(view.ecoLayer); view.ecoLayer = null; }
  const sites = deriveEcologySites(picked, { maxPerType: 6 });
  view.ecoLayer = renderEcologyMarkers(view.mapAfter, sites);
  renderEcologyLegend('ecology-legend', sites);
  document.getElementById('ecology-panel').hidden = sites.length === 0;

  renderSelectionPanel(picked);
  updateAnalytics(picked, 'Selected area');
}

function revealPrediction() {
  const pane = document.getElementById('pane-after');
  const divider = document.getElementById('map-divider');
  const lock = document.getElementById('pane-lock');

  divider.hidden = false;
  pane.classList.remove('is-hidden');
  pane.setAttribute('aria-hidden', 'false');
  lock.classList.add('is-off');
  view.revealed = true;

  setTimeout(() => {
    view.mapBefore.invalidateSize();
    view.mapAfter.invalidateSize();
    view.mapAfter.setView(view.mapBefore.getCenter(), view.mapBefore.getZoom(), { animate: false });
  }, 540);
}

function hidePrediction() {
  const pane = document.getElementById('pane-after');
  const divider = document.getElementById('map-divider');

  pane.classList.add('is-hidden');
  pane.setAttribute('aria-hidden', 'true');
  document.getElementById('pane-lock').classList.remove('is-off');
  divider.hidden = true;
  view.revealed = false;

  setTimeout(() => view.mapBefore.invalidateSize(), 540);
}

function clearSelection() {
  view.selection = null;
  view.fieldAfter.setCells([]);
  if (view.ecoLayer) { view.mapAfter.removeLayer(view.ecoLayer); view.ecoLayer = null; }
  view.selector.clearHighlight();
  document.getElementById('ecology-panel').hidden = true;
  document.getElementById('btn-select-label').textContent = 'Select area';
  hidePrediction();
  renderSelectionPanel(null);
  updateAnalytics(view.activeCells, 'Whole study area');
}

function renderSelectionPanel(cells, message) {
  const body = document.getElementById('selection-body');
  const deltaChip = document.getElementById('pane-after-delta');

  if (!cells) {
    body.className = 'selection-empty';
    body.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" class="empty-icon"><rect x="3.5" y="3.5" width="17" height="17" rx="2" fill="none" stroke="currentColor" stroke-width="1.4" stroke-dasharray="3 2.5"/></svg>
      <p>${message ? 'Selection too small.' : 'No area selected.'}</p>
      <p class="muted">${message || 'Drag a box on the map to view the planning scenario; cooling values are assumptions.'}</p>`;
    if (deltaChip) deltaChip.textContent = '';
    return;
  }

  const s = summarize(cells);
  body.className = '';
  body.innerHTML = `
    <div class="sel-grid">
      <div class="sel-cell"><b>${s.n.toLocaleString()}</b><span>cells</span></div>
      <div class="sel-cell"><b>${s.meanTemp.toFixed(1)}°C</b><span>mean now</span></div>
      <div class="sel-cell is-drop"><b>${s.meanAfter.toFixed(1)}°C</b><span>scenario mean</span></div>
      <div class="sel-cell is-drop"><b>−${s.meanDropTreated.toFixed(2)}°C</b><span>assumed drop, treated</span></div>
      <div class="sel-cell is-drop"><b>−${s.meanDrop.toFixed(2)}°C</b><span>assumed drop, all cells</span></div>
      <div class="sel-cell"><b>${s.treated.toLocaleString()}</b><span>actionable</span></div>
      <div class="sel-cell"><b>${inrShort(s.cost)}</b><span>cost if all treated</span></div>
    </div>
    <div class="sel-actions">
      <button class="btn btn-sm btn-ghost" type="button" id="btn-clear-sel">Clear</button>
      <button class="btn btn-sm btn-ghost" type="button" id="btn-zoom-sel">Zoom to</button>
    </div>`;

  document.getElementById('btn-clear-sel').addEventListener('click', clearSelection);
  document.getElementById('btn-zoom-sel').addEventListener('click', () => {
    if (view.selection) view.mapBefore.fitBounds(view.selection.bounds, { padding: [24, 24], maxZoom: 16 });
  });

  if (deltaChip) deltaChip.textContent = `−${s.meanDrop.toFixed(2)}°C avg over all cells`;
}

/* Priority filter feeds both the field and whatever selection is live. */
function renderCompareLayers(cells) {
  view.activeCells = cells;
  view.fieldBefore.setCells(cells);

  if (view.selection) {
    const picked = cellsInBounds(cells, view.selection.bounds);
    view.selection.cells = picked;
    view.fieldAfter.setCells(applyIntervention(picked));
    renderSelectionPanel(picked.length ? picked : null);
    updateAnalytics(picked.length ? picked : cells, picked.length ? 'Selected area' : 'Whole study area');
  } else {
    updateAnalytics(cells, 'Whole study area');
  }
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
