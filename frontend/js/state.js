/* The single authoritative application state.

   Every number the interface shows is derived here and read from here. Nothing
   recomputes a cell count, a cost or a mean of its own — that is what let the
   old dashboard print one cell count in the header and a different one in the
   analytics panel, which is precisely the inconsistency the redesign brief calls
   out as fatal for judge confidence (§12).

   The rule is: panels render, they do not calculate. */

const App = {
  /* data */
  allCells: [],
  release: null,
  bounds: null,
  center: null,

  /* scope */
  priority: 'All',
  selection: null,          // L.LatLngBounds, or null for the whole study area
  scopeCells: [],           // allCells narrowed by priority + selection

  /* plan */
  budget: 100000000,        // ₹10 Cr — the pipeline's BUDGET_RUPEES, so a fresh
                            // load agrees with the committed ranking.csv
  enabled: { 'Cool roof': true, 'Tree cover': true, 'Green park': true },
  funded: new Set(),        // grid_ids the budget pays for
  plan: null,               // per-action rollup of the funded set

  /* view */
  layers: { temperature: true, interventions: true, priority: false, labels: true },
  heatMode: 'field',
  compare: 0.5,             // Current → Mitigation divider, 0..1

  /* derived */
  stats: null,

  _subs: []
};

/* Budget presets. ₹10 Cr is the pipeline's own cap and the figure every
   document quotes; the rest let a judge ask "what would twice the money buy?"
   without the app inventing an answer — each one is the same greedy selection
   re-run against real per-cell costs. */
const BUDGET_PRESETS = [
  { label: '₹10 Cr', value: 100000000, note: 'committed plan' },
  { label: '₹25 Cr', value: 250000000, note: null },
  { label: '₹50 Cr', value: 500000000, note: null },
  { label: '₹100 Cr', value: 1000000000, note: null }
];

/* Slider granularity, ₹1 Cr. The range's max is rounded up to a multiple of
   this so the top of the track is actually reachable — see renderBudget(). */
const BUDGET_STEP = 10000000;

function onStateChange(fn) {
  App._subs.push(fn);
}

function emitStateChange(reason) {
  for (const fn of App._subs) fn(reason);
}

/* ── scope ───────────────────────────────────────────────────────────────── */

function recomputeScope() {
  let cells = App.allCells;
  if (App.priority !== 'All') cells = cells.filter(c => c.priority === App.priority);
  if (App.selection) cells = cellsInBounds(cells, App.selection);
  App.scopeCells = cells;
}

/* ── the optimiser ───────────────────────────────────────────────────────── */

/* Greedy fill of the budget in the pipeline's own priority order.

   The order is NOT recomputed here. `rank` comes from plan_rank in the grid,
   which export_grid_geojson.py derives with the same keys as
   rank_within_budget() — cooling per rupee, then temperature, then grid_id — at
   full precision.

   Re-deriving it client-side was tried and is wrong: `temperature` ships at 1 dp
   because that is what the UI prints, and cooling_per_rupee has only three
   distinct values, so thousands of cells tie at a precision the pipeline never
   saw. Sorting on those fields produced a funded set with the same size, the
   same cost and the same mean cooling as ranking.csv — and not one cell in
   common. Sorting on the exported rank makes that class of disagreement
   structurally impossible.

   Filtering by area, priority or intervention type just removes candidates; the
   surviving cells keep their relative order, so a filtered plan is still the
   pipeline's plan. */
function optimisePlan() {
  const eligible = App.scopeCells.filter(
    c => c.cooling > 0 && c.rank > 0 && App.enabled[c.action] !== false
  );

  eligible.sort((a, b) => a.rank - b.rank);

  const funded = new Set();
  let spent = 0;
  for (const c of eligible) {
    if (spent + c.cost > App.budget) continue;   // skip, keep filling — matches
    funded.add(c.id);                            // the cumulative-cost cut-off
    spent += c.cost;
  }

  App.funded = funded;
  App.plan = rollUpPlan(eligible, funded);
  return App.plan;
}

/* Per-action rollup: what the plan buys, and what it leaves on the table. */
function rollUpPlan(eligible, funded) {
  const rows = {};
  for (const c of eligible) {
    const r = rows[c.action] || (rows[c.action] = {
      action: c.action,
      available: 0, availableCost: 0,
      count: 0, cost: 0, cooling: 0
    });
    r.available++;
    r.availableCost += c.cost;
    if (funded.has(c.id)) {
      r.count++;
      r.cost += c.cost;
      r.cooling += c.cooling;
    }
  }

  const list = INTERVENTION_ORDER
    .filter(a => rows[a])
    .map(a => rows[a]);

  const spent = list.reduce((s, r) => s + r.cost, 0);
  return {
    rows: list,
    spent,
    remaining: Math.max(0, App.budget - spent),
    count: list.reduce((s, r) => s + r.count, 0),
    available: list.reduce((s, r) => s + r.available, 0)
  };
}

/* ── the one recompute ───────────────────────────────────────────────────── */

function refresh(reason) {
  recomputeScope();
  optimisePlan();
  App.stats = summarize(App.scopeCells, App.funded);
  emitStateChange(reason || 'refresh');
}

/* ── mutators — the only supported way to change anything ────────────────── */

function setPriority(p) {
  App.priority = p;
  refresh('priority');
}

function setSelection(bounds) {
  App.selection = bounds;
  refresh('selection');
}

function setBudget(rupees) {
  App.budget = Math.max(0, Math.round(rupees));
  refresh('budget');
}

function toggleIntervention(action, on) {
  App.enabled[action] = on;
  refresh('interventions');
}

function setLayer(name, on) {
  App.layers[name] = on;
  emitStateChange('layers');
}

function setHeatMode(mode) {
  App.heatMode = mode;
  emitStateChange('heatMode');
}

function setCompare(fraction) {
  App.compare = Math.min(1, Math.max(0, fraction));
  emitStateChange('compare');
}

/* The scope label every panel shows, so they cannot describe it differently. */
function scopeLabel() {
  const parts = [];
  parts.push(App.selection ? 'Selected area' : 'Whole study area');
  if (App.priority !== 'All') parts.push(`${App.priority} priority`);
  return parts.join(' · ');
}
