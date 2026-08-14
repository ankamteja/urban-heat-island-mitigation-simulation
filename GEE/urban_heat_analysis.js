// ======================================================
// Urban Heat Risk Analysis - Guwahati
// FIXED per spec-compliance audit (2026-08-07)
// Changes vs original:
//   A. NDVI now uses correctly rescaled surface reflectance (was raw DN - biased low)
//   B. Per-pixel cloud/shadow mask added (was scene-level CLOUD_COVER filter only)
//   C. NDBI added (was missing, spec optional item)
//   D. Land cover + vegetation fraction added via ESA WorldCover (was missing entirely)
//   E. Latitude/Longitude columns added per grid cell (was missing - only in .geo)
//   F. grid.geojson export added (was missing)
//   G. temperature.tif and ndvi.tif exports added (was missing)
//   H. CSV export renamed to match spec filename
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
// [FIX B] Per-pixel cloud / shadow / cirrus mask
// The original CLOUD_COVER<20 filter is scene-level only: a scene at 19%
// cloud is admitted whole, clouded pixels included. This masks out actual
// bad pixels before compositing.
// ======================================================
 
function maskL8(img) {
  var qa = img.select('QA_PIXEL');
  var mask = qa.bitwiseAnd(1 << 1).eq(0)   // dilated cloud
    .and(qa.bitwiseAnd(1 << 2).eq(0))      // cirrus
    .and(qa.bitwiseAnd(1 << 3).eq(0))      // cloud
    .and(qa.bitwiseAnd(1 << 4).eq(0));     // cloud shadow
  return img.updateMask(mask);
}
 
var landsat_masked = landsat.map(maskL8);
 
 
// ======================================================
// 3. Median Composite
// ======================================================
 
var image = landsat_masked.median();
 
 
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
// [FIX A] NDVI - rescale surface reflectance BEFORE the normalized difference.
// Original ran on raw DN values. The x0.0000275 multiplier cancels out in a
// ratio, but the -0.2 additive offset does NOT, which compressed every NDVI
// value toward zero (observed max 0.386 instead of the expected ~0.8).
// ======================================================
 
var sr = image.select(['SR_B4', 'SR_B5', 'SR_B6'])
              .multiply(0.0000275)
              .add(-0.2);
 
var ndvi = sr.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI');
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
// [FIX C] NDBI (Normalized Difference Built-up Index) - spec optional item
// ======================================================
 
var ndbi = sr.normalizedDifference(['SR_B6', 'SR_B5']).rename('NDBI');
var ndbi_guwahati = ndbi.clip(guwahati);
 
 
// ======================================================
// [FIX D] Land cover + vegetation fraction via ESA WorldCover
// This is the piece Member 3 (Decision Support) needs for suitability rules
// like "no ponds on highways" - without it they can only use an NDVI-based
// proxy that can't tell a road from a building.
// ======================================================
 
var worldcover = ee.ImageCollection('ESA/WorldCover/v200').first()
                   .select('Map').rename('LandCover').clip(guwahati);
 
// WorldCover classes: 10 tree, 20 shrub, 30 grassland, 40 cropland, 50 built-up,
// 60 bare/sparse, 70 snow/ice, 80 water, 90 wetland/herbaceous, 95 mangroves, 100 moss/lichen
var vegetation = worldcover.remap(
  [10, 20, 30, 40, 50, 60, 80, 90],
  [1,  1,  1,  1,  0,  0,  0,  1],
  0
).rename('Vegetation');
 
 
// ======================================================
// 6. Normalize LST and NDVI
// [FIX A follow-on] bounds widened for the corrected NDVI range
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
// [FIX D] LandCover (mode - it's categorical) and Vegetation (mean fraction) added
// [FIX E] Latitude/Longitude centroid added
// ======================================================
 
 
var grid_dataset = guwahati_grid.map(function(cell){
 
  var geom = cell.geometry();
 
  var lst_value = lst_guwahati.reduceRegion({
    reducer:ee.Reducer.mean(),
    geometry:geom,
    scale:30,
    maxPixels:1e9
  }).get('LST');
 
  var ndvi_value = ndvi_guwahati.reduceRegion({
    reducer:ee.Reducer.mean(),
    geometry:geom,
    scale:30,
    maxPixels:1e9
  }).get('NDVI');
 
  var ndbi_value = ndbi_guwahati.reduceRegion({
    reducer:ee.Reducer.mean(),
    geometry:geom,
    scale:30,
    maxPixels:1e9
  }).get('NDBI');
 
  var heat_value = heat_risk.reduceRegion({
    reducer:ee.Reducer.mean(),
    geometry:geom,
    scale:30,
    maxPixels:1e9
  }).get('Heat_Risk');
 
  // [FIX D] land cover: mode (categorical - mean is meaningless for class codes)
  var landcover_value = worldcover.reduceRegion({
    reducer:ee.Reducer.mode(),
    geometry:geom,
    scale:10,
    maxPixels:1e9
  }).get('LandCover');
 
  // [FIX D] vegetation: mean fraction of the cell that is vegetated
  var vegetation_value = vegetation.reduceRegion({
    reducer:ee.Reducer.mean(),
    geometry:geom,
    scale:10,
    maxPixels:1e9
  }).get('Vegetation');
 
  // [FIX E] centroid lat/lon
  var c = geom.centroid(1).coordinates();
 
  return cell.set({
 
    'LST':lst_value,
    'NDVI':ndvi_value,
    'NDBI':ndbi_value,
    'Heat_Risk':heat_value,
    'LandCover':landcover_value,
    'Vegetation':vegetation_value,
    'Longitude': c.get(0),
    'Latitude': c.get(1)
 
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
// [FIX H] filename now matches spec ('dataset' instead of descriptive name)
// ======================================================
 
 
Export.table.toDrive({
 
  collection:grid_dataset,
 
  description:'dataset',
 
  fileFormat:'CSV'
 
});
 
 
// ======================================================
// [FIX F] Export grid.geojson - was missing entirely, embedded geometry
// in the CSV .geo column is not a substitute per spec
// ======================================================
 
Export.table.toDrive({
  collection: grid_dataset,
  description: 'grid',
  fileFormat: 'GeoJSON'
});
 
 
// ======================================================
// [FIX G] Export temperature.tif and ndvi.tif - spec deliverables, were missing
// ======================================================
 
Export.image.toDrive({
  image: lst_guwahati,
  description: 'temperature',
  region: guwahati.geometry(),
  scale: 30,
  crs: 'EPSG:4326',
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF'
});
 
Export.image.toDrive({
  image: ndvi_guwahati,
  description: 'ndvi',
  region: guwahati.geometry(),
  scale: 30,
  crs: 'EPSG:4326',
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF'
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