loadGrid('mock_data/grid.geojson')
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