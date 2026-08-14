/* Shared constants: colour ramp, intervention model, ecology catalogue. */

const HEAT_RAMP = [
  { t: 0.00, c: [37, 99, 235] },
  { t: 0.28, c: [34, 211, 238] },
  { t: 0.55, c: [253, 224, 71] },
  { t: 0.78, c: [251, 146, 60] },
  { t: 1.00, c: [239, 68, 68] }
];

/* Derived once from the observed data, then held fixed so the current and
   predicted surfaces stay directly comparable. Anchored on the 2nd/98th
   percentiles: the raw min-max is dominated by a handful of outliers and
   would collapse the whole city into the middle of the ramp. */
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

function normTemp(t) {
  return (t - TEMP_DOMAIN.min) / (TEMP_DOMAIN.max - TEMP_DOMAIN.min);
}

/* Planning-grade cooling model. Values are indicative mean LST reductions for a
   fully implemented measure at 100 m cell scale, not calibrated field results. */
const INTERVENTIONS = {
  'Tree cover':  { cooling: 2.4, color: '#34D399', label: 'Urban tree canopy',   unit: 'per 100 m cell' },
  'Green park':  { cooling: 1.8, color: '#4ADE80', label: 'Green park / lawn',   unit: 'per 100 m cell' },
  'Cool roof':   { cooling: 2.9, color: '#60A5FA', label: 'High-albedo roof',    unit: 'per rooftop cluster' },
  'Green roof':  { cooling: 1.5, color: '#A3E635', label: 'Vegetated roof',      unit: 'per rooftop cluster' },
  'Water body':  { cooling: 2.2, color: '#22D3EE', label: 'Retention pond',      unit: 'per water feature' },
  'None':        { cooling: 0,   color: '#64748B', label: 'No action',           unit: '' }
};

const PRIORITY_COLOR = { High: '#F87171', Medium: '#FBBF24', Low: '#34D399' };

/* SVG glyphs for the ecology pointers (no emoji — see design system). */
const ECO_ICONS = {
  'Tree cover': '<path d="M12 20v-5M12 15l-4-3M12 15l4-3M12 3l6 9H6z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  'Green park': '<path d="M4 18h16M7 18c0-4 2-6 5-6s5 2 5 6M12 12V7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'Cool roof':  '<path d="M3 11l9-7 9 7M6 10v9h12v-9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  'Green roof': '<path d="M3 11l9-7 9 7M6 10v9h12v-9M9 14c1.5 0 3-1 3-3 0 2 1.5 3 3 3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  'Water body': '<path d="M12 3s6 6.5 6 10a6 6 0 0 1-12 0c0-3.5 6-10 6-10z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
  'None':       '<circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" stroke-width="2"/>'
};

function inrShort(v) {
  if (typeof v !== 'number' || !isFinite(v)) return 'N/A';
  if (v >= 1e7) return '₹' + (v / 1e7).toFixed(2) + ' Cr';
  if (v >= 1e5) return '₹' + (v / 1e5).toFixed(2) + ' L';
  if (v >= 1e3) return '₹' + (v / 1e3).toFixed(1) + 'k';
  return '₹' + Math.round(v);
}
