/* Website Dashboard (HTML + CSS + JavaScript, no libraries): live data, risk map, alerts & reports */
const COLORS = {Low: '#2e8b6e', Moderate: '#d9a520', High: '#df6f2a', Severe: '#c2362f'};
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const num = (v, d = 1) => v == null ? '\u2013' : Number(v).toFixed(d);

const map = new TileMap($('map'), 19.06, 72.86, 12);
let zones = [], pick = null, selectedId = null;

async function api(path, opts) {
  const r = await fetch('/api' + path, opts);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || 'Request failed');
  return data;
}
const post = (path, body = {}) => api(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});

/* ---------- zones: map + table ---------- */
function renderZones() {
  const shown = zones.filter(z => z.risk_level);
  map.setMarkers('zones', shown.map(z => ({
    lat: z.lat, lng: z.lng, size: 18 + z.risk_score / 4, color: COLORS[z.risk_level],
    title: `${z.name}: ${z.risk_level} (${num(z.risk_score, 0)})`, label: z.name, onClick: () => selectZone(z.id)
  })));
  map.setSelected('zones', shown.findIndex(z => z.id === selectedId));
  $('zoneRows').innerHTML = zones.map(z => `
    <tr data-id="${z.id}">
      <td>${esc(z.name)}</td>
      <td>${z.risk_level ? `<span class="pill ${z.risk_level}">${z.risk_level}</span>` : '\u2013'}</td>
      <td>${num(z.risk_score, 0)}</td><td>${num(z.ponding_cm, 0)} cm</td>
      <td>${num(z.rain_1h)} mm</td><td>${num(z.rain_24h)} mm</td><td>${num(z.forecast_3h)} mm</td>
      <td>${num(z.blockage_pct, 0)}%</td>
    </tr>`).join('');
  document.querySelectorAll('#zoneRows tr').forEach(tr => tr.onclick = () => selectZone(+tr.dataset.id, true));
  const latest = zones.filter(z => z.predicted_at).sort((a, b) => a.predicted_at < b.predicted_at ? 1 : -1)[0];
  $('updated').textContent = latest
    ? `${latest.source === 'simulated' ? 'Simulated storm, ' : 'Live data, '}updated ${new Date(latest.predicted_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`
    : 'No data yet. Press Refresh live data.';
}

async function selectZone(id, pan) {
  selectedId = id;
  const z = zones.find(x => x.id === id);
  if (!z) return;
  if (pan) map.setView(z.lat, z.lng, 14);
  map.setSelected('zones', zones.filter(x => x.risk_level).findIndex(x => x.id === id));
  $('detailTitle').textContent = z.name;
  $('detail').className = '';
  $('detail').innerHTML = `
    <span class="pill ${z.risk_level}">${z.risk_level || 'No data'}</span> score ${num(z.risk_score, 0)} / 100
    <div class="kv">
      <span>Possible water depth</span><b>${num(z.ponding_cm, 0)} cm</b>
      <span>Rain in last hour</span><b>${num(z.rain_1h)} mm</b>
      <span>Rain in last 24 h</span><b>${num(z.rain_24h)} mm</b>
      <span>Forecast next 3 h</span><b>${num(z.forecast_3h)} mm</b>
      <span>Ground saturation</span><b>${num((z.soil_saturation || 0) * 100, 0)}%</b>
      <span>Drain capacity / blockage</span><b>${num(z.drain_capacity_mm_hr, 0)} mm/h / ${num(z.blockage_pct, 0)}%</b>
      <span>Temperature / humidity</span><b>${num(z.temperature)}\u00B0C / ${num(z.humidity, 0)}%</b>
    </div>
    <span class="muted">Risk trend, last 48 hours</span>`;
  try { drawChart(await api(`/zones/${id}/history?hours=48`)); } catch (e) { $('chart').hidden = true; }
}

function drawChart(rows) {
  const svg = $('chart');
  if (rows.length < 2) { svg.hidden = true; return; }
  svg.hidden = false;
  const W = 320, H = 110, p = 8;
  const t0 = new Date(rows[0].created_at), t1 = new Date(rows[rows.length - 1].created_at);
  const x = r => p + (new Date(r.created_at) - t0) / Math.max(1, t1 - t0) * (W - 2 * p);
  const y = r => H - p - r.risk_score / 100 * (H - 2 * p);
  let bands = '';
  [[0, 25, 'Low'], [25, 50, 'Moderate'], [50, 75, 'High'], [75, 100, 'Severe']].forEach(([a, b, l]) => {
    bands += `<rect x="${p}" y="${H - p - b / 100 * (H - 2 * p)}" width="${W - 2 * p}" height="${(b - a) / 100 * (H - 2 * p)}" fill="${COLORS[l]}" opacity=".12"/>`;
  });
  svg.innerHTML = bands +
    `<polyline points="${rows.map(r => `${x(r).toFixed(1)},${y(r).toFixed(1)}`).join(' ')}" fill="none" stroke="#12303f" stroke-width="2"/>` +
    rows.map(r => `<circle cx="${x(r).toFixed(1)}" cy="${y(r).toFixed(1)}" r="2.5" fill="${COLORS[r.risk_level]}"/>`).join('');
}

/* ---------- alerts (banner + browser notifications) ---------- */
let lastAlertId = +(localStorage.getItem('lastAlertId') || 0);
async function loadAlerts() {
  const list = await api('/alerts');
  $('alerts').innerHTML = list.length ? list.map(a => `
    <li class="${a.level}"><b>${esc(a.zone)}</b>, ${a.level}<br>${esc(a.message)}
    <time>${new Date(a.created_at).toLocaleString()}</time></li>`).join('')
    : '<li class="muted">No alerts. All monitored zones are low risk.</li>';
  const fresh = list.filter(a => a.id > lastAlertId);
  if (fresh.length) {
    const top = fresh.find(a => a.level === 'Severe') || fresh.find(a => a.level === 'High') || fresh[0];
    $('banner').hidden = false; $('banner').className = 'banner ' + top.level; $('banner').textContent = top.message;
    if (lastAlertId && 'Notification' in window && Notification.permission === 'granted')
      fresh.slice(0, 3).forEach(a => new Notification(`${a.level} flood risk: ${a.zone}`, {body: a.message}));
    lastAlertId = Math.max(...list.map(a => a.id));
    localStorage.setItem('lastAlertId', lastAlertId);
  }
}
$('btnNotify').onclick = async () => {
  if (!('Notification' in window)) return alert('This browser does not support notifications.');
  $('btnNotify').textContent = (await Notification.requestPermission()) === 'granted' ? 'Alerts on' : 'Alerts blocked';
};

/* ---------- check my location ---------- */
const getPosition = () => new Promise((res, rej) => navigator.geolocation
  ? navigator.geolocation.getCurrentPosition(p => res(p.coords), () => rej(new Error('Location permission was denied. Allow location access in your browser.')))
  : rej(new Error('Location is not supported in this browser')));

$('btnLocate').onclick = async () => {
  const box = $('locResult'); box.hidden = false; box.textContent = 'Finding your location\u2026';
  try {
    const c = await getPosition();
    const z = await api(`/check?lat=${c.latitude}&lng=${c.longitude}`);
    map.setView(c.latitude, c.longitude, 14);
    box.innerHTML = `Nearest monitored zone is <b>${esc(z.name)}</b>, ${z.distance_km} km away: ` +
      `<span class="pill ${z.risk_level}">${z.risk_level}</span> risk, possible water depth ${num(z.ponding_cm, 0)} cm, ` +
      `${num(z.forecast_3h)} mm rain expected in the next 3 hours.`;
    selectZone(z.id);
  } catch (e) { box.textContent = e.message; }
};

/* ---------- public flood reports ---------- */
function setPick(lat, lng) {
  pick = {lat, lng};
  $('repLoc').value = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  map.setMarkers('pick', [{lat, lng, size: 20, color: '#2f7fa8', cls: 'pin', title: 'Your report location'}]);
}
map.onClick = setPick;
$('btnRepGeo').onclick = async () => {
  try { const c = await getPosition(); setPick(c.latitude, c.longitude); map.setView(c.latitude, c.longitude, 15); }
  catch (e) { $('repMsg').textContent = e.message; }
};
$('btnRepSend').onclick = async () => {
  if (!pick) { $('repMsg').textContent = 'Click the map to choose a location first.'; return; }
  try {
    await post('/reports', {...pick, water_level_cm: +$('repLevel').value, description: $('repDesc').value});
    $('repMsg').textContent = 'Report sent. Risk scores update at the next refresh.';
    $('repDesc').value = '';
    loadReports();
  } catch (e) { $('repMsg').textContent = e.message; }
};
async function loadReports() {
  const rows = await api('/reports');
  map.setMarkers('reports', rows.map(r => ({
    lat: r.lat, lng: r.lng, size: 12, color: '#7fc4e8',
    title: `Public report: ${r.water_level_cm} cm. ${r.description || ''}`
  })));
}

/* ---------- summary report, refresh, simulator ---------- */
$('btnReport').onclick = async () => {
  const r = await api('/report');
  $('reportText').hidden = false; $('reportText').textContent = r.text;
};
async function runBusy(btn, label, fn) {
  const old = btn.textContent; btn.disabled = true; btn.textContent = label;
  try {
    const r = await fn();
    await load();
    if (r && r.failed && r.failed.length)
      $('updated').textContent = r.updated ? `${r.updated} zones updated, ${r.failed.length} failed`
        : 'Could not reach the weather service. Check your internet or use the storm simulator.';
  } catch (e) { alert(e.message); }
  btn.disabled = false; btn.textContent = old;
}
$('btnRefresh').onclick = () => runBusy($('btnRefresh'), 'Refreshing\u2026', () => post('/refresh'));
$('btnSim').onclick = () => runBusy($('btnSim'), 'Simulating\u2026', () => post('/simulate', {mm_per_hour: +$('simLevel').value}));

async function load() {
  try {
    zones = await api('/zones');
    renderZones();
    if (selectedId) selectZone(selectedId);
    await Promise.all([loadAlerts(), loadReports()]);
  } catch (e) { $('updated').textContent = 'Cannot reach the server'; }
}
load();
setInterval(load, 60000);
