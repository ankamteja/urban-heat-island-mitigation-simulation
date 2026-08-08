# Urban Heat Island Dashboard — Frontend

Interactive split-screen map comparing current heat conditions vs. projected
temperatures after cooling interventions (trees, cool roofs, green parks).

## Running locally
cd frontend
py -m http.server

Open `http://localhost:8000/frontend/` in a browser.

## Data contract

The dashboard reads a single file: `mock_data/grid.geojson`
(swap this file for the real pipeline output — same filename, same schema).

Each GeoJSON feature must have these properties:

| Field                | Type    | Example         | Required | Notes                                    |
|----------------------|---------|-----------------|----------|-------------------------------------------|
| `grid_id`            | string  | `"91.7450_26.1650"` | Yes | Unique ID per cell (used as join key)     |
| `temperature`        | number  | `34.1`          | No*      | °C. Missing/null renders as "N/A", grey   |
| `ndvi`                | number  | `0.44`          | No*      | Vegetation index, -1 to 1                 |
| `priority`            | string  | `"High"` / `"Medium"` / `"Low"` | No* | Used by filter buttons |
| `recommended_action`  | string  | `"Tree cover"` / `"Cool roof"` / `"Green park"` / `"None"` | No* | Drives the -3°C intervention shift |
| `cost_estimate`      | number  | `112330`        | No*      | ₹ INR, shown in popup                     |

\* Fields are optional in the sense that missing/null values are handled
gracefully (shown as "N/A" / grey), but the dashboard is only meaningful
once real values are present.

**Geometry:** each feature should be a polygon representing one grid cell
(currently ~100m × 100m squares).

## Swapping in real data

1. Replace `mock_data/grid.geojson` with the real pipeline output, keeping
   the exact field names above.
2. If `predictions.csv` / `recommendation.csv` are separate files from
   Members 2/3, join them on `grid_id` into a single GeoJSON before
   dropping it in here — the frontend expects one merged file, not three.
3. No code changes needed if field names match. Hard refresh the browser.

## Features

- Split-screen before/after comparison (synced pan/zoom)
- Click any grid cell for details (temp, NDVI, priority, recommendation, cost)
- Filter by priority (All / High / Medium / Low)
- Location search (geocoder, top-left map)
- Loading state + graceful error handling for missing/malformed data

## Known limitations (mock data phase)

- Intervention effect is currently a flat -3°C applied to any cell with a
  `recommended_action` — this should be replaced by Member 2/3's real
  predicted cooling values once available.
- Mock data uses a fixed Guwahati bounding box (`91.73–91.76, 26.15–26.18`);
  confirm this matches the final chosen ward.

## File structure
frontend/
index.html
style.css
mock_data/
generate_mock.py
grid.geojson
js/
dataLoader.js
mapView.js
popup.js
compareView.js
filters.js
main.js