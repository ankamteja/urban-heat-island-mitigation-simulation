/* Popup markup for a grid cell, plus the ground-truth affordances around it:
   where the cell actually is, what the place is called, and the 100 m box the
   numbers describe. A planner reading "cool roof, 249th of 4,157" needs to be
   able to go and look at the roof. */

/* Nominatim asks for at most one request a second, so every answer is kept.
   Panning back to a cell you already opened costs nothing. */
const PLACE_CACHE = new Map();
let REVERSE_GEOCODER = null;

function cellKey(cell) {
  return cell.id || `${cell.lat.toFixed(5)},${cell.lon.toFixed(5)}`;
}

/* Street View has no free availability check without a Maps API key, so we
   cannot promise a panorama exists. `map_action=pano` asks Google for the
   nearest one and degrades to the map when there is none; the second link is
   the guaranteed fallback, and both are offered rather than one guessed. */
function streetViewUrl(cell) {
  return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${cell.lat},${cell.lon}`;
}

function mapsUrl(cell) {
  return `https://www.google.com/maps/search/?api=1&query=${cell.lat},${cell.lon}`;
}

/* Nominatim returns a full postal address; the first two parts are the part a
   human recognises. The full string stays in the title attribute. */
function shortPlace(name) {
  if (!name) return null;
  const parts = name.split(',').map(s => s.trim()).filter(Boolean);
  return parts.slice(0, 2).join(', ') || name;
}

function reverseGeocode(map, cell, cb) {
  const key = cellKey(cell);
  if (PLACE_CACHE.has(key)) return cb(PLACE_CACHE.get(key));

  const G = L.Control && L.Control.Geocoder;
  if (!G || !G.nominatim) return cb(null);
  if (!REVERSE_GEOCODER) REVERSE_GEOCODER = G.nominatim();

  const scale = map.options.crs.scale(map.getZoom());
  try {
    REVERSE_GEOCODER.reverse(L.latLng(cell.lat, cell.lon), scale, results => {
      const name = results && results[0] ? results[0].name : null;
      PLACE_CACHE.set(key, name);
      cb(name);
    });
  } catch (err) {
    console.warn('Reverse geocode failed', err);
    cb(null);
  }
}

function buildPopupContent(cell, opts) {
  const o = opts || {};
  const meta = INTERVENTIONS[cell.action] || INTERVENTIONS.None;
  const pri = cell.priority || 'Unknown';
  const priColor = PRIORITY_COLOR[pri] || '#64748B';

  const rows = [
    ['Surface temp', `${cell.temp.toFixed(1)}°C`],
    ['NDVI', cell.ndvi === null ? 'N/A' : cell.ndvi.toFixed(3)],
    ['Recommended', meta.label]
  ];

  if (cell.cooling > 0) {
    rows.push(['Scenario drop (assumed)', `−${cell.cooling.toFixed(1)}°C`]);
    rows.push(['Scenario surface temp', `${(cell.temp - cell.cooling).toFixed(1)}°C`]);
    rows.push(['Est. cost', inrShort(cell.cost)]);
  }

  const [[s, w], [n, e]] = cell.bounds;

  return `
    <div class="pop-badge" style="background:${priColor}22;color:${priColor}">${pri} priority</div>
    <div class="pop-title">${o.title || 'Grid cell'}</div>
    <div class="pop-sub">${cell.id || '—'} · ${cell.lat.toFixed(4)}, ${cell.lon.toFixed(4)}</div>
    ${rows.map(([k, v]) => `<div class="pop-row"><span>${k}</span><b>${v}</b></div>`).join('')}
    <div class="pop-place" data-place>
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 14s5-4.2 5-8A5 5 0 0 0 3 6c0 3.8 5 8 5 8z" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="8" cy="6" r="1.8" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
      <span data-place-name class="is-pending">Locating…</span>
    </div>
    <div class="pop-box">
      <span>Grid box</span>
      <b>${s.toFixed(4)}, ${w.toFixed(4)} → ${n.toFixed(4)}, ${e.toFixed(4)}</b>
    </div>
    <div class="pop-links">
      <a class="pop-link is-primary" href="${streetViewUrl(cell)}" target="_blank" rel="noopener noreferrer">
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="4.2" r="2.2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M4.2 14v-3.4a3.8 3.8 0 0 1 7.6 0V14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
        Street View
      </a>
      <a class="pop-link" href="${mapsUrl(cell)}" target="_blank" rel="noopener noreferrer">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 4.2 6 2.5l4 1.7 4.5-1.7v9.3L10 13.5l-4-1.7-4.5 1.7z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><path d="M6 2.5v9.3M10 4.2v9.3" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
        Google Maps
      </a>
    </div>
  `;
}

/* Opens the popup, outlines the cell it describes, and fills the place name in
   once Nominatim answers. The outline is what makes "grid box" mean something:
   the popup quotes an extent, the map shows it. */
function openCellPopup(map, cell, opts) {
  const box = L.rectangle(cell.bounds, {
    color: '#FBBF24',
    weight: 1.5,
    opacity: 0.9,
    dashArray: '4 3',
    fill: true,
    fillOpacity: 0.06,
    interactive: false,
    className: 'cell-box'
  }).addTo(map);

  const popup = L.popup({ closeButton: true, autoPanPadding: [24, 24] })
    .setLatLng([cell.lat, cell.lon])
    .setContent(buildPopupContent(cell, opts))
    .openOn(map);

  map.once('popupclose', () => {
    if (map.hasLayer(box)) map.removeLayer(box);
  });

  reverseGeocode(map, cell, name => {
    const el = popup.getElement && popup.getElement();
    const slot = el && el.querySelector('[data-place-name]');
    if (!slot) return;
    slot.classList.remove('is-pending');
    if (name) {
      slot.textContent = shortPlace(name);
      slot.title = name;
    } else {
      slot.textContent = 'No place name available';
      slot.classList.add('is-muted');
    }
  });

  return popup;
}
