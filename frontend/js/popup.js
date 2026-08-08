function buildPopupContent(props) {
  return `
    <b>Grid ${props.grid_id}</b><br/>
    Temp: ${props.temperature}°C<br/>
    NDVI: ${props.ndvi}<br/>
    Priority: ${props.priority}<br/>
    Suggested: ${props.recommended_action}<br/>
    Est. cost: ₹${props.cost_estimate.toLocaleString()}
  `;
}

function buildPopupContent(props) {
  const temp = props.temperature ?? 'N/A';
  const ndvi = props.ndvi ?? 'N/A';
  const priority = props.priority ?? 'Unknown';
  const action = props.recommended_action ?? 'Not assessed';
  const cost = typeof props.cost_estimate === 'number'
    ? `₹${props.cost_estimate.toLocaleString()}`
    : 'N/A';

  return `
    <b>Grid ${props.grid_id ?? '—'}</b><br/>
    Temp: ${temp}°C<br/>
    NDVI: ${ndvi}<br/>
    Priority: ${priority}<br/>
    Suggested: ${action}<br/>
    Est. cost: ${cost}
  `;
}