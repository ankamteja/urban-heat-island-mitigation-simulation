# Urban Heat Island Mitigation Simulation - Guwahati

## Project Overview

Urban Heat Island (UHI) is a phenomenon where urban regions experience higher temperatures compared to surrounding rural areas due to increased built-up surfaces, reduced vegetation, and human activities.

This project focuses on analysing the Urban Heat Island effect in **Guwahati, Assam, India** using satellite remote sensing data and geospatial analysis.

The main objective is to identify heat-risk regions by integrating:

- Land Surface Temperature (LST)
- Normalized Difference Vegetation Index (NDVI)
- Vegetation classification
- Land cover information
- Heat Risk Index
- Grid-based spatial analysis

The generated geospatial dataset provides detailed information about temperature variation, vegetation conditions, and heat intensity across the study area.

The output dataset can be used for:

- Machine Learning based heat prediction
- Urban planning
- Heat mitigation strategy development
- Future climate resilience studies


---

# Project Workflow

```
Satellite Data
        |
        |
Google Earth Engine Processing
        |
        |
Landsat Image Collection
        |
        |
LST + NDVI + Land Cover Analysis
        |
        |
100m Grid Generation
        |
        |
Feature Extraction
        |
        |
CSV Dataset Generation
        |
        |
Urban Heat Risk Analysis
```

---

# 1. Satellite Data Collection

Satellite data processing was performed using **Google Earth Engine (GEE)**.

## Dataset Used

- Satellite: Landsat 8 Collection 2 Level 2
- Data Source: Google Earth Engine
- Time Period:

```
January 2025 - December 2025
```

- Cloud Cover Filter:

```
< 20%
```

The satellite images were filtered based on the Guwahati boundary.

A median composite operation was applied to reduce:

- Cloud contamination
- Shadows
- Scene-level noise


---

# 2. Study Area

## Location

```
Guwahati, Assam, India
```

The Guwahati city boundary was imported into Google Earth Engine and used as the Region of Interest (ROI).

All satellite processing, grid generation, and feature extraction were performed inside this boundary.


---

# 3. Land Surface Temperature (LST) Analysis

Land Surface Temperature was calculated using the thermal infrared band from Landsat imagery.


## Thermal Band Used

```
ST_B10
```

## Processing Steps

1. Extract thermal band information
2. Apply Landsat scaling factors
3. Convert temperature values into Celsius
4. Generate temperature raster


## Formula

```
Temperature = ST_B10 × 0.00341802 + 149 - 273.15
```


## Output

Generated raster:

```
Results/temperature.tif
```


The temperature map represents the spatial distribution of surface temperature across Guwahati.


---

# 4. Vegetation Analysis (NDVI)

Vegetation density was analysed using the Normalized Difference Vegetation Index (NDVI).


## Formula

```
NDVI = (NIR - RED) / (NIR + RED)
```


## Landsat Bands Used

| Band | Description |
|------|-------------|
| SR_B5 | Near Infrared (NIR) |
| SR_B4 | Red |


## Interpretation

| NDVI Value | Meaning |
|------------|---------|
| High NDVI | Dense vegetation |
| Medium NDVI | Moderate vegetation |
| Low NDVI | Urban/bare surfaces |


## Output

Generated raster:

```
Results/ndvi.tif
```


---

# 5. Vegetation Classification

The NDVI values were converted into vegetation classes.

| NDVI Range | Vegetation Class |
|------------|------------------|
| < 0.2 | Low Vegetation |
| 0.2 - 0.5 | Moderate Vegetation |
| > 0.5 | High Vegetation |


This helps identify areas where vegetation can reduce urban heat intensity.


---

# 6. Land Cover Analysis

Land cover information was obtained using:

```
ESA WorldCover v200
```

The land cover layer provides surface classification information for the study area.

Examples:

- Built-up regions
- Vegetation areas
- Water bodies
- Other land classes


The land cover feature was extracted for every grid cell.


---

# 7. Heat Risk Index Calculation

The Urban Heat Risk Index was calculated by combining temperature and vegetation information.


## Formula

```
Heat Risk = Normalized Temperature - Normalized NDVI
```


## Interpretation

### High Heat Risk

Occurs when:

- Temperature is high
- Vegetation coverage is low


### Low Heat Risk

Occurs when:

- Temperature is lower
- Vegetation coverage is higher


The heat risk map highlights regions requiring potential heat mitigation strategies.


---

# 8. Grid-Based Spatial Analysis

The study region was divided into approximately:


```
100m × 100m Grid Cells
```


Each grid cell was treated as an individual analysis unit.


## Grid Features Extracted


| Feature | Description |
|---------|-------------|
| grid_id | Unique grid identifier |
| Latitude | Grid centroid latitude |
| Longitude | Grid centroid longitude |
| Temperature | Average land surface temperature |
| NDVI | Average vegetation index |
| Vegetation | Vegetation class |
| Land_Cover | Land cover category |
| Heat_Risk | Heat intensity value |


Total generated grid cells:

```
8144
```


---

# 9. Dataset Generation

The final dataset was exported from Google Earth Engine.


## Dataset File

```
Remote Sensing & Data Engineering/Dataset/dataset.csv
```


## Dataset Attributes

```
grid_id
Latitude
Longitude
Temperature
NDVI
Vegetation
Land_Cover
Heat_Risk
```


## Applications

The dataset can be used for:

- Machine Learning models
- Heat prediction
- Spatial analysis
- Urban planning
- Heat mitigation recommendations


---

# 10. Generated Outputs

The project generates the following outputs:


## CSV Dataset

```
Dataset/dataset.csv
```


Contains grid-wise extracted features.


---

## Grid Boundary File

```
```


Contains the generated spatial grid polygons.


---

## Temperature Raster

```
Results/temperature.tif
```


Contains Land Surface Temperature information.


---

## NDVI Raster

```
Results/ndvi.tif
```


Contains vegetation index information.


---

# Tools and Technologies Used


## Google Earth Engine

Used for:

- Satellite data collection
- Landsat image processing
- LST calculation
- NDVI calculation
- Heat risk generation
- Dataset export


---

## QGIS

Used for:

- Boundary visualization
- Raster visualization
- Spatial analysis
- Map inspection


---

## Python / Machine Learning (Future Extension)

The generated dataset can be further used for:

- Regression models
- Temperature prediction
- Heat-risk forecasting
- AI-based mitigation recommendations


---

# Project Structure


```
urban-heat-island-mitigation-simulation
│
├── README.md
│
└── Remote Sensing & Data Engineering
    │
    ├── Boundary
    │   └── Guwahati boundary data
    │
    ├── Dataset
    │   └── dataset.csv
    │
    ├── GEE
    │   └── urban_heat_analysis.js
    │
    ├── QGIS
    │   └── QGIS project files
    │
    ├── Results
    │   ├── grid.geojson
    │   ├── temperature.tif
    │   └── ndvi.tif
    │
    └── SPEC_AUDIT.md

```


---

# Results

The project successfully generates:

- Urban Heat Risk Analysis
- Land Surface Temperature Map
- NDVI Vegetation Map
- Grid-based Heat Dataset
- Spatial Heat Distribution Information


The analysis identifies areas with increased thermal stress and provides geospatial information useful for urban heat mitigation planning.


---

# Future Improvements

Future improvements include:

## Machine Learning Integration

- Heat prediction models
- Temperature forecasting
- Risk classification models


## Advanced Remote Sensing Analysis

- Improved land-use classification
- Multi-year temperature trend analysis
- Higher resolution satellite data integration


## Urban Heat Mitigation Simulation

Possible mitigation strategies:

- Tree plantation planning
- Green roof analysis
- Cool roof simulation
- Urban vegetation optimisation


## Application Development

Development of:

- Interactive heat-risk dashboard
- Real-time monitoring system
- Urban planning decision-support platform


---

# Author

**Nikhil Kumar Reddy**
