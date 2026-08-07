loadGrid('mock_data/grid.geojson')
  .then(geojson => {
    const map = initMap('map', [26.165, 91.745]);
    renderGridLayer(map, geojson);
    renderLegend('legend');
  })
  .catch(err => console.error(err));