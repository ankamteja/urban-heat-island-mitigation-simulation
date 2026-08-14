// Real pipeline output: 8,144 Guwahati cells, produced by
// `Machine Learning & Prediction/scripts/export_grid_geojson.py` and copied
// here. Swap to 'mock_data/grid.geojson' for 900 synthetic cells if you want
// to work offline — the dashboard handles both.
loadGrid('data/grid.geojson')
  .then(geojson => {
    initCompareView(geojson);
    renderLegend('legend');
    setupFilters(geojson, renderCompareLayers);
    hideLoadingScreen();
  })
  .catch(err => {
    console.error(err);
    showLoadingError();
  });

function hideLoadingScreen() {
  const el = document.getElementById('loading-screen');
  el.classList.add('hidden');
}

function showLoadingError() {
  const el = document.getElementById('loading-screen');
  el.textContent = 'Failed to load map data. Check console for details.';
  el.style.color = '#c0392b';
}