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