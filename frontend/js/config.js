/* Shared constants: temperature ramp, intervention catalogue, formatters.

   Two colour systems, deliberately kept apart (see the redesign brief §14): the
   interface palette lives in style.css and is neutral, while the temperature
   ramp below encodes data and nothing else. Nothing in the chrome may borrow a
   ramp colour, or a reader stops being able to tell "this is hot" from "this is
   a button". */

/* Magma, sampled at six stops. Perceptually uniform and sequential — equal
   steps in temperature are equal steps in perceived brightness, which a
   blue-cyan-yellow-orange-red rainbow cannot claim: rainbows invent a bright
   band in the middle that reads as a feature in the data when it is an artefact
   of the palette. Magma is also the convention for thermal rasters, and its
   dark end still separates from a dark basemap. */
const HEAT_RAMP = [
  { t: 0.00, c: [ 40,  16,  74] },
  { t: 0.20, c: [ 94,  23, 108] },
  { t: 0.40, c: [148,  40, 108] },
  { t: 0.60, c: [204,  62,  91] },
  { t: 0.80, c: [246, 110,  92] },
  { t: 1.00, c: [252, 187, 140] }
];

/* Derived from the observed data, then held fixed so the current and mitigation
   surfaces stay directly comparable. Anchored on the 2nd/98th percentiles: the
   raw min-max is dominated by a handful of outliers and would collapse the whole
   city into the middle of the ramp. */
const TEMP_DOMAIN = { min: 23, max: 30 };

function setTempDomain(lo, hi) {
  const round = v => Math.round(v * 2) / 2;
  TEMP_DOMAIN.min = round(lo);
  TEMP_DOMAIN.max = round(hi);
  if (TEMP_DOMAIN.max - TEMP_DOMAIN.min < 2) TEMP_DOMAIN.max = TEMP_DOMAIN.min + 2;
}

function rampColor(t) {
  const x = Math.min(1, Math.max(0, t));
  for (let i = 1; i < HEAT_RAMP.length; i++) {
    if (x <= HEAT_RAMP[i].t) {
      const a = HEAT_RAMP[i - 1], b = HEAT_RAMP[i];
      const f = (x - a.t) / (b.t - a.t);
      return [
        Math.round(a.c[0] + (b.c[0] - a.c[0]) * f),
        Math.round(a.c[1] + (b.c[1] - a.c[1]) * f),
        Math.round(a.c[2] + (b.c[2] - a.c[2]) * f)
      ];
    }
  }
  return HEAT_RAMP[HEAT_RAMP.length - 1].c;
}

function rampCss(t) {
  const c = rampColor(t);
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function normTemp(t) {
  return (t - TEMP_DOMAIN.min) / (TEMP_DOMAIN.max - TEMP_DOMAIN.min);
}

/* The intervention catalogue.

   `label` follows the brief's category names; `action` is the string the
   pipeline emits and the only thing the data is keyed on — renaming the display
   label must never rename the key, or the rule engine and the UI silently stop
   agreeing.

   `cooling` is a fallback for data predating the pipeline's per-cell cooling_c.
   Both are planning assumptions, not measurements; see docs/08-limitations.md.

   Blue Infrastructure is listed because the brief names it as a category, and
   omitted from any count because the rule engine never emits it — WorldCover
   water and wetland cells are never-touch. Showing it with a fabricated figure
   would be exactly the invention the brief forbids. */
const INTERVENTIONS = {
  'Tree cover': {
    label: 'Tree Canopy',
    short: 'Canopy',
    cooling: 0.8,
    unit: 'per 100 m cell',
    /* Category tints. Desaturated on purpose: these are layer symbology, and
       they have to sit on top of the magma ramp without competing with it or
       being mistaken for a temperature. */
    tint: '#5E9E7E',
    /* GIS-style symbols: a filled square carrying a glyph, the way a layer
       swatch reads in ArcGIS — not a decorative pin. */
    symbol: '<path d="M8 13V9.5M8 9.5 5.4 7.6M8 9.5l2.6-1.9M8 3l3.6 5.2H4.4z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>'
  },
  'Green park': {
    label: 'Pocket Park',
    short: 'Park',
    cooling: 2.0,
    unit: 'per 100 m cell',
    tint: '#7BA05B',
    symbol: '<path d="M3 12.5h10M5.2 12.5c0-2.6 1.3-3.9 2.8-3.9s2.8 1.3 2.8 3.9M8 8.6V5.2" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
  },
  'Cool roof': {
    label: 'Cool Roof',
    short: 'Roof',
    cooling: 1.0,
    unit: 'per rooftop cluster',
    tint: '#6E93C8',
    symbol: '<path d="M2.6 7.6 8 3.2l5.4 4.4M4.6 7v5.8h6.8V7" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>'
  },
  'Blue infrastructure': {
    label: 'Blue Infrastructure',
    short: 'Water',
    cooling: 2.0,
    unit: 'per water feature',
    tint: '#4E93A8',
    unavailable: 'Water and wetland are never-touch land cover, so the rule engine never proposes this.',
    symbol: '<path d="M8 3s4 4.4 4 6.7a4 4 0 0 1-8 0C4 7.4 8 3 8 3z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>'
  },
  'None': {
    label: 'No action',
    short: 'None',
    cooling: 0,
    unit: '',
    tint: '#5A6678',
    symbol: '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
  }
};

/* Display order wherever interventions are listed, so the plan panel, the map
   legend and the analytics agree. */
const INTERVENTION_ORDER = ['Cool roof', 'Tree cover', 'Green park', 'Blue infrastructure'];

const PRIORITY_ORDER = ['High', 'Medium', 'Low'];

/* Land-cover labels for the inspector. Keys are the pipeline's normalised
   classes (see add_land_cover); anything unmapped falls through to the raw key
   rather than being hidden. */
const LAND_COVER_LABEL = {
  built_up: 'Built-up',
  tree_cover: 'Tree cover',
  cropland: 'Cropland',
  grassland: 'Grassland',
  water: 'Water',
  wetland: 'Wetland',
  bare_sparse: 'Bare / sparse'
};

function landCoverLabel(key) {
  return LAND_COVER_LABEL[key] || key || 'Unknown';
}

function interventionMeta(action) {
  return INTERVENTIONS[action] || INTERVENTIONS.None;
}

/* ── formatters ──────────────────────────────────────────────────────────── */

function inrShort(v) {
  if (typeof v !== 'number' || !isFinite(v)) return 'N/A';
  if (v >= 1e7) return '₹' + (v / 1e7).toFixed(2) + ' Cr';
  if (v >= 1e5) return '₹' + (v / 1e5).toFixed(2) + ' L';
  if (v >= 1e3) return '₹' + (v / 1e3).toFixed(1) + 'k';
  return '₹' + Math.round(v);
}

function inrCrore(v) {
  return '₹' + (v / 1e7).toFixed(2) + ' Cr';
}

function degrees(v, dp) {
  return v.toFixed(dp === undefined ? 1 : dp) + '°C';
}

function signedDrop(v) {
  return (v > 0 ? '−' : '') + Math.abs(v).toFixed(2) + '°C';
}
