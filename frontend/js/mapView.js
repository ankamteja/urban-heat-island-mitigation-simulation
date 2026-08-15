/* The map: basemap, the two thermal surfaces, intervention symbology, layer
   control, legend, and the Current -> Mitigation divider.

   One map, not two. The brief makes the map the product (§3), and a single
   canvas that wipes between current and mitigated states shows the change far
   better than two small maps the eye has to compare by memory. */

const BASEMAP = {
  url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
  subdomains: 'abcd',
  maxZoom: 19
};

const LABELS_URL = 'https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png';

const mapView = {
  map: null,
  labels: null,
  current: null,      // HeatField, observed surface
  mitigated: null,    // HeatField, post-plan surface
  sites: null,        // funded intervention symbols
  selector: null
};

function initMap(containerId, center) {
  const map = L.map(containerId, {
    center,
    zoom: 13,
    zoomControl: false,
    attributionControl: true,
    preferCanvas: true,
    zoomSnap: 0.5
  });

  L.control.zoom({ position: 'topright' }).addTo(map);
  L.tileLayer(BASEMAP.url, BASEMAP).addTo(map);

  /* Labels ride above the thermal surface so place names stay readable through
     it — the planner has to know which ward they are looking at. */
  mapView.labels = L.tileLayer(LABELS_URL, {
    subdomains: 'abcd', maxZoom: 19, pane: 'shadowPane', opacity: 0.9
  }).addTo(map);

  mapView.map = map;
  setTimeout(() => map.invalidateSize(), 60);
  return map;
}

/* ── the two surfaces ────────────────────────────────────────────────────── */

function initSurfaces(cells) {
  mapView.current = heatField(cells).addTo(mapView.map);
  mapView.mitigated = heatField(cells).addTo(mapView.map);
  mapView.sites = siteLayer([]).addTo(mapView.map);

  mapView.map.on('move zoom resize zoomend moveend', applyCompareClip);
  applyCompareClip();
}

/* Clip the two canvases against a screen-space divider.

   clip-path rather than redrawing: the divider has to stay put while the map
   pans underneath it, and re-splatting 8,144 cells on every move frame would
   not hold 60fps. The canvases are transformed by Leaflet, so the divider is
   converted from map-container space into each canvas's own box on the way. */
function applyCompareClip() {
  const el = mapView.map && mapView.map.getContainer();
  if (!el || !mapView.current || !mapView.mitigated) return;

  const mapRect = el.getBoundingClientRect();
  const divX = mapRect.left + mapRect.width * App.compare;

  const clip = (field, side) => {
    const canvas = field._canvas;
    if (!canvas) return;
    const r = canvas.getBoundingClientRect();
    if (!r.width) return;
    const local = divX - r.left;
    canvas.style.clipPath = side === 'left'
      ? `inset(0 ${Math.max(0, r.width - local)}px 0 0)`
      : `inset(0 0 0 ${Math.max(0, local)}px)`;
  };

  clip(mapView.current, 'left');
  clip(mapView.mitigated, 'right');
}

/* Repaint both surfaces from state. Called on every plan change. */
function renderSurfaces() {
  if (!mapView.current) return;

  const cells = App.scopeCells;
  mapView.current.setMode(App.heatMode).setCells(App.layers.temperature ? cells : []);
  mapView.mitigated
    .setMode(App.heatMode)
    .setCells(App.layers.temperature ? applyIntervention(cells, App.funded) : []);

  const funded = App.layers.interventions
    ? cells.filter(c => App.funded.has(c.id))
    : [];
  mapView.sites.setCells(funded);

  if (mapView.labels) {
    const on = App.layers.labels;
    if (on && !mapView.map.hasLayer(mapView.labels)) mapView.labels.addTo(mapView.map);
    if (!on && mapView.map.hasLayer(mapView.labels)) mapView.map.removeLayer(mapView.labels);
  }

  applyCompareClip();
}

/* ── funded-site symbology ───────────────────────────────────────────────── */

/* A canvas layer rather than one Leaflet marker per cell: at the ₹100 Cr
   scenario the plan funds ~2,500 sites, and that many DOM markers stalls the
   map on every pan. Squares, not pins — this is a layer symbol in the GIS
   sense, and it sits over its own cell rather than floating above it. */
const SiteLayer = L.Layer.extend({
  initialize(cells) { this._cells = cells || []; },

  onAdd(map) {
    this._map = map;
    const canvas = this._canvas = L.DomUtil.create('canvas', 'site-layer');
    canvas.style.position = 'absolute';
    canvas.style.pointerEvents = 'none';
    this._ctx = canvas.getContext('2d');
    map.getPanes().overlayPane.appendChild(canvas);
    map.on('moveend zoomend resize', this._reset, this);
    this._reset();
    return this;
  },

  onRemove(map) {
    map.off('moveend zoomend resize', this._reset, this);
    if (this._canvas && this._canvas.parentNode) {
      this._canvas.parentNode.removeChild(this._canvas);
    }
    this._canvas = this._ctx = this._map = null;
    return this;
  },

  setCells(cells) {
    this._cells = cells || [];
    if (this._map) this._reset();
    return this;
  },

  _reset() {
    const map = this._map;
    if (!map) return;
    const size = map.getSize();
    const canvas = this._canvas;
    canvas.width = size.x;
    canvas.height = size.y;
    canvas.style.width = size.x + 'px';
    canvas.style.height = size.y + 'px';
    L.DomUtil.setTransform(canvas, map.containerPointToLayerPoint([0, 0]), 1);
    this._draw(size.x, size.y);
  },

  _draw(w, h) {
    const ctx = this._ctx;
    const map = this._map;
    ctx.clearRect(0, 0, w, h);
    if (!this._cells.length) return;

    /* Below this zoom the sites are smaller than the symbol and the map turns
       into a field of identical dots that says nothing. Show a count instead by
       simply not drawing — the plan panel already carries the number. */
    const z = map.getZoom();
    const size = z >= 15 ? 9 : z >= 13.5 ? 6 : 4;
    if (z < 12) return;

    ctx.lineWidth = 1;
    for (const cell of this._cells) {
      const p = map.latLngToContainerPoint(L.latLng(cell.lat, cell.lon));
      if (p.x < -20 || p.y < -20 || p.x > w + 20 || p.y > h + 20) continue;
      const tint = interventionMeta(cell.action).tint;
      const x = Math.round(p.x - size / 2);
      const y = Math.round(p.y - size / 2);
      ctx.fillStyle = tint + 'cc';
      ctx.fillRect(x, y, size, size);
      ctx.strokeStyle = 'rgba(8,12,20,.85)';
      ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);
    }
  }
});

function siteLayer(cells) { return new SiteLayer(cells); }

/* ── legend ──────────────────────────────────────────────────────────────── */

function renderLegend(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const mid = (TEMP_DOMAIN.min + TEMP_DOMAIN.max) / 2;
  const stops = HEAT_RAMP.map(s => `${rampCss(s.t)} ${(s.t * 100).toFixed(0)}%`).join(',');

  /* Only measures the current budget actually funds. Listing a symbol for a
     measure that appears nowhere on the map is a legend describing a different
     map. */
  const funded = App.plan ? App.plan.rows.filter(r => r.count > 0) : [];
  const symbols = funded.map(r => {
    const m = interventionMeta(r.action);
    return `<li><span class="sym" style="background:${m.tint}"></span>${m.label}
      <b>${r.count.toLocaleString()}</b></li>`;
  }).join('');

  el.innerHTML = `
    <div class="legend-block">
      <p class="legend-title">Land surface temperature</p>
      <div class="ramp" style="background:linear-gradient(90deg,${stops})"
           role="img" aria-label="Sequential ramp, ${TEMP_DOMAIN.min} to ${TEMP_DOMAIN.max} degrees Celsius"></div>
      <div class="ramp-scale">
        <span>${TEMP_DOMAIN.min}</span><span>${mid}</span><span>${TEMP_DOMAIN.max} °C</span>
      </div>
    </div>
    ${symbols ? `<div class="legend-block">
      <p class="legend-title">Funded interventions</p>
      <ul class="legend-syms">${symbols}</ul>
    </div>` : ''}
  `;
}

/* ── layer control ───────────────────────────────────────────────────────── */

const LAYER_ROWS = [
  { key: 'temperature', label: 'Surface temperature' },
  { key: 'interventions', label: 'Funded interventions' },
  { key: 'labels', label: 'Place labels' }
];

function renderLayerControl(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;

  el.innerHTML = `
    <p class="ctl-title">Layers</p>
    ${LAYER_ROWS.map(r => `
      <label class="ctl-row">
        <input type="checkbox" data-layer="${r.key}" ${App.layers[r.key] ? 'checked' : ''}>
        <span>${r.label}</span>
      </label>`).join('')}
    <p class="ctl-title ctl-sep">Rendering</p>
    <div class="ctl-seg" role="group" aria-label="Thermal surface rendering">
      <button type="button" data-mode="field" class="${App.heatMode === 'field' ? 'is-on' : ''}" aria-pressed="${App.heatMode === 'field'}">Interpolated</button>
      <button type="button" data-mode="grid" class="${App.heatMode === 'grid' ? 'is-on' : ''}" aria-pressed="${App.heatMode === 'grid'}">100 m cells</button>
    </div>
  `;

  el.querySelectorAll('[data-layer]').forEach(input => {
    input.addEventListener('change', () => setLayer(input.dataset.layer, input.checked));
  });
  el.querySelectorAll('[data-mode]').forEach(btn => {
    btn.addEventListener('click', () => {
      setHeatMode(btn.dataset.mode);
      el.querySelectorAll('[data-mode]').forEach(b => {
        const on = b === btn;
        b.classList.toggle('is-on', on);
        b.setAttribute('aria-pressed', String(on));
      });
    });
  });
}

/* ── the Current -> Mitigation divider ───────────────────────────────────── */

function initCompareControl(handleId, mapId) {
  const handle = document.getElementById(handleId);
  const mapEl = document.getElementById(mapId);
  if (!handle || !mapEl) return;

  const place = () => { handle.style.left = (App.compare * 100) + '%'; };
  place();
  onStateChange(reason => { if (reason === 'compare') place(); });

  const move = clientX => {
    const r = mapEl.getBoundingClientRect();
    setCompare((clientX - r.left) / r.width);
  };

  let dragging = false;
  const down = e => {
    dragging = true;
    handle.setPointerCapture && handle.setPointerCapture(e.pointerId);
    e.preventDefault();
  };
  const up = e => {
    dragging = false;
    handle.releasePointerCapture && handle.releasePointerCapture(e.pointerId);
  };

  handle.addEventListener('pointerdown', down);
  handle.addEventListener('pointermove', e => { if (dragging) move(e.clientX); });
  handle.addEventListener('pointerup', up);
  handle.addEventListener('pointercancel', up);

  /* Keyboard: the comparison is the signature interaction, so it cannot be
     pointer-only. */
  handle.addEventListener('keydown', e => {
    const step = e.shiftKey ? 0.1 : 0.02;
    if (e.key === 'ArrowLeft') { setCompare(App.compare - step); e.preventDefault(); }
    if (e.key === 'ArrowRight') { setCompare(App.compare + step); e.preventDefault(); }
    if (e.key === 'Home') { setCompare(0); e.preventDefault(); }
    if (e.key === 'End') { setCompare(1); e.preventDefault(); }
  });
}

function addGeocoder(map) {
  if (L.Control.geocoder) {
    L.Control.geocoder({ defaultMarkGeocode: true, position: 'topright' }).addTo(map);
  }
}
