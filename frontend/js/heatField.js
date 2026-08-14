/* HeatField — renders the grid as a continuous, cloud-like thermal surface.

   Each cell contributes a Gaussian blob to two float accumulators: one for
   weight, one for weight x temperature. Dividing them per pixel yields a
   smoothly interpolated temperature field (Shepard/Gaussian interpolation)
   rather than a density plot, so colour still means degrees Celsius.
   The result is upscaled with bilinear smoothing, which removes every trace
   of the underlying square lattice. */

const FIELD = {
  scale: 0.4,      // accumulator resolution vs. CSS pixels
  blend: 5.5,      // blur radius as a multiple of cell spacing
  padding: 0.14,   // offscreen margin so panning does not reveal edges
  opacity: 0.84,
  alphaRef: 0.30,  // fraction of peak density that counts as solid cloud
  alphaK: 2.6,     // how fast the cloud reaches full opacity
  passes: 3,       // box-blur passes; 3 approximates a true Gaussian
  blur: 2
};

/* Separable box blur with a running sum: O(1) per pixel regardless of radius,
   so the blend radius can be large enough to close the gaps in a sparse grid
   without the cost of splatting a kernel per cell. */
function boxBlurH(src, dst, w, h, r) {
  const norm = 1 / (2 * r + 1);
  for (let y = 0; y < h; y++) {
    const row = y * w;
    let sum = 0;
    for (let x = -r; x <= r; x++) sum += src[row + Math.min(w - 1, Math.max(0, x))];
    for (let x = 0; x < w; x++) {
      dst[row + x] = sum * norm;
      sum += src[row + Math.min(w - 1, x + r + 1)] - src[row + Math.max(0, x - r)];
    }
  }
}

function boxBlurV(src, dst, w, h, r) {
  const norm = 1 / (2 * r + 1);
  for (let x = 0; x < w; x++) {
    let sum = 0;
    for (let y = -r; y <= r; y++) sum += src[Math.min(h - 1, Math.max(0, y)) * w + x];
    for (let y = 0; y < h; y++) {
      dst[y * w + x] = sum * norm;
      sum += src[Math.min(h - 1, y + r + 1) * w + x] - src[Math.max(0, y - r) * w + x];
    }
  }
}

function blurField(buf, tmp, w, h, r, passes) {
  for (let i = 0; i < passes; i++) {
    boxBlurH(buf, tmp, w, h, r);
    boxBlurV(tmp, buf, w, h, r);
  }
}

const HeatField = L.Layer.extend({

  initialize(cells, options) {
    this._cells = cells || [];
    L.setOptions(this, options || {});
    this._index = null;
  },

  onAdd(map) {
    this._map = map;
    const canvas = this._canvas = L.DomUtil.create('canvas', 'heat-field');
    canvas.style.position = 'absolute';
    canvas.style.pointerEvents = 'none';
    canvas.style.opacity = FIELD.opacity;
    this._ctx = canvas.getContext('2d');

    map.getPanes().overlayPane.appendChild(canvas);
    map.on('moveend zoomend resize', this._reset, this);
    if (map.options.zoomAnimation && L.Browser.any3d) map.on('zoomanim', this._animateZoom, this);
    this._reset();
    return this;
  },

  onRemove(map) {
    map.off('moveend zoomend resize', this._reset, this);
    map.off('zoomanim', this._animateZoom, this);
    if (this._canvas && this._canvas.parentNode) this._canvas.parentNode.removeChild(this._canvas);
    this._canvas = this._ctx = this._map = null;
    return this;
  },

  setCells(cells) {
    this._cells = cells || [];
    this._index = null;
    if (this._map) this._reset();
    return this;
  },

  _animateZoom(e) {
    const map = this._map;
    const scale = map.getZoomScale(e.zoom, map.getZoom());
    const corner = map.containerPointToLatLng(this._padPoint.multiplyBy(-1));
    const offset = map._latLngToNewLayerPoint(corner, e.zoom, e.center);
    L.DomUtil.setTransform(this._canvas, offset, scale);
  },

  _reset() {
    const map = this._map;
    if (!map) return;

    const size = map.getSize();
    const padX = Math.round(size.x * FIELD.padding);
    const padY = Math.round(size.y * FIELD.padding);
    this._padPoint = L.point(padX, padY);

    const w = size.x + padX * 2;
    const h = size.y + padY * 2;

    const canvas = this._canvas;
    canvas.width = w;
    canvas.height = h;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';

    const corner = map.containerPointToLayerPoint(L.point(-padX, -padY));
    this._origin = corner;
    L.DomUtil.setTransform(canvas, corner, 1);

    this._draw(w, h, padX, padY);
  },

  /* Pixel spacing between neighbouring cells at the current zoom. */
  _cellSpacingPx() {
    const map = this._map;
    const c = this._cells[0];
    if (!c) return 8;
    const a = map.latLngToContainerPoint(L.latLng(c.bounds[0][0], c.bounds[0][1]));
    const b = map.latLngToContainerPoint(L.latLng(c.bounds[1][0], c.bounds[1][1]));
    return Math.max(2, Math.abs(b.x - a.x) || 8);
  },

  _draw(w, h, padX, padY) {
    const ctx = this._ctx;
    ctx.clearRect(0, 0, w, h);
    if (!this._cells.length) return;

    const map = this._map;
    const S = FIELD.scale;
    const bw = Math.max(1, Math.ceil(w * S));
    const bh = Math.max(1, Math.ceil(h * S));

    const R = Math.min(96, Math.max(2, Math.round(this._cellSpacingPx() * FIELD.blend * S)));

    const accW = new Float32Array(bw * bh);
    const accT = new Float32Array(bw * bh);

    /* Bilinear splat: one cell contributes to its four neighbouring samples so
       the field does not snap to the accumulator's integer lattice. */
    for (const cell of this._cells) {
      const p = map.latLngToContainerPoint(L.latLng(cell.lat, cell.lon));
      const cx = (p.x + padX) * S;
      const cy = (p.y + padY) * S;
      const x0 = Math.floor(cx), y0 = Math.floor(cy);
      if (x0 < -1 || y0 < -1 || x0 > bw || y0 > bh) continue;

      const fx = cx - x0, fy = cy - y0;
      const tn = normTemp(cell.temp);

      for (let dy = 0; dy < 2; dy++) {
        const y = y0 + dy;
        if (y < 0 || y >= bh) continue;
        const wy = dy ? fy : 1 - fy;
        for (let dx = 0; dx < 2; dx++) {
          const x = x0 + dx;
          if (x < 0 || x >= bw) continue;
          const wgt = wy * (dx ? fx : 1 - fx);
          const i = y * bw + x;
          accW[i] += wgt;
          accT[i] += wgt * tn;
        }
      }
    }

    const tmp = new Float32Array(bw * bh);
    blurField(accW, tmp, bw, bh, R, FIELD.passes);
    blurField(accT, tmp, bw, bh, R, FIELD.passes);

    let maxW = 0;
    for (let i = 0; i < accW.length; i++) if (accW[i] > maxW) maxW = accW[i];
    if (maxW <= 0) return;

    const img = ctx.createImageData(bw, bh);
    const px = img.data;
    const ref = maxW * FIELD.alphaRef;
    const k = FIELD.alphaK;
    const floor = maxW * 0.004;

    for (let i = 0, j = 0; i < accW.length; i++, j += 4) {
      const wsum = accW[i];
      if (wsum <= floor) continue;
      const rgb = rampColor(accT[i] / wsum);
      px[j] = rgb[0];
      px[j + 1] = rgb[1];
      px[j + 2] = rgb[2];
      px[j + 3] = (255 * (1 - Math.exp(-k * wsum / ref))) | 0;
    }

    /* Upscale the accumulator through an offscreen canvas so the browser's
       bilinear filter does the final smoothing pass. */
    const off = document.createElement('canvas');
    off.width = bw; off.height = bh;
    off.getContext('2d').putImageData(img, 0, 0);

    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    if (FIELD.blur) ctx.filter = `blur(${FIELD.blur}px)`;
    ctx.drawImage(off, 0, 0, bw, bh, 0, 0, w, h);
    ctx.restore();
  },

  /* Nearest-cell hit test, bucketed so clicks stay O(1). */
  cellAt(latlng) {
    if (!this._cells.length) return null;
    if (!this._index) this._buildIndex();

    const { size, minLat, minLon, cols, buckets } = this._index;
    const gx = Math.floor((latlng.lng - minLon) / size);
    const gy = Math.floor((latlng.lat - minLat) / size);

    let best = null, bestD = Infinity;
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        const list = buckets.get((gy + dy) * cols + (gx + dx));
        if (!list) continue;
        for (const c of list) {
          const a = c.lat - latlng.lat, b = c.lon - latlng.lng;
          const d = a * a + b * b;
          if (d < bestD) { bestD = d; best = c; }
        }
      }
    }
    return bestD <= size * size ? best : null;
  },

  _buildIndex() {
    const cells = this._cells;
    let minLat = Infinity, minLon = Infinity, maxLon = -Infinity;
    for (const c of cells) {
      if (c.lat < minLat) minLat = c.lat;
      if (c.lon < minLon) minLon = c.lon;
      if (c.lon > maxLon) maxLon = c.lon;
    }
    const c0 = cells[0];
    const size = Math.max(1e-5, (c0.bounds[1][1] - c0.bounds[0][1]) * 2);
    const cols = Math.max(1, Math.ceil((maxLon - minLon) / size) + 3);

    const buckets = new Map();
    for (const c of cells) {
      const key = Math.floor((c.lat - minLat) / size) * cols + Math.floor((c.lon - minLon) / size);
      const list = buckets.get(key);
      if (list) list.push(c); else buckets.set(key, [c]);
    }
    this._index = { size, minLat, minLon, cols, buckets };
  }
});

function heatField(cells, options) {
  return new HeatField(cells, options);
}
