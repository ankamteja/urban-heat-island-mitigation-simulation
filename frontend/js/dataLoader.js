/* Loads the grid and reduces each polygon to the flat record the app works on. */

async function loadGrid(path) {
  const res = await fetch(path, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const geojson = await res.json();
  validateGrid(geojson);
  return normalize(geojson, path);
}

/* The grid contract, checked before anything is drawn.

   Since the dashboard can open a file the user chose, the interesting failure
   is no longer "the fetch broke" but "that is the wrong file". Without this,
   a plausible-but-wrong GeoJSON — a ward boundary layer, an older 7-property
   grid, someone's unrelated export — renders an empty map and a panel of
   zeroes, which reads as a broken dashboard rather than a wrong input. Every
   throw here has to name what is actually wrong with the file.

   The 11 properties are export_grid_geojson.py's FRONTEND_PROPERTIES. Three
   of them are load-bearing enough to be fatal:
     grid_id            — identity; the funded set is a set of these
     temperature        — the measurement the whole app is about
     plan_rank          — the pipeline's funding order. A grid without it
                          parses, draws and then funds nothing at any budget,
                          because optimisePlan() only considers rank > 0.
   The rest degrade honestly, so they are reported as a warning, not a throw. */
const REQUIRED_PROPERTIES = ['grid_id', 'temperature', 'plan_rank'];
const CONTRACT_PROPERTIES = [
  'grid_id', 'temperature', 'ndvi', 'ndbi', 'land_cover', 'priority',
  'recommended_action', 'exclusion_reason', 'cost_estimate', 'cooling_c',
  'plan_rank'
];

function validateGrid(geojson) {
  if (!geojson || typeof geojson !== 'object') {
    throw new Error('the file did not parse to a JSON object');
  }
  if (geojson.type !== 'FeatureCollection') {
    throw new Error(
      `expected a GeoJSON FeatureCollection, found ${geojson.type ? `"${geojson.type}"` : 'no "type" field'}`);
  }
  if (!Array.isArray(geojson.features) || !geojson.features.length) {
    throw new Error('the FeatureCollection has no features');
  }

  const sample = geojson.features[0];
  const geom = sample && sample.geometry;
  if (!geom || geom.type !== 'Polygon') {
    throw new Error(
      `grid cells must be Polygons, the first feature is ${geom && geom.type ? `a ${geom.type}` : 'missing its geometry'}`);
  }

  const props = (sample && sample.properties) || {};
  const missing = REQUIRED_PROPERTIES.filter(k => props[k] === undefined);
  if (missing.length) {
    throw new Error(
      `its cells have no ${missing.join(', ')}. ` +
      `A grid from this pipeline carries ${CONTRACT_PROPERTIES.length} properties ` +
      `(${CONTRACT_PROPERTIES.join(', ')}); this file has ` +
      `${Object.keys(props).length} (${Object.keys(props).join(', ') || 'none'})`);
  }
  if (typeof props.temperature !== 'number' || !isFinite(props.temperature)) {
    throw new Error(`temperature must be a number, found ${JSON.stringify(props.temperature)}`);
  }
  if (typeof props.plan_rank !== 'number') {
    throw new Error(
      `plan_rank must be a number — the budget is allocated by sorting on it — found ${JSON.stringify(props.plan_rank)}`);
  }

  const absent = CONTRACT_PROPERTIES.filter(k => props[k] === undefined);
  if (absent.length) {
    console.warn(`Grid is missing optional properties: ${absent.join(', ')}. ` +
                 'Panels that read them will show blanks.');
  }
  return true;
}

function normalize(geojson, source) {
  const cells = [];
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;

  for (const f of geojson.features || []) {
    const ring = f.geometry && f.geometry.coordinates && f.geometry.coordinates[0];
    if (!ring || ring.length < 4) continue;

    let sx = 0, sy = 0;
    let cMinLon = Infinity, cMaxLon = -Infinity, cMinLat = Infinity, cMaxLat = -Infinity;
    for (let i = 0; i < 4; i++) {
      const [lon, lat] = ring[i];
      sx += lon; sy += lat;
      if (lon < cMinLon) cMinLon = lon;
      if (lon > cMaxLon) cMaxLon = lon;
      if (lat < cMinLat) cMinLat = lat;
      if (lat > cMaxLat) cMaxLat = lat;
    }

    const p = f.properties || {};
    const temp = typeof p.temperature === 'number' && isFinite(p.temperature) ? p.temperature : null;
    if (temp === null) continue;

    let action = p.recommended_action;
    if (!action || action === 'nan' || action === 'NaN') action = 'None';

    /* The pipeline emits a per-cell cooling_c; the table in INTERVENTIONS is a
       fallback for data that predates it. A cooling_c of 0 is a real zero, not a
       missing value. */
    const rawCooling = p.cooling_c;
    const cooling = typeof rawCooling === 'number' && isFinite(rawCooling)
      ? rawCooling
      : interventionMeta(action).cooling;

    const lon = sx / 4, lat = sy / 4;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;

    cells.push({
      id: p.grid_id,
      lat, lon,
      bounds: [[cMinLat, cMinLon], [cMaxLat, cMaxLon]],
      temp,
      ndvi: typeof p.ndvi === 'number' ? p.ndvi : null,
      ndbi: typeof p.ndbi === 'number' ? p.ndbi : null,
      landCover: p.land_cover || '',
      priority: p.priority || 'Unknown',
      action,
      exclusionReason: p.exclusion_reason || '',
      cost: typeof p.cost_estimate === 'number' ? p.cost_estimate : 0,
      cooling: action === 'None' ? 0 : cooling,
      /* The pipeline's funding order, carried through so the browser never has
         to re-derive it. 0 means "never funded at any budget". */
      rank: typeof p.plan_rank === 'number' && p.plan_rank > 0 ? p.plan_rank : 0
    });
  }

  if (!cells.length) throw new Error('grid contains no usable cells');

  const sorted = cells.map(c => c.temp).sort((a, b) => a - b);
  const at = q => sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
  setTempDomain(at(0.02), at(0.98));

  return {
    source,
    cells,
    bounds: [[minLat, minLon], [maxLat, maxLon]],
    center: [(minLat + maxLat) / 2, (minLon + maxLon) / 2]
  };
}

/* Descriptive statistics for one set of cells.

   `funded` is the set the budget actually pays for. Everything that reports a
   cooling or a cost takes it as an argument rather than recomputing a
   membership rule of its own — see state.js on why that matters. */
function summarize(cells, funded) {
  const n = cells.length;
  const empty = {
    n: 0, meanTemp: 0, maxTemp: 0, minTemp: 0, meanNdvi: 0,
    eligibleCost: 0, eligible: 0, fundedCount: 0, fundedCost: 0,
    meanDrop: 0, meanDropTreated: 0, meanAfter: 0, peakDrop: 0,
    hotspotsBefore: 0, hotspotsAfter: 0,
    byPriority: {}, byAction: {}
  };
  if (!n) return empty;

  const fundedIds = funded instanceof Set ? funded : new Set();

  let sumT = 0, maxT = -Infinity, minT = Infinity, sumN = 0, nNdvi = 0;
  let eligibleCost = 0, eligible = 0;
  let fundedCount = 0, fundedCost = 0, sumDrop = 0, peakDrop = 0;
  let hotBefore = 0, hotAfter = 0;
  const byPriority = {}, byAction = {};

  /* "Hotspot" is the top decile of the observed range, stated once here so the
     impact panel and the analytics cannot drift apart on the definition. */
  const hotCut = TEMP_DOMAIN.min + (TEMP_DOMAIN.max - TEMP_DOMAIN.min) * 0.9;

  for (const c of cells) {
    sumT += c.temp;
    if (c.temp > maxT) maxT = c.temp;
    if (c.temp < minT) minT = c.temp;
    if (c.ndvi !== null) { sumN += c.ndvi; nNdvi++; }
    byPriority[c.priority] = (byPriority[c.priority] || 0) + 1;

    if (c.cooling > 0) {
      eligible++;
      eligibleCost += c.cost;
      const a = byAction[c.action] || { cells: 0, cost: 0, cooling: 0, funded: 0, fundedCost: 0, fundedCooling: 0 };
      a.cells++; a.cost += c.cost; a.cooling += c.cooling;
      byAction[c.action] = a;
    }

    const paid = fundedIds.has(c.id) && c.cooling > 0;
    const drop = paid ? c.cooling : 0;
    if (paid) {
      fundedCount++;
      fundedCost += c.cost;
      sumDrop += drop;
      if (drop > peakDrop) peakDrop = drop;
      const a = byAction[c.action];
      if (a) { a.funded++; a.fundedCost += c.cost; a.fundedCooling += c.cooling; }
    }

    if (c.temp >= hotCut) hotBefore++;
    if (c.temp - drop >= hotCut) hotAfter++;
  }

  const meanTemp = sumT / n;
  return {
    n,
    meanTemp,
    maxTemp: maxT,
    minTemp: minT,
    meanNdvi: nNdvi ? sumN / nNdvi : 0,
    eligible,
    eligibleCost,
    fundedCount,
    fundedCost,
    // Two averages, both exposed and both labelled at every call site.
    //
    // meanDrop divides by every cell in the set, including the ~49% that are
    // water, existing tree cover or low priority and are never treated. It is
    // the honest city-wide figure and it is small.
    //
    // meanDropTreated divides by the funded cells only, and is ~1.0 degC.
    //
    // Reporting only the first next to a crore-scale cost invites "that much
    // money for half a degree?"; reporting only the second overstates what the
    // programme does to the city. The UI names the denominator on both.
    meanDrop: sumDrop / n,
    meanDropTreated: fundedCount ? sumDrop / fundedCount : 0,
    meanAfter: meanTemp - sumDrop / n,
    peakDrop,
    hotspotsBefore: hotBefore,
    hotspotsAfter: hotAfter,
    byPriority,
    byAction
  };
}

/* Post-mitigation twin of a cell set: only funded cells move. */
function applyIntervention(cells, funded) {
  const ids = funded instanceof Set ? funded : new Set();
  return cells.map(c => (
    ids.has(c.id) && c.cooling > 0
      ? { ...c, temp: +(c.temp - c.cooling).toFixed(2) }
      : c
  ));
}
