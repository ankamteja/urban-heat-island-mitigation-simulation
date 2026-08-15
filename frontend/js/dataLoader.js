/* Loads the grid and reduces it to the flat point set the heat field renders. */

async function loadGrid(paths) {
  const list = Array.isArray(paths) ? paths : [paths];
  let lastErr;
  for (const path of list) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return normalize(await res.json(), path);
    } catch (err) {
      lastErr = err;
    }
  }
  throw new Error(`Could not load grid data (${lastErr && lastErr.message})`);
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
       fallback for data that predates it (the legacy mock grid). A cooling_c of
       0 is a real zero, not a missing value. */
    const rawCooling = p.cooling_c;
    const cooling = typeof rawCooling === 'number' && isFinite(rawCooling)
      ? rawCooling
      : (INTERVENTIONS[action] || INTERVENTIONS.None).cooling;

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
      priority: p.priority || 'Unknown',
      action,
      cost: typeof p.cost_estimate === 'number' ? p.cost_estimate : 0,
      cooling: action === 'None' ? 0 : cooling
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

/* Descriptive statistics for one set of cells — drives KPIs and charts. */
function summarize(cells) {
  const n = cells.length;
  if (!n) {
    return { n: 0, meanTemp: 0, maxTemp: 0, minTemp: 0, meanNdvi: 0,
             cost: 0, treated: 0, meanDrop: 0, meanDropTreated: 0, meanAfter: 0,
             byPriority: {}, byAction: {} };
  }

  let sumT = 0, maxT = -Infinity, minT = Infinity, sumN = 0, nNdvi = 0;
  let cost = 0, treated = 0, sumDrop = 0;
  const byPriority = {}, byAction = {};

  for (const c of cells) {
    sumT += c.temp;
    if (c.temp > maxT) maxT = c.temp;
    if (c.temp < minT) minT = c.temp;
    if (c.ndvi !== null) { sumN += c.ndvi; nNdvi++; }

    byPriority[c.priority] = (byPriority[c.priority] || 0) + 1;

    if (c.cooling > 0) {
      treated++;
      sumDrop += c.cooling;
      cost += c.cost;
      const a = byAction[c.action] || { cells: 0, cost: 0, cooling: 0 };
      a.cells++; a.cost += c.cost; a.cooling += c.cooling;
      byAction[c.action] = a;
    }
  }

  const meanTemp = sumT / n;
  return {
    n,
    meanTemp,
    maxTemp: maxT,
    minTemp: minT,
    meanNdvi: nNdvi ? sumN / nNdvi : 0,
    cost,
    treated,
    // Two different averages, deliberately both exposed.
    //
    // meanDrop divides by every cell in the set, including the ~49% that are
    // water, existing tree cover or low priority and are never treated. It is
    // the honest city-wide figure and it is small: ~0.5 degC.
    //
    // meanDropTreated divides by the treated cells only, and is ~1.0 degC.
    //
    // Reporting only the first next to a crore-scale cost invites the obvious
    // reaction - "that much money for half a degree?" - by pairing a total
    // spent on 4,157 cells with an average spread over 8,144. Reporting only
    // the second overstates what the programme does to the city. The UI names
    // the denominator on both. See docs/08-limitations.md.
    meanDrop: sumDrop / n,
    meanDropTreated: treated ? sumDrop / treated : 0,
    meanAfter: meanTemp - sumDrop / n,
    byPriority,
    byAction
  };
}

/* Post-intervention twin of a cell set. */
function applyIntervention(cells) {
  return cells.map(c => (c.cooling > 0 ? { ...c, temp: +(c.temp - c.cooling).toFixed(2) } : c));
}
