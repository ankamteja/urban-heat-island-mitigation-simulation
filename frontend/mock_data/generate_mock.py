import geopandas as gpd
from shapely.geometry import box
import random

minx, miny, maxx, maxy = 91.73, 26.15, 91.76, 26.18  # rough Guwahati ward bbox — swap for your real ward
cell_size = 0.001

cells = []
x = minx
while x < maxx:
    y = miny
    while y < maxy:
        cells.append({
            "grid_id": f"{x:.4f}_{y:.4f}",
            "geometry": box(x, y, x + cell_size, y + cell_size),
            "temperature": round(random.uniform(28, 42), 1),
            "ndvi": round(random.uniform(-0.1, 0.8), 2),
            "priority": random.choice(["High", "Medium", "Low"]),
            "recommended_action": random.choice(["Tree cover", "Cool roof", "Green park", "None"]),
            "cost_estimate": random.randint(5000, 200000)
        })
        y += cell_size
    x += cell_size

gdf = gpd.GeoDataFrame(cells, crs="EPSG:4326")
gdf.to_file("grid.geojson", driver="GeoJSON")
print(f"Generated {len(cells)} grid cells")