/* Drag-a-box area selection on the current-conditions map.
   Selecting an area is what unlocks the prediction pane. */

function createAreaSelector(map, paneEl, callbacks) {
  const onSelect = callbacks.onSelect || (() => {});
  const onStateChange = callbacks.onStateChange || (() => {});

  let armed = false;
  let dragging = false;
  let startPt = null;
  let band = null;
  let highlight = null;

  function setArmed(next) {
    if (armed === next) return;
    armed = next;

    if (armed) {
      map.dragging.disable();
      map.doubleClickZoom.disable();
      paneEl.addEventListener('mousedown', onDown);
      document.addEventListener('keydown', onKey);
    } else {
      map.dragging.enable();
      map.doubleClickZoom.enable();
      paneEl.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
      cleanupBand();
    }
    onStateChange(armed);
  }

  function onKey(e) {
    if (e.key === 'Escape') setArmed(false);
  }

  function localPoint(e) {
    const r = paneEl.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  function onDown(e) {
    if (e.button !== 0) return;
    e.preventDefault();
    dragging = true;
    startPt = localPoint(e);

    band = document.createElement('div');
    band.className = 'sel-band';
    paneEl.appendChild(band);
    paint(startPt);

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  function paint(cur) {
    if (!band) return;
    const x = Math.min(startPt.x, cur.x), y = Math.min(startPt.y, cur.y);
    band.style.left = x + 'px';
    band.style.top = y + 'px';
    band.style.width = Math.abs(cur.x - startPt.x) + 'px';
    band.style.height = Math.abs(cur.y - startPt.y) + 'px';
  }

  function onMove(e) {
    if (!dragging) return;
    paint(localPoint(e));
  }

  function onUp(e) {
    if (!dragging) return;
    dragging = false;
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);

    const end = localPoint(e);
    const dx = Math.abs(end.x - startPt.x);
    const dy = Math.abs(end.y - startPt.y);
    cleanupBand();

    if (dx < 18 || dy < 18) { setArmed(false); return; }

    const bounds = L.latLngBounds(
      map.containerPointToLatLng(L.point(startPt.x, startPt.y)),
      map.containerPointToLatLng(L.point(end.x, end.y))
    );

    setArmed(false);
    showHighlight(bounds);
    onSelect(bounds);
  }

  function cleanupBand() {
    if (band && band.parentNode) band.parentNode.removeChild(band);
    band = null;
  }

  function showHighlight(bounds) {
    clearHighlight();
    highlight = L.rectangle(bounds, {
      color: '#FBBF24', weight: 1.5, dashArray: '5 4', fill: false, interactive: false
    }).addTo(map);
  }

  function clearHighlight() {
    if (highlight) { map.removeLayer(highlight); highlight = null; }
  }

  return {
    toggle: () => setArmed(!armed),
    disarm: () => setArmed(false),
    isArmed: () => armed,
    clearHighlight,
    showHighlight
  };
}

function cellsInBounds(cells, bounds) {
  const s = bounds.getSouth(), n = bounds.getNorth();
  const w = bounds.getWest(), e = bounds.getEast();
  return cells.filter(c => c.lat >= s && c.lat <= n && c.lon >= w && c.lon <= e);
}
