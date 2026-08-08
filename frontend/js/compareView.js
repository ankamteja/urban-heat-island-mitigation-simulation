let mapBefore, mapAfter;
let currentBeforeLayer = null;
let currentAfterLayer = null;

function applyIntervention(geojson) {
  const transformed = JSON.parse(JSON.stringify(geojson));
  transformed.features.forEach(f => {
    if (f.properties.recommended_action !== 'None') {
      f.properties.temperature = +(f.properties.temperature - 3).toFixed(1);
    }
  });
  return transformed;
}

function initCompareView(geojson) {
  mapBefore = initMap('map-before', [26.165, 91.745]);
  mapAfter = initMap('map-after', [26.165, 91.745]);

  renderCompareLayers(geojson);
  syncMaps(mapBefore, mapAfter);
  addGeocoder(mapBefore);

  window.addEventListener('resize', () => {
    mapBefore.invalidateSize();
    mapAfter.invalidateSize();
  });
}

function renderCompareLayers(geojson) {
  if (currentBeforeLayer) mapBefore.removeLayer(currentBeforeLayer);
  if (currentAfterLayer) mapAfter.removeLayer(currentAfterLayer);

  const afterGeojson = applyIntervention(geojson);
  currentBeforeLayer = renderGridLayer(mapBefore, geojson);
  currentAfterLayer = renderGridLayer(mapAfter, afterGeojson);
}

function syncMaps(mapA, mapB) {
  let syncing = false;
  function sync(source, target) {
    if (syncing) return;
    syncing = true;
    target.setView(source.getCenter(), source.getZoom(), { animate: false });
    syncing = false;
  }
  mapA.on('move', () => sync(mapA, mapB));
  mapB.on('move', () => sync(mapB, mapA));
}

function addGeocoder(map) {
  L.Control.geocoder({ defaultMarkGeocode: true }).addTo(map);
}

function applyIntervention(geojson) {
  const transformed = JSON.parse(JSON.stringify(geojson));
  transformed.features.forEach(f => {
    const action = f.properties.recommended_action;
    const temp = f.properties.temperature;

    if (action && action !== 'None' && typeof temp === 'number') {
      f.properties.temperature = +(temp - 3).toFixed(1);
    }
  });
  return transformed;
}