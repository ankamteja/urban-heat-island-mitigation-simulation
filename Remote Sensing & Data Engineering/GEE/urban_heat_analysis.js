// ======================================================
// Urban Heat Risk Analysis - Guwahati
// Complete Workflow
// ======================================================


// ======================================================
// 1. Load Guwahati Boundary
// ======================================================

var guwahati = ee.FeatureCollection(
  "projects/urban-heat-guwahati/assets/guwahati_boundary"
);


// ======================================================
// 2. Load Landsat 8 Data
// ======================================================

var landsat = ee.ImageCollection(
  "LANDSAT/LC08/C02/T1_L2"
)
.filterBounds(guwahati)
.filterDate(
  '2025-01-01',
  '2025-12-31'
)
.filter(
  ee.Filter.lt('CLOUD_COVER',20)
);


print(
  "Number of Landsat Images:",
  landsat.size()
);



// ======================================================
// 3. Median Composite
// ======================================================

var image = landsat.median();



// ======================================================
// 4. Land Surface Temperature (LST)
// ======================================================

var lst = image
.select('ST_B10')
.multiply(0.00341802)
.add(149.0)
.subtract(273.15)
.rename('LST');


var lst_guwahati = lst.clip(guwahati);



print(
  "LST Statistics",
  lst_guwahati.reduceRegion({
    reducer: ee.Reducer.minMax(),
    geometry: guwahati,
    scale:30,
    maxPixels:1e9
  })
);



// ======================================================
// 5. NDVI Calculation
// ======================================================

var ndvi = image
.normalizedDifference([
  'SR_B5',
  'SR_B4'
])
.rename('NDVI');


var ndvi_guwahati = ndvi.clip(guwahati);



print(
  "NDVI Statistics",
  ndvi_guwahati.reduceRegion({
    reducer: ee.Reducer.minMax(),
    geometry: guwahati,
    scale:30,
    maxPixels:1e9
  })
);



// ======================================================
// 6. Normalize LST and NDVI
// ======================================================

var lst_norm = lst_guwahati
.unitScale(20,34);


var ndvi_norm = ndvi_guwahati
.unitScale(-0.2,0.8);



// ======================================================
// 7. Heat Risk Index
// ======================================================

var heat_risk = lst_norm
.subtract(ndvi_norm)
.rename('Heat_Risk');



print(
  "Heat Risk Statistics",
  heat_risk.reduceRegion({
    reducer: ee.Reducer.minMax(),
    geometry: guwahati,
    scale:30,
    maxPixels:1e9
  })
);



// ======================================================
// 8. Create 100m Grid
// ======================================================

var grid = ee.Image.random()
.multiply(100000)
.toInt()
.reduceToVectors({

  geometry: guwahati.geometry(),

  scale:100,

  geometryType:'polygon',

  eightConnected:false,

  labelProperty:'grid_id',

  reducer:ee.Reducer.countEvery()

});


var guwahati_grid = grid.map(function(feature){

  return feature.set({

    'grid_id':feature.id()

  });

});



print(
  "Number of Grid Cells:",
  guwahati_grid.size()
);



// ======================================================
// 9. Extract Grid-wise Features
// ======================================================


var grid_dataset = guwahati_grid.map(function(cell){


  var lst_value = lst_guwahati.reduceRegion({

    reducer:ee.Reducer.mean(),

    geometry:cell.geometry(),

    scale:30,

    maxPixels:1e9

  }).get('LST');



  var ndvi_value = ndvi_guwahati.reduceRegion({

    reducer:ee.Reducer.mean(),

    geometry:cell.geometry(),

    scale:30,

    maxPixels:1e9

  }).get('NDVI');



  var heat_value = heat_risk.reduceRegion({

    reducer:ee.Reducer.mean(),

    geometry:cell.geometry(),

    scale:30,

    maxPixels:1e9

  }).get('Heat_Risk');



  return cell.set({

    'LST':lst_value,

    'NDVI':ndvi_value,

    'Heat_Risk':heat_value

  });


});





// ======================================================
// 10. Preview Dataset
// ======================================================


print(
  "Sample Grid Dataset",
  grid_dataset.limit(5)
);



// ======================================================
// 11. Export CSV
// ======================================================


Export.table.toDrive({

  collection:grid_dataset,

  description:'Guwahati_Urban_Heat_Dataset',

  fileFormat:'CSV'

});




// ======================================================
// 12. Visualization
// ======================================================


Map.addLayer(

  heat_risk,

  {

    min:0,

    max:0.6,

    palette:[

      '006400',

      'ffff00',

      'ff9900',

      'ff0000',

      '800000'

    ]

  },

  'Urban Heat Risk Map'

);



Map.addLayer(

  guwahati,

  {

    color:'black'

  },

  'Guwahati Boundary'

);



// Grid display (optional)

Map.addLayer(

  guwahati_grid,

  {

    color:'white'

  },

  '100m Grid'

);



Map.centerObject(

  guwahati,

  12

);