/* Ecology pointers — marks where each cooling measure is viable inside a selection.

   The ML module emits a coarse action per cell; here it is refined into distinct
   ecological measures using surface temperature and vegetation cover, then thinned
   so pointers mark representative sites instead of every single cell. */

function ecologyTypeFor(cell, hotThreshold) {
  switch (cell.action) {
    case 'Cool roof':
      return cell.ndvi !== null && cell.ndvi >= 0.15 ? 'Green roof' : 'Cool roof';
    case 'Tree cover':
      return 'Tree cover';
    case 'Green park':
      if (cell.temp >= hotThreshold && cell.ndvi !== null && cell.ndvi < 0.10) return 'Water body';
      return 'Green park';
    default:
      return null;
  }
}

function deriveEcologySites(cells, opts) {
  const o = opts || {};
  const maxPerType = o.maxPerType || 6;

  const temps = cells.map(c => c.temp).sort((a, b) => a - b);
  if (!temps.length) return [];
  const hotThreshold = temps[Math.floor(temps.length * 0.75)];

  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
  for (const c of cells) {
    if (c.lat < minLat) minLat = c.lat;
    if (c.lat > maxLat) maxLat = c.lat;
    if (c.lon < minLon) minLon = c.lon;
    if (c.lon > maxLon) maxLon = c.lon;
  }
  const span = Math.max(maxLat - minLat, maxLon - minLon);
  const minSep = Math.max(span / 9, 0.0025);

  const byType = new Map();
  for (const c of cells) {
    const type = ecologyTypeFor(c, hotThreshold);
    if (!type) continue;
    const list = byType.get(type);
    if (list) list.push(c); else byType.set(type, [c]);
  }

  /* Round-robin across types so every viable measure gets representation, but
     test separation against every pin already placed — pins of different types
     would otherwise stack on top of each other. */
  const queues = [...byType.entries()].map(([type, list]) => ({
    type,
    list: list.sort((a, b) => b.temp - a.temp),
    at: 0,
    taken: 0,
    total: list.length
  }));

  const sites = [];
  const clashes = c => sites.some(s => {
    const dy = s.cell.lat - c.lat, dx = s.cell.lon - c.lon;
    return Math.sqrt(dy * dy + dx * dx) < minSep;
  });

  let progress = true;
  while (progress) {
    progress = false;
    for (const q of queues) {
      if (q.taken >= maxPerType) continue;
      while (q.at < q.list.length) {
        const c = q.list[q.at++];
        if (clashes(c)) continue;
        const meta = INTERVENTIONS[q.type] || INTERVENTIONS.None;
        sites.push({
          type: q.type,
          cell: c,
          /* The cell carries the pipeline's own cooling_c; a derived measure
             inherits it from the cell it was refined out of. */
          cooling: c.cooling,
          color: meta.color,
          label: meta.label,
          catchment: q.total
        });
        q.taken++;
        progress = true;
        break;
      }
    }
  }
  return sites;
}

function ecoIcon(type, color) {
  const glyph = ECO_ICONS[type] || ECO_ICONS.None;
  return L.divIcon({
    className: '',
    iconSize: [30, 30],
    iconAnchor: [15, 28],
    popupAnchor: [0, -26],
    html: `<div class="eco-pin" style="width:30px;height:30px;background:${color}">
             <svg viewBox="0 0 24 24" aria-hidden="true">${glyph}</svg>
           </div>`
  });
}

function renderEcologyMarkers(map, sites) {
  const layer = L.layerGroup().addTo(map);
  sites.forEach((site, i) => {
    const m = L.marker([site.cell.lat, site.cell.lon], {
      icon: ecoIcon(site.type, site.color),
      keyboard: true,
      title: `${site.label} — ${site.cell.temp.toFixed(1)}°C`,
      riseOnHover: true
    });
    m.bindPopup(`
      <div class="pop-badge" style="background:${site.color}22;color:${site.color}">${site.label}</div>
      <div class="pop-title">${site.type}</div>
      <div class="pop-sub">${site.cell.lat.toFixed(4)}, ${site.cell.lon.toFixed(4)}</div>
      <div class="pop-row"><span>Current temp</span><b>${site.cell.temp.toFixed(1)}°C</b></div>
      <div class="pop-row"><span>Scenario drop (assumed)</span><b>−${site.cooling.toFixed(1)}°C</b></div>
      <div class="pop-row"><span>Scenario surface temp</span><b>${(site.cell.temp - site.cooling).toFixed(1)}°C</b></div>
      <div class="pop-row"><span>NDVI</span><b>${site.cell.ndvi === null ? 'N/A' : site.cell.ndvi.toFixed(3)}</b></div>
      <div class="pop-row"><span>Est. cost</span><b>${inrShort(site.cell.cost)}</b></div>
      <div class="pop-row"><span>Similar cells here</span><b>${site.catchment}</b></div>
    `);
    m.addTo(layer);
    const node = m.getElement();
    if (node) node.style.animationDelay = (i * 45) + 'ms';
  });
  return layer;
}

function renderEcologyLegend(containerId, sites) {
  const el = document.getElementById(containerId);
  const counts = new Map();
  for (const s of sites) {
    const e = counts.get(s.type) || { n: 0, color: s.color, label: s.label, cooling: s.cooling };
    e.n++;
    counts.set(s.type, e);
  }

  if (!counts.size) {
    el.innerHTML = '<p class="panel-hint">No viable measures in this selection.</p>';
    return;
  }

  el.innerHTML = [...counts.entries()].map(([type, e]) => `
    <div class="eco-item">
      <span class="eco-swatch" style="background:${e.color}22;color:${e.color}">
        <svg viewBox="0 0 24 24" aria-hidden="true">${ECO_ICONS[type] || ECO_ICONS.None}</svg>
      </span>
      <span class="eco-meta">
        <b>${e.label}</b>
        <span>${e.n} site${e.n > 1 ? 's' : ''} · −${e.cooling.toFixed(1)}°C</span>
      </span>
    </div>
  `).join('');
}
