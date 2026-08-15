/* Map bootstrap, basemap, legend. */

const BASEMAP = {
  url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
  subdomains: 'abcd',
  maxZoom: 19
};

function initMap(containerId, center, zoom) {
  const map = L.map(containerId, {
    center,
    zoom: zoom || 13,
    zoomControl: false,
    attributionControl: true,
    preferCanvas: true
  });

  /* Controls live on the right so they never sit under the pane label. */
  if (containerId === 'map-before') L.control.zoom({ position: 'topright' }).addTo(map);

  L.tileLayer(BASEMAP.url, BASEMAP).addTo(map);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd', maxZoom: 19, pane: 'shadowPane', opacity: 0.75
  }).addTo(map);

  setTimeout(() => map.invalidateSize(), 60);
  return map;
}

const LAYER_MODES = {
  field: {
    label: 'Blended',
    hint: 'Land surface temperature, blended across the 100 m grid.',
    icon: '<path d="M4 12c0-3 2.5-5 5-4.5C10 4.5 12.5 3 15 4.5S19 8 18.5 11 15 16 11 15.5 4 15 4 12z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'
  },
  grid: {
    label: 'Grid cells',
    hint: 'The raw 100 m cells the blend is smoothing over. Same ramp, lighter.',
    icon: '<path d="M3.5 3.5h13v13h-13zM8 3.5v13M12 3.5v13M3.5 8h13M3.5 12h13" fill="none" stroke="currentColor" stroke-width="1.3"/>'
  }
};

/* The ramp doubles as the layer switch: the thing that explains the colour is
   also the thing that changes how the colour is drawn. */
function renderLegend(containerId, onModeChange, initialMode) {
  const el = document.getElementById(containerId);
  const mid = (TEMP_DOMAIN.min + TEMP_DOMAIN.max) / 2;
  const active = LAYER_MODES[initialMode] ? initialMode : 'field';

  const buttonFor = key => {
    const m = LAYER_MODES[key];
    const on = key === active;
    return `<button type="button" class="filter-btn${on ? ' is-active' : ''}" data-mode="${key}" aria-pressed="${on}">
        <svg viewBox="0 0 20 20" aria-hidden="true">${m.icon}</svg><span>${m.label}</span>
      </button>`;
  };

  el.innerHTML = `
    <div class="legend-ramp" role="img" aria-label="Colour ramp from ${TEMP_DOMAIN.min} to ${TEMP_DOMAIN.max} degrees Celsius"></div>
    <div class="legend-scale">
      <span>${TEMP_DOMAIN.min}°C</span><span>${mid}°C</span><span>${TEMP_DOMAIN.max}°C</span>
    </div>
    <div class="segmented is-pair legend-modes" role="group" aria-label="Heat layer rendering">
      ${buttonFor('field')}${buttonFor('grid')}
    </div>
    <p class="panel-hint" data-legend-hint>${LAYER_MODES[active].hint}</p>
  `;

  const buttons = Array.from(el.querySelectorAll('.legend-modes .filter-btn'));
  const hint = el.querySelector('[data-legend-hint]');

  for (const btn of buttons) {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      for (const b of buttons) {
        const on = b === btn;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-pressed', String(on));
      }
      hint.textContent = LAYER_MODES[mode].hint;
      if (onModeChange) onModeChange(mode);
    });
  }
}

function addGeocoder(map) {
  if (L.Control.geocoder) L.Control.geocoder({ defaultMarkGeocode: true, position: 'topright' }).addTo(map);
}

/* Keeps the two maps on the same view without feedback loops. */
function syncMaps(a, b) {
  let lock = false;
  const link = (src, dst) => () => {
    if (lock) return;
    lock = true;
    dst.setView(src.getCenter(), src.getZoom(), { animate: false });
    lock = false;
  };
  a.on('move zoom', link(a, b));
  b.on('move zoom', link(b, a));
}
