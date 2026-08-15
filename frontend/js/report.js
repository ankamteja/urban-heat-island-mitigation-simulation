/* Export report and methodology drawer.

   There is no backend, so the report is generated in the page and handed to the
   browser's own print-to-PDF. That is a real export — nothing is stubbed, and
   nothing promises a server round-trip that does not exist (§18).

   The map snapshot is composited from the thermal canvases this app draws
   itself. Basemap tiles are cross-origin and would taint the canvas, so
   toDataURL() on a composite including them throws. The snapshot is therefore
   the data layer only, and the report says so rather than shipping a picture
   the reader would assume includes streets. */

function snapshotSurfaces() {
  const map = mapView.map;
  if (!map) return null;

  const size = map.getSize();
  const out = document.createElement('canvas');
  out.width = size.x;
  out.height = size.y;
  const ctx = out.getContext('2d');

  ctx.fillStyle = '#0C1017';
  ctx.fillRect(0, 0, out.width, out.height);

  const divX = Math.round(size.x * App.compare);

  const paint = (field, clipFrom, clipTo, alpha) => {
    const c = field && field._canvas;
    if (!c) return;
    const originPt = map.containerPointToLayerPoint([0, 0]);
    const rect = c.getBoundingClientRect();
    const mapRect = map.getContainer().getBoundingClientRect();
    const dx = rect.left - mapRect.left;
    const dy = rect.top - mapRect.top;

    ctx.save();
    ctx.beginPath();
    ctx.rect(clipFrom, 0, clipTo - clipFrom, out.height);
    ctx.clip();
    ctx.globalAlpha = alpha;
    ctx.drawImage(c, dx, dy, rect.width, rect.height);
    ctx.restore();
    void originPt;
  };

  const heatAlpha = App.heatMode === 'grid' ? 0.34 : 0.62;
  paint(mapView.current, 0, divX, heatAlpha);
  paint(mapView.mitigated, divX, size.x, heatAlpha);
  paint(mapView.sites, 0, size.x, 1);

  // divider, so the reader can see which half is which
  ctx.strokeStyle = 'rgba(232,234,240,.9)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(divX + 0.5, 0);
  ctx.lineTo(divX + 0.5, out.height);
  ctx.stroke();

  try {
    return out.toDataURL('image/png');
  } catch (err) {
    console.warn('Snapshot failed', err);
    return null;
  }
}

function reportHtml() {
  const s = App.stats;
  const plan = App.plan;
  const snap = snapshotSurfaces();
  const release = App.release || {};
  const now = new Date().toISOString().slice(0, 10);

  const rows = (plan ? plan.rows : []).filter(r => r.count > 0).map(r => {
    const m = interventionMeta(r.action);
    return `<tr>
      <td>${m.label}</td>
      <td class="n">${r.count.toLocaleString()}</td>
      <td class="n">${r.available.toLocaleString()}</td>
      <td class="n">${inrCrore(r.cost)}</td>
      <td class="n">${r.cooling.toFixed(0)} °C·cells</td>
    </tr>`;
  }).join('');

  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Heat mitigation plan — Guwahati — ${now}</title>
<style>
  @page { margin: 18mm; }
  body { font: 12px/1.55 -apple-system, "Segoe UI", system-ui, sans-serif; color: #16181d; max-width: 190mm; }
  h1 { font-size: 20px; margin: 0 0 2px; }
  h2 { font-size: 13px; margin: 22px 0 6px; text-transform: uppercase; letter-spacing: .07em; color: #5a6272; }
  .sub { color: #5a6272; margin: 0 0 18px; }
  table { border-collapse: collapse; width: 100%; margin-top: 4px; }
  th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid #dcdfe5; }
  th { font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; color: #5a6272; }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px 24px; }
  .grid div { display: flex; justify-content: space-between; border-bottom: 1px solid #eceef2; padding: 4px 0; }
  .grid dt { color: #5a6272; }
  .grid dd { margin: 0; font-weight: 600; font-variant-numeric: tabular-nums; }
  img { width: 100%; border: 1px solid #dcdfe5; margin-top: 6px; }
  .note { color: #5a6272; font-size: 11px; margin-top: 6px; }
  .caveat { border-left: 3px solid #c9822b; background: #fdf6ec; padding: 8px 12px; margin-top: 18px; font-size: 11.5px; }
  footer { margin-top: 24px; padding-top: 8px; border-top: 1px solid #dcdfe5; color: #5a6272; font-size: 10.5px; }
</style></head><body>

<h1>Urban heat mitigation plan</h1>
<p class="sub">Guwahati, Assam · 100 m grid · Landsat-derived surface temperature · generated ${now}</p>

<h2>Scope</h2>
<div class="grid">
  <div><dt>Area</dt><dd>${scopeLabel()}</dd></div>
  <div><dt>Cells analysed</dt><dd>${s.n.toLocaleString()}</dd></div>
  <div><dt>Mean surface temperature</dt><dd>${degrees(s.meanTemp)}</dd></div>
  <div><dt>Peak</dt><dd>${degrees(s.maxTemp)}</dd></div>
  <div><dt>Hotspot cells (top decile)</dt><dd>${s.hotspotsBefore.toLocaleString()}</dd></div>
  <div><dt>Eligible for intervention</dt><dd>${s.eligible.toLocaleString()}</dd></div>
</div>

<h2>Selected plan</h2>
<div class="grid">
  <div><dt>Budget</dt><dd>${inrCrore(App.budget)}</dd></div>
  <div><dt>Estimated cost</dt><dd>${inrCrore(s.fundedCost)}</dd></div>
  <div><dt>Sites funded</dt><dd>${s.fundedCount.toLocaleString()}</dd></div>
  <div><dt>Unspent</dt><dd>${inrCrore(plan ? plan.remaining : 0)}</dd></div>
</div>

<table>
  <thead><tr><th>Measure</th><th class="n">Funded</th><th class="n">Eligible</th><th class="n">Cost</th><th class="n">Cooling</th></tr></thead>
  <tbody>${rows || '<tr><td colspan="5">No measures funded at this budget.</td></tr>'}</tbody>
</table>

<h2>Projected impact</h2>
<div class="grid">
  <div><dt>Mean reduction, funded cells</dt><dd>${signedDrop(s.meanDropTreated)}</dd></div>
  <div><dt>Mean reduction, all cells in scope</dt><dd>${signedDrop(s.meanDrop)}</dd></div>
  <div><dt>Projected mean temperature</dt><dd>${degrees(s.meanAfter)}</dd></div>
  <div><dt>Hotspot cells after plan</dt><dd>${s.hotspotsAfter.toLocaleString()}</dd></div>
</div>

${snap ? `<h2>Thermal surface</h2>
<img src="${snap}" alt="Current surface left of the divider, post-plan surface right of it">
<p class="note">Data layers only — current surface left of the divider, projected
surface right of it. Basemap tiles are omitted because they are served
cross-origin and cannot be composited into an exportable image.</p>` : ''}

<h2>Method</h2>
<p class="note">${METHODOLOGY.map(m => `<strong>${m.k}:</strong> ${m.v}`).join('<br>')}</p>

<div class="caveat">
  <strong>Cooling values are planning assumptions used to compare scenarios, not
  measured guarantees.</strong> They were not fitted to Guwahati or validated
  against a field trial. The measurement layer — surface temperature, vegetation
  and land cover — is observed; the intervention layer is modelled.
</div>

<footer>
  Data release ${release.release_id || 'unknown'} ·
  ${release.cell_count ? release.cell_count.toLocaleString() + ' cells' : ''} ·
  Generated from the live dashboard. Source and full limitations:
  github.com/ankamteja/urban-heat-island-mitigation-simulation
</footer>

</body></html>`;
}

function exportReport() {
  if (!App.stats) return;
  const w = window.open('', '_blank');
  if (!w) {
    alertInline('Allow pop-ups to export the report.');
    return;
  }
  w.document.write(reportHtml());
  w.document.close();
  w.focus();
  /* Let layout and the snapshot image settle before the print dialog, or the
     first page renders without the map. */
  setTimeout(() => w.print(), 350);
}

/* ── methodology ─────────────────────────────────────────────────────────── */

const METHODOLOGY = [
  { k: 'Satellite data', v: 'Landsat 8 Collection 2 surface reflectance and thermal bands, composited in Google Earth Engine.' },
  { k: 'Spatial resolution', v: '100 m analysis grid, 8,144 cells over the Guwahati study area.' },
  { k: 'Surface temperature', v: 'Land surface temperature from the thermal band; this is skin temperature, not air temperature.' },
  { k: 'Vegetation and built-up', v: 'NDVI and NDBI from the same scene. ESA WorldCover supplies land cover.' },
  { k: 'Heat prediction model', v: 'RandomForest regression. R² 0.895 on a random split, 0.513 under a spatial-block split — the blocked figure is the honest one, because adjacent 100 m cells are near-duplicates.' },
  { k: 'Model role', v: 'Diagnostic. The visible recommendation comes from the land-cover rule engine and the cost table, not from the model.' },
  { k: 'Intervention suitability', v: 'Gated on ESA WorldCover: no measure is proposed on water, wetland or existing tree cover.' },
  { k: 'Mitigation optimisation', v: 'Greedy selection by cooling per rupee, ties broken by surface temperature descending, capped at the selected budget.' },
  { k: 'Observation window', v: 'A single thermal scene. Results describe one moment, not a seasonal trend.' }
];

function renderMethodology(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `
    <dl class="method-list">
      ${METHODOLOGY.map(m => `<div><dt>${m.k}</dt><dd>${m.v}</dd></div>`).join('')}
    </dl>
    <p class="method-foot">Full limitations and data contracts are documented in
      the repository under <code>docs/</code>.</p>
  `;
}

function alertInline(message) {
  const el = document.getElementById('app-toast');
  if (!el) return;
  el.textContent = message;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 4000);
}
