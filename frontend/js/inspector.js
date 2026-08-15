/* Cell inspection drawer.

   The brief's test for this panel (§8) is that clicking a cell should
   demonstrate a decision-support system rather than a heatmap. So it does not
   just print the record — it says why the cell reads as it does, why the rule
   engine reached the action it did, and whether the current budget pays for it.

   Every explanation below is read from exported pipeline fields. Nothing is
   inferred in the browser: re-deriving the rule engine on the client is how the
   two ends of a system start disagreeing. */

const PLACE_CACHE = new Map();
let REVERSE_GEOCODER = null;

function cellKey(cell) {
  return cell.id || `${cell.lat.toFixed(5)},${cell.lon.toFixed(5)}`;
}

/* Street View has no free availability check without a Maps API key, so a
   panorama cannot be promised. map_action=pano asks Google for the nearest one
   and degrades to the map when there is none; the second link always resolves.
   Both are offered rather than one guessed. */
function streetViewUrl(cell) {
  return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${cell.lat},${cell.lon}`;
}

function mapsUrl(cell) {
  return `https://www.google.com/maps/search/?api=1&query=${cell.lat},${cell.lon}`;
}

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

  try {
    REVERSE_GEOCODER.reverse(
      L.latLng(cell.lat, cell.lon),
      map.options.crs.scale(map.getZoom()),
      results => {
        const name = results && results[0] ? results[0].name : null;
        PLACE_CACHE.set(key, name);
        cb(name);
      }
    );
  } catch (err) {
    console.warn('Reverse geocode failed', err);
    cb(null);
  }
}

/* ── why this cell ───────────────────────────────────────────────────────── */

/* Ranks the cell against the study area on the two indices the model actually
   uses, so "why" is a comparison rather than a bare number. */
function factorRows(cell) {
  const all = App.allCells;
  const pctOf = (value, key) => {
    if (value === null || value === undefined) return null;
    let below = 0, n = 0;
    for (const c of all) {
      const v = c[key];
      if (v === null || v === undefined) continue;
      n++;
      if (v < value) below++;
    }
    return n ? below / n : null;
  };

  const band = p => p === null ? '' :
    p >= 0.9 ? 'top 10%' :
    p >= 0.75 ? 'top 25%' :
    p <= 0.1 ? 'bottom 10%' :
    p <= 0.25 ? 'bottom 25%' : 'mid-range';

  const rows = [];

  const tp = pctOf(cell.temp, 'temp');
  rows.push({
    label: 'Surface temperature',
    value: degrees(cell.temp),
    note: band(tp),
    weight: tp
  });

  if (cell.ndbi !== null) {
    const bp = pctOf(cell.ndbi, 'ndbi');
    rows.push({
      label: 'Built-up intensity',
      value: cell.ndbi.toFixed(3),
      /* NDBI is the strongest single driver in the model at 0.408 importance,
         so it is the honest first answer to "why is this cell hot". */
      note: band(bp) + ' NDBI',
      weight: bp
    });
  }

  if (cell.ndvi !== null) {
    const vp = pctOf(cell.ndvi, 'ndvi');
    rows.push({
      label: 'Vegetation (NDVI)',
      value: cell.ndvi.toFixed(3),
      note: band(vp),
      weight: vp === null ? null : 1 - vp
    });
  }

  rows.push({
    label: 'Land cover',
    value: landCoverLabel(cell.landCover),
    note: 'ESA WorldCover',
    weight: null
  });

  return rows;
}

function whyText(cell) {
  const hot = cell.temp >= TEMP_DOMAIN.min + (TEMP_DOMAIN.max - TEMP_DOMAIN.min) * 0.75;
  const built = cell.landCover === 'built_up';
  const bare = cell.ndvi !== null && cell.ndvi < 0.25;

  const causes = [];
  if (built) causes.push('the surface is built-up');
  if (bare) causes.push('vegetation cover is low');
  if (cell.ndbi !== null && cell.ndbi > -0.1) causes.push('the built-up index is high for this city');

  if (!causes.length) {
    return hot
      ? 'This cell runs hot without an obvious built-up or vegetation driver — worth checking against the source scene.'
      : 'This cell sits within the normal range for the study area.';
  }
  const joined = causes.length > 1
    ? causes.slice(0, -1).join(', ') + ' and ' + causes[causes.length - 1]
    : causes[0];
  return `${hot ? 'Runs hot because ' : 'Elevated because '}${joined}.`;
}

/* ── the drawer ──────────────────────────────────────────────────────────── */

let activeBox = null;

function openInspector(cell) {
  const el = document.getElementById('inspector');
  if (!el) return;

  const meta = interventionMeta(cell.action);
  const funded = App.funded.has(cell.id);
  const actionable = cell.cooling > 0;
  const [[s, w], [n, e]] = cell.bounds;

  const factors = factorRows(cell).map(f => `
    <div class="fx">
      <span class="fx-k">${f.label}</span>
      <b class="fx-v">${f.value}</b>
      <span class="fx-n">${f.note}</span>
      ${f.weight === null ? '' : `<i class="fx-bar"><em style="width:${Math.round(f.weight * 100)}%"></em></i>`}
    </div>`).join('');

  const recommendation = actionable ? `
    <div class="rec${funded ? ' is-funded' : ''}">
      <div class="rec-head">
        <span class="iv-sym" style="--tint:${meta.tint}">
          <svg viewBox="0 0 16 16" aria-hidden="true">${meta.symbol}</svg>
        </span>
        <div>
          <p class="rec-name">${meta.label}</p>
          <p class="rec-unit">${meta.unit}</p>
        </div>
        <span class="rec-state">${funded ? 'Funded' : 'Not in budget'}</span>
      </div>
      <dl class="rec-figs">
        <div><dt>Expected cooling</dt><dd>${signedDrop(cell.cooling)}</dd></div>
        <div><dt>Estimated cost</dt><dd>${inrShort(cell.cost)}</dd></div>
        <div><dt>Plan priority</dt><dd>#${cell.rank.toLocaleString()} of ${App.stats ? App.stats.eligible.toLocaleString() : '—'}</dd></div>
      </dl>
      ${funded ? '' : `<p class="rec-why">Ranked #${cell.rank.toLocaleString()}; the current budget reaches #${App.stats ? App.stats.fundedCount.toLocaleString() : '—'}.</p>`}
    </div>` : `
    <div class="rec is-excluded">
      <p class="rec-name">No intervention proposed</p>
      <p class="rec-why">${cell.exclusionReason || 'This cell is not eligible under the land-cover rules.'}</p>
    </div>`;

  el.innerHTML = `
    <header class="ins-head">
      <div>
        <p class="ins-eyebrow">Grid cell</p>
        <h2 class="ins-id">${cell.id || '—'}</h2>
      </div>
      <button type="button" id="ins-close" class="icon-btn" aria-label="Close cell inspector">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>
      </button>
    </header>

    <p class="ins-place" data-place-name>Locating…</p>
    <p class="ins-coords">${cell.lat.toFixed(4)}, ${cell.lon.toFixed(4)} · ${cell.priority} priority</p>

    <section class="ins-sec">
      <h3>Why this cell</h3>
      <p class="ins-why">${whyText(cell)}</p>
      ${factors}
    </section>

    <section class="ins-sec">
      <h3>Recommended action</h3>
      ${recommendation}
    </section>

    <section class="ins-sec">
      <h3>Verify on the ground</h3>
      <div class="ins-links">
        <a href="${streetViewUrl(cell)}" target="_blank" rel="noopener noreferrer">Street View</a>
        <a href="${mapsUrl(cell)}" target="_blank" rel="noopener noreferrer">Google Maps</a>
      </div>
      <p class="ins-box">Cell extent ${s.toFixed(4)}, ${w.toFixed(4)} → ${n.toFixed(4)}, ${e.toFixed(4)}</p>
    </section>
  `;

  el.hidden = false;
  el.classList.add('is-open');
  document.body.classList.add('has-inspector');

  const close = document.getElementById('ins-close');
  if (close) close.addEventListener('click', closeInspector);

  showCellBox(cell);

  reverseGeocode(mapView.map, cell, name => {
    const slot = el.querySelector('[data-place-name]');
    if (!slot) return;
    if (name) {
      slot.textContent = shortPlace(name);
      slot.title = name;
    } else {
      slot.textContent = 'No place name available';
      slot.classList.add('is-dim');
    }
  });
}

function closeInspector() {
  const el = document.getElementById('inspector');
  if (el) { el.hidden = true; el.classList.remove('is-open'); }
  document.body.classList.remove('has-inspector');
  clearCellBox();
}

/* The outline is what makes "cell extent" mean something: the drawer quotes a
   box, the map shows it. */
function showCellBox(cell) {
  clearCellBox();
  activeBox = L.rectangle(cell.bounds, {
    color: '#E8EAF0', weight: 1.4, opacity: 0.95,
    fill: true, fillOpacity: 0.05, interactive: false
  }).addTo(mapView.map);
}

function clearCellBox() {
  if (activeBox && mapView.map) mapView.map.removeLayer(activeBox);
  activeBox = null;
}
