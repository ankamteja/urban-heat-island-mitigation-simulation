const TEMP_COLOR_SCALE = [
  { max: 30, color: '#2c7bb6' },
  { max: 34, color: '#abd9e9' },
  { max: 38, color: '#fdae61' },
  { max: 100, color: '#d7191c' }
];

function colorByTemperature(temp) {
  const match = TEMP_COLOR_SCALE.find(step => temp <= step.max);
  return match ? match.color : '#d7191c';
}

function initMap(containerId, center, zoom = 15) {
  const map = L.map(containerId).setView(center, zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
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

function renderLegend(containerId) {
  const el = document.getElementById(containerId);
  const labels = ['< 30°C', '30–34°C', '34–38°C', '> 38°C'];
  el.innerHTML = TEMP_COLOR_SCALE.map((step, i) =>
    `<div><span style="background:${step.color}"></span>${labels[i]}</div>`
  ).join('');
}