/* Minimal slippy map in plain JavaScript: OpenStreetMap tiles, drag, wheel/button zoom, markers. */
class TileMap {
  constructor(el, lat, lng, zoom) {
    this.el = el; this.lat = lat; this.lng = lng; this.z = zoom;
    this.minZ = 10; this.maxZ = 18; this.tiles = new Map(); this.groups = {};
    this.onClick = null; this.moved = false;
    el.classList.add('tmap');
    this.tileLayer = this._div('tm-tiles'); this.markerLayer = this._div('tm-markers');
    const ctl = this._div('tm-ctl');
    [['+', 'Zoom in', 1], ['\u2212', 'Zoom out', -1]].forEach(([t, label, d]) => {
      const b = document.createElement('button');
      b.textContent = t; b.title = label; b.setAttribute('aria-label', label);
      b.onclick = e => { e.stopPropagation(); this.zoomBy(d); };
      b.onpointerdown = e => e.stopPropagation();
      ctl.appendChild(b);
    });
    const attr = this._div('tm-attr'); attr.textContent = '\u00A9 OpenStreetMap contributors';
    el.addEventListener('pointerdown', e => this._down(e));
    el.addEventListener('wheel', e => { e.preventDefault(); this.zoomBy(e.deltaY < 0 ? 1 : -1); }, {passive: false});
    new ResizeObserver(() => this.draw()).observe(el);
    this.draw();
  }
  _div(cls) { const d = document.createElement('div'); d.className = cls; this.el.appendChild(d); return d; }
  proj(lat, lng, z = this.z) {
    const s = 256 * 2 ** z, sin = Math.sin(lat * Math.PI / 180);
    return {x: (lng + 180) / 360 * s, y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * s};
  }
  unproj(x, y, z = this.z) {
    const s = 256 * 2 ** z, n = Math.PI - 2 * Math.PI * y / s;
    return {lat: 180 / Math.PI * Math.atan(Math.sinh(n)), lng: x / s * 360 - 180};
  }
  _origin() {
    const c = this.proj(this.lat, this.lng), r = this.el.getBoundingClientRect();
    return {x: c.x - r.width / 2, y: c.y - r.height / 2, w: r.width, h: r.height};
  }
  setView(lat, lng, z) { this.lat = lat; this.lng = lng; if (z) this.z = Math.min(this.maxZ, Math.max(this.minZ, z)); this.draw(); }
  zoomBy(d) { this.setView(this.lat, this.lng, this.z + d); }
  draw() {
    const o = this._origin(), z = this.z, n = 2 ** z, need = new Set();
    for (let tx = Math.floor(o.x / 256); tx <= Math.floor((o.x + o.w) / 256); tx++) {
      for (let ty = Math.floor(o.y / 256); ty <= Math.floor((o.y + o.h) / 256); ty++) {
        if (ty < 0 || ty >= n) continue;
        const key = `${z}/${tx}/${ty}`; need.add(key);
        let img = this.tiles.get(key);
        if (!img) {
          img = new Image(); img.draggable = false; img.alt = '';
          img.src = `https://tile.openstreetmap.org/${z}/${((tx % n) + n) % n}/${ty}.png`;
          this.tileLayer.appendChild(img); this.tiles.set(key, img);
        }
        img.style.left = (tx * 256 - o.x) + 'px'; img.style.top = (ty * 256 - o.y) + 'px';
      }
    }
    for (const [k, img] of this.tiles) if (!need.has(k)) { img.remove(); this.tiles.delete(k); }
    this._place(o);
  }
  _place(o = this._origin()) {
    Object.values(this.groups).flat().forEach(it => {
      const p = this.proj(it.lat, it.lng);
      it.el.style.left = (p.x - o.x) + 'px'; it.el.style.top = (p.y - o.y) + 'px';
    });
  }
  /* items: [{lat, lng, size, color, title, label, cls, onClick}] */
  setMarkers(group, items) {
    (this.groups[group] || []).forEach(it => it.el.remove());
    this.groups[group] = items.map(it => {
      const el = document.createElement('div');
      el.className = 'tm-marker ' + (it.cls || '');
      el.style.width = el.style.height = it.size + 'px';
      el.style.background = it.color;
      if (it.title) el.title = it.title;
      if (it.label) { const s = document.createElement('span'); s.className = 'tm-label'; s.textContent = it.label; el.appendChild(s); }
      el.addEventListener('click', e => { e.stopPropagation(); if (!this.moved && it.onClick) it.onClick(); });
      this.markerLayer.appendChild(el);
      return {...it, el};
    });
    this._place();
  }
  setSelected(group, index) {
    (this.groups[group] || []).forEach((it, i) => it.el.classList.toggle('sel', i === index));
  }
  _down(e) {
    if (e.button > 0) return;
    const start = {x: e.clientX, y: e.clientY}, c0 = this.proj(this.lat, this.lng);
    this.moved = false;
    const move = ev => {
      const dx = ev.clientX - start.x, dy = ev.clientY - start.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) this.moved = true;
      if (this.moved) { const p = this.unproj(c0.x - dx, c0.y - dy); this.lat = p.lat; this.lng = p.lng; this.draw(); }
    };
    const up = ev => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up);
      if (!this.moved && this.onClick && !ev.target.closest('.tm-marker')) {
        const r = this.el.getBoundingClientRect(), o = this._origin();
        const p = this.unproj(o.x + ev.clientX - r.left, o.y + ev.clientY - r.top);
        this.onClick(p.lat, p.lng);
      }
    };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  }
}
