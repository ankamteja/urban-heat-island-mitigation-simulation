// ======================================================
// Urban Heat Risk Analysis - Guwahati
// Complete Workflow
// ======================================================
//
// Spec-compliance revision:
//   - Landsat C2 L2 surface reflectance is now rescaled
//     (x 0.0000275, -0.2) before NDVI / NDBI. The -0.2
//     offset does not cancel in a normalized difference,
//     so the previous raw-DN NDVI was badly compressed.
//   - Per-pixel QA_PIXEL cloud / cirrus / shadow mask is
//     applied before the median composite.
//   - NDBI added (SR_B6 / SR_B5).
//   - ESA WorldCover land cover + binary vegetation added.
//   - Latitude / Longitude added per grid cell.
//   - grid.geojson, temperature.tif and ndvi.tif exports
//     added alongside the CSV.
//
// Re-running this script in Google Earth Engine is what
// regenerates the corrected dataset and the deliverables;
// the exports land in the Drive of whoever runs it.
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
// 3. Per-Pixel Cloud and Shadow Mask
// ======================================================

// Scene-level CLOUD_COVER above still admits whole scenes
// at up to 20% cloud. This drops the clouded pixels too.

function maskL8(img) {
  var qa = img.select('QA_PIXEL');
  var mask = qa.bitwiseAnd(1 << 1).eq(0)   // dilated cloud
    .and(qa.bitwiseAnd(1 << 2).eq(0))      // cirrus
    .and(qa.bitwiseAnd(1 << 3).eq(0))      // cloud
    .and(qa.bitwiseAnd(1 << 4).eq(0));     // cloud shadow
  return img.updateMask(mask);
}



// ======================================================
// 4. Median Composite
// ======================================================

var image = landsat.map(maskL8).median();



// ======================================================
// 5. Land Surface Temperature (LST)
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
// 6. NDVI Calculation
// ======================================================

// Landsat C2 L2 surface reflectance -> physical reflectance
var sr = image
.select([
  'SR_B4',
  'SR_B5',
  'SR_B6'
])
.multiply(0.0000275)
.add(-0.2);


var ndvi = sr
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
// 7. NDBI Calculation
// ======================================================

var ndbi = sr
.normalizedDifference([
  'SR_B6',
  'SR_B5'
])
.rename('NDBI');


var ndbi_guwahati = ndbi.clip(guwahati);



print(
  "NDBI Statistics",
  ndbi_guwahati.reduceRegion({
    reducer: ee.Reducer.minMax(),
    geometry: guwahati,
    scale:30,
    maxPixels:1e9
  })
);



// ======================================================
// 8. Land Cover and Vegetation
// ======================================================

var worldcover = ee.ImageCollection('ESA/WorldCover/v200')
.first()
.select('Map')
.rename('LandCover')
.clip(guwahati);


// binary vegetation: WorldCover classes 10 (tree), 20 (shrub),
// 30 (grass), 40 (crop)
var vegetation = worldcover
.remap(
  [10,20,30,40],
  [1,1,1,1],
  0
)
.rename('Vegetation');



print(
  "Land Cover Statistics",
  worldcover.reduceRegion({
    reducer: ee.Reducer.frequencyHistogram(),
    geometry: guwahati,
    scale:30,
    maxPixels:1e9
  })
);



print(
  "Vegetation Statistics",
  vegetation.reduceRegion({
    reducer: ee.Reducer.minMax(),
    geometry: guwahati,
    scale:30,
    maxPixels:1e9
  })
);



// ======================================================
// 9. Normalize LST and NDVI
// ======================================================

// These bounds are now meaningful: with the surface
// reflectance rescale in section 6 the NDVI actually spans
// roughly -0.1 to 0.85, so unitScale(-0.2,0.8) is the right
// range rather than an over-wide one.

var lst_norm = lst_guwahati
.unitScale(20,34);


var ndvi_norm = ndvi_guwahati
.unitScale(-0.2,0.8);



// ======================================================
// 10. Heat Risk Index
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
// 11. Create 100m Grid
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
// 12. Extract Grid-wise Features
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



  var ndbi_value = ndbi_guwahati.reduceRegion({

    reducer:ee.Reducer.mean(),

    geometry:cell.geometry(),

    scale:30,

    maxPixels:1e9

  }).get('NDBI');



  // categorical band - the modal class, not a mean
  var landcover_value = worldcover.reduceRegion({

    reducer:ee.Reducer.mode(),

    geometry:cell.geometry(),

    scale:30,

    maxPixels:1e9

  }).get('LandCover');



  // mean of a 0/1 band = vegetated fraction of the cell
  var vegetation_value = vegetation.reduceRegion({

    reducer:ee.Reducer.mean(),

    geometry:cell.geometry(),

    scale:30,

    maxPixels:1e9

  }).get('Vegetation');



  var heat_value = heat_risk.reduceRegion({

    reducer:ee.Reducer.mean(),

    geometry:cell.geometry(),

    scale:30,

    maxPixels:1e9

  }).get('Heat_Risk');



  var c = cell.geometry().centroid(1).coordinates();



  return cell.set({

    'Longitude':c.get(0),

    'Latitude':c.get(1),

    'LST':lst_value,

    'NDVI':ndvi_value,

    'NDBI':ndbi_value,

    'LandCover':landcover_value,

    'Vegetation':vegetation_value,

    'Heat_Risk':heat_value

  });


});





// ======================================================
// 13. Preview Dataset
// ======================================================


print(
  "Sample Grid Dataset",
  grid_dataset.limit(5)
);



// ======================================================
// 14. Export CSV
// ======================================================


Export.table.toDrive({

  collection:grid_dataset,

  description:'dataset',

  fileFormat:'CSV'

});




// ======================================================
// 15. Export Grid GeoJSON
// ======================================================


Export.table.toDrive({

  collection:grid_dataset,

  description:'grid',

  fileFormat:'GeoJSON'

});




// ======================================================
// 16. Export Raster Deliverables
// ======================================================


Export.image.toDrive({

  image:lst_guwahati,

  description:'temperature',

  region:guwahati.geometry(),

  scale:30,

  crs:'EPSG:4326',

  maxPixels:1e13,

  fileFormat:'GeoTIFF'

});



Export.image.toDrive({

  image:ndvi_guwahati,

  description:'ndvi',

  region:guwahati.geometry(),

  scale:30,

  crs:'EPSG:4326',

  maxPixels:1e13,

  fileFormat:'GeoTIFF'

});




// ======================================================
// 17. Visualization
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
