// Breakpoints tuned for the real Guwahati grid: 20.9–33.1°C, median 27.3, p99 30.2.
// The last band's max is a sentinel, not a real temperature.
const TEMP_COLOR_SCALE = [
  { max: 24, color: '#2c7bb6' },
  { max: 27, color: '#abd9e9' },
  { max: 30, color: '#fdae61' },
  { max: 100, color: '#d7191c' }
];

function colorByTemperature(temp) {
  if (typeof temp !== 'number' || isNaN(temp)) return '#999999';
  const match = TEMP_COLOR_SCALE.find(step => temp <= step.max);
  return match ? match.color : '#d7191c';
}

function initMap(containerId, center, zoom = 15) {
  const map = L.map(containerId).setView(center, zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  setTimeout(() => map.invalidateSize(), 100);

  return map;
}

function renderGridLayer(map, geojson) {
  return L.geoJSON(geojson, {
    style: feature => ({
      fillColor: colorByTemperature(feature.properties.temperature),
      fillOpacity: 0.65,
      color: '#333',
      weight: 0.5
    }),
    onEachFeature: (feature, layer) => {
      layer.bindPopup(buildPopupContent(feature.properties));
    }
  }).addTo(map);
}

function legendLabel(step, i) {
  if (i === 0) return `< ${step.max}°C`;
  if (i === TEMP_COLOR_SCALE.length - 1) return `> ${TEMP_COLOR_SCALE[i - 1].max}°C`;
  return `${TEMP_COLOR_SCALE[i - 1].max}–${step.max}°C`;
}

function renderLegend(containerId) {
  const el = document.getElementById(containerId);
  el.innerHTML = TEMP_COLOR_SCALE.map((step, i) =>
    `<div><span style="background:${step.color}"></span>${legendLabel(step, i)}</div>`
  ).join('');
}