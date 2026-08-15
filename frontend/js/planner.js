/* MITIGATION PLAN — the decision panel.

   This is the product, not a sidebar. It answers the four questions the brief
   says the interface exists to answer: where is the problem, where do we
   intervene, what does it cost, how much cooling do we get.

   Every figure here is read from App.stats / App.plan. Nothing is computed
   locally, so this panel cannot disagree with the map or the analytics. */

function renderPlanner() {
  renderBudget();
  renderInterventions();
  renderPlanResult();
  renderDecisionSummary();
}

/* ── budget ──────────────────────────────────────────────────────────────── */

function renderBudget() {
  const el = document.getElementById('budget-control');
  if (!el) return;

  const needed = Math.max(App.stats ? App.stats.eligibleCost : 0, App.budget);

  /* Round the top of the range up to a whole step.
     A range input only lands on min + n*step, so a max that is not itself on
     that grid is unreachable: with the exact cost of every eligible cell
     (₹167.46 Cr) as max and ₹1 Cr as step, the slider stopped at ₹167.00 Cr.
     The plan could then never fund the last five cells however far the handle
     was dragged, and committed spend capped at ₹166.95 Cr against a programme
     that costs ₹167.46 Cr. */
  const ceiling = Math.ceil(needed / BUDGET_STEP) * BUDGET_STEP;

  const spent = App.plan ? App.plan.spent : 0;
  const pct = needed ? Math.min(100, (spent / needed) * 100) : 0;
  const fundsEverything = App.plan && App.plan.count === App.plan.available;

  el.innerHTML = `
    <div class="field-row">
      <label for="budget-input">Available budget</label>
      <output id="budget-value">${inrCrore(App.budget)}</output>
    </div>
    <input id="budget-input" type="range" min="0" max="${ceiling}"
           step="${BUDGET_STEP}" value="${Math.min(App.budget, ceiling)}"
           aria-label="Available budget in rupees">
    <div class="budget-bar" aria-hidden="true"><i style="width:${pct}%"></i></div>
    <div class="field-row sub">
      <span>Committed</span>
      <b>${inrCrore(spent)}</b>
    </div>
    <div class="field-row sub">
      <span>${fundsEverything ? 'Every eligible cell funded' : 'Unspent'}</span>
      <b>${fundsEverything ? '—' : inrCrore(App.plan ? App.plan.remaining : 0)}</b>
    </div>
    <div class="preset-row" role="group" aria-label="Budget scenarios">
      ${BUDGET_PRESETS.map(p => `
        <button type="button" data-budget="${p.value}"
                class="${App.budget === p.value ? 'is-on' : ''}"
                ${p.note ? `title="${p.note}"` : ''}>${p.label}</button>`).join('')}
    </div>
  `;

  const input = el.querySelector('#budget-input');
  const value = el.querySelector('#budget-value');
  /* Repaint the readout live while dragging, but only re-run the plan on
     release: the optimiser touches every eligible cell and the map redraws
     behind it, which is too much work for every pixel of a drag. */
  input.addEventListener('input', () => { value.textContent = inrCrore(+input.value); });
  input.addEventListener('change', () => setBudget(+input.value));

  el.querySelectorAll('[data-budget]').forEach(b => {
    b.addEventListener('click', () => setBudget(+b.dataset.budget));
  });
}

/* ── intervention mix ────────────────────────────────────────────────────── */

function renderInterventions() {
  const el = document.getElementById('intervention-list');
  if (!el) return;

  const rows = App.plan ? App.plan.rows : [];
  const byAction = Object.fromEntries(rows.map(r => [r.action, r]));

  el.innerHTML = INTERVENTION_ORDER.map(action => {
    const meta = interventionMeta(action);
    const row = byAction[action];

    if (!row) {
      /* The category exists in the catalogue but the rule engine never proposes
         it here. Saying so is more useful than hiding it, and inventing a number
         to fill the row is exactly what the brief forbids. */
      return `
        <li class="iv is-off" aria-disabled="true">
          <span class="iv-sym" style="--tint:${meta.tint}">
            <svg viewBox="0 0 16 16" aria-hidden="true">${meta.symbol}</svg>
          </span>
          <div class="iv-body">
            <p class="iv-name">${meta.label}</p>
            <p class="iv-note">${meta.unavailable || 'Not proposed in this study area.'}</p>
          </div>
        </li>`;
    }

    const on = App.enabled[action] !== false;
    return `
      <li class="iv${on ? '' : ' is-muted'}">
        <label class="iv-check">
          <input type="checkbox" data-iv="${action}" ${on ? 'checked' : ''}
                 aria-label="Include ${meta.label} in the plan">
        </label>
        <span class="iv-sym" style="--tint:${meta.tint}">
          <svg viewBox="0 0 16 16" aria-hidden="true">${meta.symbol}</svg>
        </span>
        <div class="iv-body">
          <p class="iv-name">${meta.label}</p>
          <p class="iv-note">${row.count.toLocaleString()} of ${row.available.toLocaleString()} sites funded</p>
        </div>
        <div class="iv-figs">
          <b>${inrCrore(row.cost)}</b>
          <span>${row.cooling.toFixed(0)} °C·cells</span>
        </div>
      </li>`;
  }).join('');

  el.querySelectorAll('[data-iv]').forEach(input => {
    input.addEventListener('change', () => toggleIntervention(input.dataset.iv, input.checked));
  });
}

/* ── optimiser result ────────────────────────────────────────────────────── */

function renderPlanResult() {
  const el = document.getElementById('plan-result');
  if (!el || !App.stats) return;

  const s = App.stats;
  const figures = [
    { v: s.fundedCount.toLocaleString(), k: 'Sites funded' },
    { v: inrCrore(s.fundedCost), k: 'Estimated cost' },
    { v: signedDrop(s.meanDropTreated), k: 'Mean cooling, funded cells' },
    { v: signedDrop(s.peakDrop), k: 'Peak cooling' }
  ];

  el.innerHTML = figures.map(f => `
    <div class="fig"><b>${f.v}</b><span>${f.k}</span></div>`).join('');
}

/* ── decision summary ────────────────────────────────────────────────────── */

function renderDecisionSummary() {
  const el = document.getElementById('decision-summary');
  if (!el || !App.stats) return;

  const s = App.stats;
  const hotspotDelta = s.hotspotsBefore - s.hotspotsAfter;

  el.innerHTML = `
    <div class="kpi-lead">
      <b>${signedDrop(s.meanDrop)}</b>
      <span>Projected mean reduction across ${s.n.toLocaleString()} cells</span>
    </div>
    <dl class="summary-list">
      <div><dt>Current mean</dt><dd>${degrees(s.meanTemp)}</dd></div>
      <div><dt>Projected mean</dt><dd>${degrees(s.meanAfter)}</dd></div>
      <div><dt>Priority cells treated</dt><dd>${s.fundedCount.toLocaleString()} of ${s.eligible.toLocaleString()} eligible</dd></div>
      <div><dt>Hotspot cells</dt><dd>${s.hotspotsBefore.toLocaleString()} → ${s.hotspotsAfter.toLocaleString()}${hotspotDelta > 0 ? ` <em>−${hotspotDelta}</em>` : ''}</dd></div>
      <div><dt>Estimated investment</dt><dd>${inrCrore(s.fundedCost)}</dd></div>
    </dl>
    <p class="caveat">Cooling values are planning assumptions used to compare
      scenarios, not measured guarantees.</p>
  `;
}

/* ── scope controls ──────────────────────────────────────────────────────── */

function renderScope() {
  const el = document.getElementById('scope-bar');
  if (!el) return;

  const label = document.getElementById('scope-label');
  if (label) label.textContent = scopeLabel();

  el.querySelectorAll('[data-priority]').forEach(b => {
    const on = b.dataset.priority === App.priority;
    b.classList.toggle('is-on', on);
    b.setAttribute('aria-pressed', String(on));
  });

  const clear = document.getElementById('btn-clear-area');
  if (clear) clear.hidden = !App.selection;
}

function setupScopeControls() {
  document.querySelectorAll('[data-priority]').forEach(b => {
    b.addEventListener('click', () => setPriority(b.dataset.priority));
  });
  const clear = document.getElementById('btn-clear-area');
  if (clear) clear.addEventListener('click', () => setSelection(null));
}
