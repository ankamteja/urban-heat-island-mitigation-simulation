/* City switching and file insertion.

   The pipeline used to build one city. It now builds any city, so the
   dashboard has to answer two questions it never had to before: which city am
   I looking at, and does what I am reading still mean anything here.

   The second one is the reason this file is longer than a dropdown needs to
   be. Temperature and land cover are measured and travel fine. The rupee
   figures do not: the unit rates in shared/constants.json are Indian municipal
   INR/m2. Applied to Phoenix they render perfectly and mean nothing. Every
   city carries `cost_basis_applies`, and where it is false the cost figures
   are banded off rather than quietly shown.

   Swapping a city is a data swap, not a rebuild. state.js owns the truth:
   replace App.allCells, reset the scope, then call refresh() once and let the
   single subscription repaint everything. No panel is told about the change
   individually -- that is what the redesign exists to prevent. */

const CITY_MANIFEST = 'data/cities.json';

/* The city the app falls back to when there is no manifest at all: the
   committed Earth Engine build, which has always been on disk. */
const BUILTIN_CITY = {
  slug: 'guwahati',
  name: 'Guwahati',
  region: 'Assam, India',
  path: 'data/grid.geojson',
  source: 'Google Earth Engine (Landsat 8 C2 L2 + ESA WorldCover v200)',
  cost_basis_applies: true,
  builtin: true
};

/* ── manifest ────────────────────────────────────────────────────────────── */

/* cities.json is derived from the city.json files on disk by
   backend/build_city.py. It is optional: a checkout with only the committed
   Guwahati grid has no manifest, and the dashboard must still work. */
async function loadCityManifest() {
  try {
    const res = await fetch(CITY_MANIFEST, { cache: 'no-store' });
    if (!res.ok) throw new Error(String(res.status));
    const json = await res.json();
    const cities = Array.isArray(json.cities) ? json.cities.filter(c => c && c.slug && c.path) : [];
    if (!cities.length) throw new Error('manifest lists no cities');
    return cities;
  } catch (err) {
    console.warn('No city manifest; falling back to the built-in city.', err);
    return [BUILTIN_CITY];
  }
}

/* ?city=<slug> so a plan can be linked to, not just navigated to. An unknown
   slug is not an error worth blocking the boot for — say so and load the
   default. */
function resolveInitialCity(cities) {
  const want = new URLSearchParams(location.search).get('city');
  if (!want) return cities[0];
  const hit = cities.find(c => c.slug === want);
  if (hit) return hit;
  console.warn(`Unknown city "${want}" in the URL; loading ${cities[0].slug}.`);
  return cities[0];
}

/* ── loading ─────────────────────────────────────────────────────────────── */

/* Both the committed city and a built one carry a sha256 of their own grid —
   release.json for the first, city.json for the second, and update_manifest()
   copies both into the manifest. Appending it to the URL means a rebuilt city
   can never be served from a stale browser cache, which is exactly the failure
   that produced "the dashboard is not updating" against a server that was
   serving the new file all along. */
async function loadCityGrid(city) {
  const token = city.grid_sha256 && /^[a-f0-9]{64}$/.test(city.grid_sha256)
    ? `?release=${city.grid_sha256}`
    : '';
  const data = await loadGrid(city.path + token);

  /* The committed city is the one the integrity gate was written for, and the
     gate is not optional there: the whole point of release.json is that the
     canonical grid is never loaded unchecked. */
  if (city.builtin && !token) {
    throw new Error('The built-in grid has no valid checksum in the manifest.');
  }
  return data;
}

/* ── the swap ────────────────────────────────────────────────────────────── */

/* Everything that makes a city the current city, in one place, so a dropdown
   change and a dropped file cannot end up in different states.

   `meta` is the manifest entry, or a synthetic one for a dropped file. */
function adoptCity(data, meta) {
  App.allCells = data.cells;
  App.bounds = data.bounds;
  App.center = data.center;
  App.city = meta;

  /* A selection is a rectangle in the previous city's coordinates. Carrying it
     across would silently scope the new city to an empty box somewhere off its
     edge, and the panels would truthfully report zero of everything. */
  App.selection = null;
  App.priority = 'All';
  closeInspector();

  /* heatField caches a projected splat per cell, and initSurfaces() both adds
     layers and subscribes to map movement. Re-running it without tearing the
     old one down leaves the previous city's surface painted underneath and
     doubles the move handler on every switch. */
  teardownSurfaces();
  initSurfaces(data.cells);

  mapView.map.fitBounds(L.latLngBounds(data.bounds), { padding: [24, 24] });
  syncPriorityButtons();
  renderCityIdentity();

  /* A dropped file exists only in this browser, so ?city= can no longer
     describe what is on screen. Leaving the previous slug in the URL means a
     copied link opens a different city than the one the sender was reading. */
  if (meta.dropped) {
    const url = new URL(location.href);
    url.searchParams.delete('city');
    history.replaceState(null, '', url);
  }

  refresh('city');
}

function teardownSurfaces() {
  const map = mapView.map;
  if (!map) return;
  map.off('move zoom resize zoomend moveend', applyCompareClip);
  for (const key of ['current', 'mitigated', 'sites']) {
    const layer = mapView[key];
    if (layer && map.hasLayer(layer)) map.removeLayer(layer);
    mapView[key] = null;
  }
}

/* setPriority() would fire a second refresh; the buttons are display state, so
   set them directly and let adoptCity()'s single refresh cover it. */
function syncPriorityButtons() {
  document.querySelectorAll('[data-priority]').forEach(b => {
    const on = b.dataset.priority === App.priority;
    b.classList.toggle('is-on', on);
    b.setAttribute('aria-pressed', String(on));
  });
  const clear = document.getElementById('btn-clear-area');
  if (clear) clear.hidden = true;
}

async function switchCity(slug) {
  if (slug === '__file__') return;   // the ghost entry for a dropped file
  const city = App.cities.find(c => c.slug === slug);
  if (!city || (App.city && city.slug === App.city.slug && !App.city.dropped)) return;

  setCityBusy(true);
  try {
    const data = await loadCityGrid(city);
    adoptCity(data, city);
    /* replaceState, not push: the dropdown is not navigation, and a back
       button that silently reloads a different city reads as a bug. */
    const url = new URL(location.href);
    url.searchParams.set('city', city.slug);
    history.replaceState(null, '', url);
    alertInline(`Loaded ${city.name} — ${data.cells.length.toLocaleString()} cells.`);
  } catch (err) {
    console.error(err);
    alertInline(`Could not load ${city.name}: ${err.message}`);
    const select = document.getElementById('city-select');
    if (select && App.city) select.value = App.city.slug;
  } finally {
    setCityBusy(false);
  }
}

function setCityBusy(busy) {
  const select = document.getElementById('city-select');
  if (select) select.disabled = busy;
  document.body.classList.toggle('is-loading-city', busy);
}

/* ── file insertion ──────────────────────────────────────────────────────── */

/* A grid.geojson built on the user's own machine, opened here.

   The file is read with FileReader and parsed in the page. It is never sent
   anywhere, and the UI says so, because "drop your city data here" on a
   dashboard is otherwise a reasonable thing to be suspicious of. */
function readCityFile(file) {
  if (!file) return;
  if (!/\.(geojson|json)$/i.test(file.name)) {
    alertInline(`${file.name} is not a .geojson file.`);
    return;
  }
  /* 8,000-odd cells is about 4 MB. A 60 MB file is not a city grid, and
     JSON.parse on it blocks the main thread long enough to look like a hang. */
  const LIMIT = 64 * 1024 * 1024;
  if (file.size > LIMIT) {
    alertInline(`${file.name} is ${(file.size / 1048576).toFixed(0)} MB — too large to be a city grid.`);
    return;
  }

  const reader = new FileReader();
  reader.onerror = () => alertInline(`Could not read ${file.name}.`);
  reader.onload = () => {
    let geojson;
    try {
      geojson = JSON.parse(String(reader.result));
    } catch (err) {
      alertInline(`${file.name} is not valid JSON: ${err.message}`);
      return;
    }
    try {
      /* Validate before adopting. Without this a wrong file renders an empty
         map with no message, which reads as "the dashboard is broken" rather
         than "that is the wrong file". */
      validateGrid(geojson);
      const data = normalize(geojson, file.name);
      adoptCity(data, syntheticCityMeta(file, data));
      alertInline(`Loaded ${file.name} — ${data.cells.length.toLocaleString()} cells. Nothing was uploaded.`);
    } catch (err) {
      console.error(err);
      alertInline(`${file.name} is not a usable grid: ${err.message}`);
    }
  };
  reader.readAsText(file);
}

/* A dropped file has no city.json, so nothing vouches for where its costs came
   from. It is not marked false — the rates may well apply — but it cannot be
   marked true either, and the banner says exactly that. */
function syntheticCityMeta(file, data) {
  return {
    slug: 'file',
    name: file.name.replace(/\.(geojson|json)$/i, ''),
    region: 'loaded from a local file',
    path: file.name,
    source: 'local file — provenance unknown',
    cost_basis_applies: null,
    builtin: false,
    cells: data.cells.length,
    dropped: true
  };
}

/* ── the control ─────────────────────────────────────────────────────────── */

function setupCityPicker(cities) {
  App.cities = cities;

  const select = document.getElementById('city-select');
  if (select) {
    select.innerHTML = cities.map(c =>
      `<option value="${c.slug}">${c.name}${c.cost_basis_applies === false ? ' (costs N/A)' : ''}</option>`
    ).join('');
    if (App.city) select.value = App.city.slug;
    select.addEventListener('change', () => switchCity(select.value));
  }

  const input = document.getElementById('city-file');
  const openBtn = document.getElementById('btn-city-file');
  if (input && openBtn) {
    openBtn.addEventListener('click', () => input.click());
    input.addEventListener('change', () => {
      readCityFile(input.files && input.files[0]);
      input.value = '';   // so re-picking the same file fires change again
    });
  }

  setupDownloadMenu();
  setupDropZone();
  renderCityIdentity();
}

/* ── downloading the current city ────────────────────────────────────────── */

/* What a city ships, and where it actually lives.

   The point of the download is that a reader can check the dashboard's numbers
   against the file it drew them from. grid.geojson is what the map renders;
   dataset.csv is the per-cell measurements; ranking.csv is the funding order,
   which is the one a sceptic wants because it is the plan.

   Only files that are actually on the server are listed. The committed
   Guwahati build predates the per-city layout and ships only its grid under
   frontend/data -- its dataset.csv lives outside the web root and linking to
   it would 404. A dropped file has no server copy at all. */
function downloadableFiles(city) {
  if (!city || city.dropped) return [];
  if (city.builtin) {
    return [{ name: 'grid.geojson', href: city.path, note: 'the grid the map draws' }];
  }
  const dir = `data/cities/${city.slug}`;
  return [
    { name: 'grid.geojson', href: `${dir}/grid.geojson`, note: 'the grid the map draws' },
    { name: 'dataset.csv',  href: `${dir}/dataset.csv`,  note: 'per-cell measurements' },
    { name: 'ranking.csv',  href: `${dir}/ranking.csv`,  note: 'funding order — the plan' },
    { name: 'city.json',    href: `${dir}/city.json`,    note: 'provenance and headline figures' }
  ];
}

function setupDownloadMenu() {
  const btn = document.getElementById('btn-download');
  const menu = document.getElementById('download-menu');
  if (!btn || !menu) return;

  const close = () => { menu.hidden = true; btn.setAttribute('aria-expanded', 'false'); };

  btn.addEventListener('click', e => {
    e.stopPropagation();
    if (!menu.hidden) { close(); return; }
    renderDownloadMenu();
    menu.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
  });

  document.addEventListener('click', e => {
    if (!menu.hidden && !menu.contains(e.target)) close();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
}

function renderDownloadMenu() {
  const menu = document.getElementById('download-menu');
  const city = App.city || BUILTIN_CITY;
  const files = downloadableFiles(city);

  if (!files.length) {
    menu.innerHTML = `<p class="dl-empty">${escapeHtml(city.name)} was opened from a
      file on your own machine, so there is nothing to download — you already
      have it.</p>`;
    return;
  }

  menu.innerHTML = `
    <p class="dl-head">${escapeHtml(city.name)}</p>
    <ul>
      ${files.map(f => `
        <li><a href="${f.href}" download="${city.slug}-${f.name}">
          <b>${f.name}</b><i>${f.note}</i>
        </a></li>`).join('')}
    </ul>
    <p class="dl-foot">Served straight from this site — the same files the
      dashboard reads.</p>`;
}


/* Drop anywhere on the page, not just on a target.

   The map canvas swallows pointer events across most of the viewport, so a
   small drop target is both hard to hit and hard to find. The whole document
   accepts the file and a full-page overlay says so while a drag is in
   progress. */
function setupDropZone() {
  const overlay = document.getElementById('drop-overlay');
  if (!overlay) return;

  /* The overlay hides on a timer that `dragover` keeps resetting, rather than
     on a dragenter/dragleave counter.

     Counting was tried and it strands the overlay over the whole dashboard.
     dragenter and dragleave fire per element, so the obvious implementation
     counts them and hides at zero -- but a drag can end with no dragleave at
     all: cancelled with Escape, released outside the window, or dragged back
     out over a region the browser reports inconsistently. The count never
     returns to zero, the overlay never hides, and the only way out is a
     reload.

     A drag in progress fires dragover continuously, several times a second.
     So "no dragover for 200 ms" means the drag is over, whatever ended it and
     whether or not any event announced it. This cannot get stuck: the timer is
     always already scheduled by the time the overlay is visible. */
  let hideTimer = null;

  const show = () => {
    overlay.hidden = false;
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, 200);
  };
  const hide = () => {
    clearTimeout(hideTimer);
    hideTimer = null;
    overlay.hidden = true;
  };

  window.addEventListener('dragenter', e => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    show();
  });
  window.addEventListener('dragover', e => {
    if (!hasFiles(e)) return;
    /* Both preventDefaults are required. Without them the browser refuses the
       drop and falls back to navigating to the file. */
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    show();
  });
  window.addEventListener('drop', e => {
    if (!hasFiles(e)) return;
    /* Without this the browser navigates away from the dashboard to render the
       dropped JSON, which loses the whole session. */
    e.preventDefault();
    hide();
    readCityFile(e.dataTransfer.files && e.dataTransfer.files[0]);
  });

  /* Belt and braces for the cases that strand a drag: Escape cancels it, and
     a drag released outside the window ends it without a drop. */
  window.addEventListener('dragend', hide);
  window.addEventListener('blur', hide);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
}

function hasFiles(e) {
  const dt = e.dataTransfer;
  return !!dt && Array.from(dt.types || []).includes('Files');
}

/* ── identity and the cost-basis banner ──────────────────────────────────── */

/* The appbar strip and the banner both describe the current city, so they are
   written together and can only disagree if this function is wrong. */
function renderCityIdentity() {
  const city = App.city || BUILTIN_CITY;

  document.title = `Heatwise — Urban Heat Mitigation · ${city.name}`;

  const area = document.getElementById('meta-area');
  if (area) area.textContent = city.region ? `${city.name}, ${city.region}` : city.name;

  const grid = document.getElementById('meta-grid');
  if (grid) {
    const n = (city.cells || App.allCells.length || 0).toLocaleString();
    grid.textContent = `100 m · ${n} cells`;
  }

  const source = document.getElementById('meta-source');
  if (source) {
    source.textContent = city.source || 'unknown source';
    source.title = city.composite_window
      ? `Composite: ${city.composite_window[0]} to ${city.composite_window[1]}` +
        (city.composite_season ? ` · ${city.composite_season}` : '') +
        (city.scenes_used ? ` · ${city.scenes_used} scenes` : '')
      : '';
  }

  /* The dropdown has to name what is actually loaded. Leaving it on the last
     manifest city while a dropped file is on screen labels the view with the
     wrong city, which is the one thing this control exists to prevent. */
  const menu = document.getElementById('download-menu');
  if (menu && !menu.hidden) renderDownloadMenu();

  const select = document.getElementById('city-select');
  if (select) {
    let ghost = select.querySelector('option[value="__file__"]');
    if (city.dropped) {
      if (!ghost) {
        ghost = document.createElement('option');
        ghost.value = '__file__';
        select.insertBefore(ghost, select.firstChild);
      }
      ghost.textContent = `${city.name} (local file)`;
      select.value = '__file__';
    } else {
      if (ghost) ghost.remove();
      if (select.value !== city.slug) select.value = city.slug;
    }
  }

  renderCostBasisBanner(city);
}

/* The banner is the point of the whole feature.

   shared/constants.json prices interventions at Indian municipal rates in
   INR/m2. Those rates are real and sourced, and they are real *for India*.
   Phoenix is in the preset list deliberately as the worked example: its
   temperatures and land cover are measured and correct, its rupee totals are
   arithmetic on rates that do not apply there. A dashboard that renders
   "₹167 Cr" for Phoenix with no caveat is not wrong by a little.

   Three states, and only the money changes between them:
     true  — nothing shown, the rates apply
     false — red, costs are not valid here
     null  — amber, the file arrived without provenance so nothing vouches
             for its costs either way */
function renderCostBasisBanner(city) {
  const el = document.getElementById('cost-basis');
  if (!el) return;

  const applies = city.cost_basis_applies;
  if (applies === true) {
    el.hidden = true;
    el.className = 'cost-basis';
    document.body.dataset.costBasis = 'ok';
    return;
  }

  el.hidden = false;
  if (applies === false) {
    el.className = 'cost-basis is-invalid';
    document.body.dataset.costBasis = 'invalid';
    el.innerHTML = `
      <strong>Costs do not apply to ${escapeHtml(city.name)}.</strong>
      Unit rates are Indian municipal INR/m² from
      <code>shared/constants.json</code>. Temperature, vegetation and land
      cover here are measured and correct; every rupee figure below is
      arithmetic on rates from another country. Read the plan as a
      <em>ranking</em>, not a budget.`;
  } else {
    el.className = 'cost-basis is-unverified';
    document.body.dataset.costBasis = 'unverified';
    el.innerHTML = `
      <strong>Costs unverified.</strong>
      This grid was opened from a local file, so nothing records which rate
      card produced its <code>cost_estimate</code> values. Temperature and land
      cover are read straight from the file. Treat the totals as the file's own
      claim.`;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
