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

function renderLegend(containerId) {
  const el = document.getElementById(containerId);
  const mid = (TEMP_DOMAIN.min + TEMP_DOMAIN.max) / 2;
  el.innerHTML = `
    <div class="legend-ramp" role="img" aria-label="Colour ramp from ${TEMP_DOMAIN.min} to ${TEMP_DOMAIN.max} degrees Celsius"></div>
    <div class="legend-scale">
      <span>${TEMP_DOMAIN.min}°C</span><span>${mid}°C</span><span>${TEMP_DOMAIN.max}°C</span>
    </div>
    <p class="panel-hint">Land surface temperature, blended across the 100 m grid.</p>
  `;
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
