/* Popup markup for a grid cell. */

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
    rows.push(['Expected drop', `−${cell.cooling.toFixed(1)}°C`]);
    rows.push(['After mitigation', `${(cell.temp - cell.cooling).toFixed(1)}°C`]);
    rows.push(['Est. cost', inrShort(cell.cost)]);
  }

  return `
    <div class="pop-badge" style="background:${priColor}22;color:${priColor}">${pri} priority</div>
    <div class="pop-title">${o.title || 'Grid cell'}</div>
    <div class="pop-sub">${cell.id || '—'} · ${cell.lat.toFixed(4)}, ${cell.lon.toFixed(4)}</div>
    ${rows.map(([k, v]) => `<div class="pop-row"><span>${k}</span><b>${v}</b></div>`).join('')}
  `;
}
