/* =====================================================================
   秋刀魚漁場速預報系統 - 前端邏輯 (Leaflet)
   農業部水產試驗所 漁海況研究小組
   ===================================================================== */
'use strict';

const V = window.VIEW || { lat_min: 17, lat_max: 56, lon_min: 114, lon_max: 162 };

// ── 地圖初始化 ───────────────────────────────────────────
const map = L.map('map', {
  center: [(V.lat_min + V.lat_max) / 2, (V.lon_min + V.lon_max) / 2],
  zoom: 4, minZoom: 3, maxZoom: 9, worldCopyJump: false,
  zoomControl: true, preferCanvas: true
});

// 海洋底圖（Esri Ocean Basemap）
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}', {
  attribution: 'Esri Ocean | JMA GOOS', maxZoom: 13
}).addTo(map);
// 地名參考層
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Reference/MapServer/tile/{z}/{y}/{x}', {
  maxZoom: 13, opacity: 0.9
}).addTo(map);

map.fitBounds([[V.lat_min, V.lon_min], [V.lat_max, V.lon_max]]);

// ── 圖層狀態 ─────────────────────────────────────────────
const layers = {};          // layerName -> L.imageOverlay / L.geoJSON / L.layerGroup
const legends = {};         // layerName -> legend spec
let overlayOpacity = 0.82;
const IMAGE_LAYERS = ['sst', 'subtemp', 'currents', 'habitat'];

function currentDate() { return document.getElementById('date-select').value; }
function setStatus(txt, cls) {
  const el = document.getElementById('status-text');
  el.textContent = txt; el.className = cls || 'status-idle';
}

// ── 疊圖載入 ─────────────────────────────────────────────
async function loadImageLayer(name) {
  const date = currentDate();
  let url = `/api/overlay/${name}?date=${date}&alpha=${Math.round(overlayOpacity * 255)}`;
  if (name === 'subtemp') url += `&depth=${document.getElementById('sub-depth').value}`;
  if (name === 'currents') url += `&arrow_size=${document.getElementById('cur-size').value}&skip=${document.getElementById('cur-skip').value}`;
  setStatus(`載入 ${layerLabel(name)}…`, 'status-busy');
  try {
    const r = await fetch(url);
    const d = await r.json();
    if (d.error) { setStatus(d.error, 'status-idle'); return; }
    if (layers[name]) { map.removeLayer(layers[name]); }
    const ov = L.imageOverlay(d.image, d.bounds, { opacity: overlayOpacity, interactive: false });
    ov.addTo(map);
    layers[name] = ov;
    legends[name] = d.legend;
    renderLegend();
    setStatus(`${layerLabel(name)} 已載入`, 'status-ok');
  } catch (e) { setStatus('載入失敗：' + e, 'status-idle'); }
}

async function loadFronts() {
  const date = currentDate();
  const th = document.getElementById('front-th').value;
  setStatus('偵測溫度鋒面…', 'status-busy');
  try {
    const r = await fetch(`/api/fronts?date=${date}&threshold=${th}`);
    const d = await r.json();
    if (d.error) { setStatus(d.error, 'status-idle'); return; }
    if (layers.fronts) map.removeLayer(layers.fronts);
    layers.fronts = L.geoJSON(d.geojson, {
      style: { color: '#ff2d2d', weight: 2, opacity: 0.9 }
    }).addTo(map);
    legends.fronts = { type: 'line', label: '溫度鋒面', color: '#ff2d2d',
      note: `門檻 ${d.stats.threshold} °C/km · 共 ${d.stats.front_count} 段` };
    renderLegend();
    setStatus(`偵測到 ${d.stats.front_count} 段鋒面`, 'status-ok');
  } catch (e) { setStatus('鋒面偵測失敗：' + e, 'status-idle'); }
}

async function loadHotspots() {
  const date = currentDate();
  setStatus('萃取漁場熱區…', 'status-busy');
  try {
    const r = await fetch(`/api/hotspots?date=${date}&prob=0.6`);
    const d = await r.json();
    if (d.error) { setStatus(d.error, 'status-idle'); return; }
    drawHotspots(d.hotspots);
    renderHotspotList(d.hotspots);
    setStatus(`標示 ${d.count} 個推薦漁場`, 'status-ok');
  } catch (e) { setStatus('熱區萃取失敗：' + e, 'status-idle'); }
}

function drawHotspots(spots) {
  if (layers.hotspots) map.removeLayer(layers.hotspots);
  const grp = L.layerGroup();
  spots.forEach(s => {
    const icon = L.divIcon({ className: '', html: `<div class="hotspot-marker">${s.rank}</div>`,
      iconSize: [30, 30], iconAnchor: [15, 15] });
    const m = L.marker(s.center, { icon });
    m.bindPopup(hotspotPopup(s));
    grp.addLayer(m);
  });
  grp.addTo(map);
  layers.hotspots = grp;
}

function hotspotPopup(s) {
  return `<div class="hs-popup-title">推薦漁場 #${s.rank}</div>
    座標：${s.center[0].toFixed(2)}°N, ${s.center[1].toFixed(2)}°E<br>
    平均機率：${(s.mean_prob * 100).toFixed(0)}%（最高 ${(s.max_prob * 100).toFixed(0)}%）<br>
    面積：約 ${Number(s.area_km2).toLocaleString()} km²<br>
    ${s.mean_sst != null ? '平均 SST：' + s.mean_sst + ' °C' : ''}`;
}

function renderHotspotList(spots) {
  const panel = document.getElementById('hotspot-panel');
  const list = document.getElementById('hotspot-list');
  if (!spots.length) { panel.style.display = 'none'; return; }
  panel.style.display = 'block';
  list.innerHTML = spots.map(s => `
    <div class="hotspot-item" onclick="flyTo(${s.center[0]}, ${s.center[1]})">
      <div class="hs-rank">${s.rank}</div>
      <div class="hs-body">
        <div class="hs-coord">${s.center[0].toFixed(2)}°N, ${s.center[1].toFixed(2)}°E</div>
        <div class="hs-meta">機率 ${(s.mean_prob*100).toFixed(0)}% · ${Number(s.area_km2).toLocaleString()} km²${s.mean_sst!=null?' · '+s.mean_sst+'°C':''}</div>
      </div>
    </div>`).join('');
}
window.flyTo = (lat, lon) => map.flyTo([lat, lon], 6, { duration: 0.8 });

// ── 圖層開關 ─────────────────────────────────────────────
window.toggleLayer = function (name, on) {
  if (name === 'sst') document.getElementById('opt-sst').classList.toggle('show', on);
  if (name === 'currents') document.getElementById('opt-currents').classList.toggle('show', on);
  if (name === 'subtemp') document.getElementById('opt-subtemp').classList.toggle('show', on);
  if (name === 'fronts') document.getElementById('opt-fronts').classList.toggle('show', on);
  if ((name === 'sst' || name === 'subtemp') && !on && isoLayers[name]) {
    map.removeLayer(isoLayers[name]); delete isoLayers[name];
    const chk = document.getElementById(name === 'sst' ? 'sst-iso' : 'subtemp-iso');
    if (chk) chk.checked = false;
  }

  if (on) {
    if (name === 'fronts') loadFronts();
    else if (name === 'hotspots') loadHotspots();
    else loadImageLayer(name);
  } else {
    if (layers[name]) { map.removeLayer(layers[name]); delete layers[name]; }
    delete legends[name];
    if (name === 'hotspots') document.getElementById('hotspot-panel').style.display = 'none';
    renderLegend();
  }
};

window.reloadLayer = function (name) {
  const chk = document.querySelector(`.layer-chk[data-layer="${name}"]`);
  if (chk && chk.checked) { name === 'fronts' ? loadFronts() : loadImageLayer(name); }
};

window.onDateChange = function () {
  IMAGE_LAYERS.forEach(n => { if (layers[n]) loadImageLayer(n); });
  if (layers.fronts) loadFronts();
  if (layers.hotspots) loadHotspots();
  ['sst', 'subtemp'].forEach(reloadIso);
};

window.setOpacity = function (v) {
  overlayOpacity = parseFloat(v);
  IMAGE_LAYERS.forEach(n => { if (layers[n]) layers[n].setOpacity(overlayOpacity); });
};


// ── 等溫線 ───────────────────────────────────────────────
const isoLayers = {};   // layer -> L.layerGroup（線 + 標註）
async function loadIsotherms(layer) {
  const date = currentDate();
  const interval = document.getElementById(layer === 'sst' ? 'sst-iso-int' : 'subtemp-iso-int').value;
  let url = `/api/isotherms?layer=${layer}&date=${date}&interval=${interval}`;
  if (layer === 'subtemp') url += `&depth=${document.getElementById('sub-depth').value}`;
  setStatus(`繪製${layerLabel(layer)}等溫線…`, 'status-busy');
  try {
    const r = await fetch(url);
    const d = await r.json();
    if (d.error) { setStatus(d.error, 'status-idle'); return; }
    if (isoLayers[layer]) map.removeLayer(isoLayers[layer]);
    const grp = L.layerGroup();
    L.geoJSON(d.geojson, { style: { color: '#111', weight: 0.9, opacity: 0.85 },
      interactive: false }).addTo(grp);
    (d.labels || []).forEach(lb => {
      const icon = L.divIcon({ className: '', html: `<span class="iso-label">${lb.temp}°</span>`,
        iconSize: null });
      L.marker([lb.lat, lb.lon], { icon, interactive: false, keyboard: false }).addTo(grp);
    });
    grp.addTo(map);
    isoLayers[layer] = grp;
    setStatus(`${layerLabel(layer)}等溫線（間距 ${interval}°C）已繪製`, 'status-ok');
  } catch (e) { setStatus('等溫線繪製失敗：' + e, 'status-idle'); }
}
window.toggleIso = function (layer, on) {
  if (on) loadIsotherms(layer);
  else if (isoLayers[layer]) { map.removeLayer(isoLayers[layer]); delete isoLayers[layer]; }
};
window.reloadIso = function (layer) {
  const chk = document.getElementById(layer === 'sst' ? 'sst-iso' : 'subtemp-iso');
  if (chk && chk.checked) loadIsotherms(layer);
};
window.onSubDepthChange = function () {
  reloadLayer('subtemp');
  reloadIso('subtemp');
};

// ── 一鍵速預報 ───────────────────────────────────────────
let lastForecast = null;
window.runForecast = async function () {
  showMask('速預報分析中，請稍候…');
  try {
    const r = await fetch(`/api/forecast?date=${currentDate()}`);
    const d = await r.json();
    if (d.error) { hideMask(); setStatus(d.error, 'status-idle'); return; }
    lastForecast = d;

    // SST 底圖
    if (d.sst_overlay) {
      setChk('sst', true);
      if (layers.sst) map.removeLayer(layers.sst);
      layers.sst = L.imageOverlay(d.sst_overlay.image, d.sst_overlay.bounds, { opacity: overlayOpacity }).addTo(map);
      legends.sst = d.sst_overlay.legend;
    }
    // 棲息機率
    if (d.habitat) {
      setChk('habitat', true);
      if (layers.habitat) map.removeLayer(layers.habitat);
      layers.habitat = L.imageOverlay(d.habitat.image, d.habitat.bounds, { opacity: overlayOpacity }).addTo(map);
      legends.habitat = d.habitat.legend;
    }
    // 鋒面
    if (d.fronts) {
      setChk('fronts', true);
      document.getElementById('opt-fronts').classList.add('show');
      if (layers.fronts) map.removeLayer(layers.fronts);
      layers.fronts = L.geoJSON(d.fronts, { style: { color: '#ff2d2d', weight: 2, opacity: 0.9 } }).addTo(map);
      legends.fronts = { type: 'line', label: '溫度鋒面', color: '#ff2d2d',
        note: `共 ${d.front_stats.front_count} 段` };
    }
    // 熱區
    setChk('hotspots', true);
    drawHotspots(d.hotspots || []);
    renderHotspotList(d.hotspots || []);
    renderLegend();

    const n = (d.hotspots || []).length;
    const area = Number(d.high_prob_area_km2 || 0).toLocaleString();
    setStatus(`✓ ${d.date} 速預報完成：${n} 個推薦漁場 · 高機率海域 ${area} km²`, 'status-ok');
  } catch (e) { setStatus('速預報失敗：' + e, 'status-idle'); }
  hideMask();
};

function setChk(name, on) {
  const c = document.querySelector(`.layer-chk[data-layer="${name}"]`);
  if (c) c.checked = on;
}

// ── 報告下載 ─────────────────────────────────────────────
window.downloadReport = function () {
  if (!lastForecast) { alert('請先執行一鍵速預報'); return; }
  const d = lastForecast;
  const rows = (d.hotspots || []).map(s =>
    `<tr><td>${s.rank}</td><td>${s.center[0].toFixed(2)}°N, ${s.center[1].toFixed(2)}°E</td>
     <td>${(s.mean_prob*100).toFixed(0)}%</td><td>${Number(s.area_km2).toLocaleString()}</td>
     <td>${s.mean_sst!=null?s.mean_sst:'—'}</td></tr>`).join('');
  const e = d.ecdf || {};
  const html = `<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8">
<title>秋刀魚漁場速預報報告 ${d.date}</title>
<style>body{font-family:'Noto Sans TC',sans-serif;max-width:820px;margin:30px auto;color:#22303f;padding:0 20px}
h1{color:#0d2a4a;border-bottom:3px solid #e07a1f;padding-bottom:8px}
h2{color:#14395f;margin-top:24px}table{width:100%;border-collapse:collapse;margin:12px 0}
th,td{border:1px solid #d9e2ec;padding:8px 10px;text-align:center;font-size:14px}
th{background:#14395f;color:#fff}tr:nth-child(even){background:#f5f9fc}
.meta{color:#5b6b7c;font-size:13px}.kpi{display:flex;gap:16px;margin:16px 0}
.card{flex:1;background:#f0f4f8;border-radius:10px;padding:14px;text-align:center}
.card b{display:block;font-size:24px;color:#e07a1f}.foot{margin-top:30px;color:#5b6b7c;font-size:12px;border-top:1px solid #d9e2ec;padding-top:10px}</style></head><body>
<h1>🎯 秋刀魚漁場速預報報告</h1>
<p class="meta">資料日期：${d.date} ｜ 產製時間：${d.generated_at} ｜ 農業部水產試驗所 漁海況研究小組</p>
<div class="kpi">
<div class="card"><b>${(d.hotspots||[]).length}</b>推薦漁場熱區</div>
<div class="card"><b>${Number(d.high_prob_area_km2||0).toLocaleString()}</b>高機率海域 (km²)</div>
<div class="card"><b>${d.front_stats?d.front_stats.front_count:0}</b>溫度鋒面段數</div></div>
<h2>ECDF 最適環境參數</h2>
<table><tr><th>參數</th><th>最適範圍</th><th>平均</th><th>觀測範圍</th></tr>
<tr><td>海面水溫 SST</td><td>${e.SST_optimal||'—'}</td><td>${e.SST_mean||'—'}</td><td>${e.SST_range||'—'}</td></tr>
<tr><td>100m 水溫</td><td>${e['100mT_optimal']||'—'}</td><td>${e['100mT_mean']||'—'}</td><td>${e['100mT_range']||'—'}</td></tr></table>
<h2>推薦漁場熱區（依機率×面積排序）</h2>
<table><tr><th>排名</th><th>中心座標</th><th>平均機率</th><th>面積 (km²)</th><th>平均SST (°C)</th></tr>${rows||'<tr><td colspan=5>無</td></tr>'}</table>
<p class="foot">資料來源：日本氣象廳 JMA GOOS（HIMSST／NPRSUBT／NPRSUBC）。棲息機率依歷史秋刀魚 CPUE 之 SST 與 100m 水溫 ECDF 分析推估，僅供漁場參考。</p>
</body></html>`;
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `秋刀魚速預報_${d.date}.html`;
  a.click();
};

// ── 圖例 ─────────────────────────────────────────────────
function renderLegend() {
  const box = document.getElementById('legend-box');
  const order = ['sst', 'subtemp', 'currents', 'habitat', 'fronts'];
  let html = '';
  order.forEach(k => {
    const lg = legends[k]; if (!lg) return;
    html += '<div class="legend-block">';
    html += `<div class="legend-title">${lg.label}${lg.unit ? ' (' + lg.unit + ')' : ''}</div>`;
    if (lg.type === 'gradient') {
      const grad = lg.stops.map(s => `${s.color} ${(s.pos*100).toFixed(0)}%`).join(',');
      html += `<div class="legend-bar" style="background:linear-gradient(90deg,${grad})"></div>`;
      html += `<div class="legend-scale"><span>${lg.vmin}</span><span>${lg.vmax}</span></div>`;
    } else if (lg.type === 'discrete') {
      lg.items.forEach(it => html += `<div class="legend-item"><span class="legend-sw" style="background:${it.color}"></span>${it.text}</div>`);
    } else if (lg.type === 'line') {
      html += `<div class="legend-item"><span class="legend-sw" style="background:${lg.color};height:3px"></span>${lg.note||''}</div>`;
    } else if (lg.type === 'vector') {
      html += `<div class="legend-item">${lg.note||''}</div>`;
    }
    html += '</div>';
  });
  box.innerHTML = html;
  box.classList.toggle('show', html !== '');
}

// ── 滑鼠即時取值 ─────────────────────────────────────────
let valTimer = null;
map.on('mousemove', e => {
  clearTimeout(valTimer);
  valTimer = setTimeout(() => probeValue(e.latlng), 120);
});
async function probeValue(ll) {
  if (ll.lat < V.lat_min || ll.lat > V.lat_max || ll.lng < V.lon_min || ll.lng > V.lon_max) {
    document.getElementById('live-value').textContent = ''; return;
  }
  const depth = document.getElementById('sub-depth').value;
  try {
    const r = await fetch(`/api/value?date=${currentDate()}&lat=${ll.lat.toFixed(3)}&lon=${ll.lng.toFixed(3)}&depth=${depth}`);
    const d = await r.json();
    let parts = [`${ll.lat.toFixed(2)}°N ${ll.lng.toFixed(2)}°E`];
    if (d.sst != null) parts.push(`SST ${d.sst}°C`);
    if (d.subtemp != null) parts.push(`${d.depth} ${d.subtemp}°C`);
    if (d.current != null) parts.push(`流速 ${d.current}m/s`);
    document.getElementById('live-value').textContent = parts.join(' ｜ ');
  } catch (e) {}
}

// ── 資料更新 ─────────────────────────────────────────────
window.updateData = async function () {
  const btn = document.getElementById('btn-update');
  btn.disabled = true;
  showMask('連線 JMA 下載最新資料…');
  try {
    const r = await fetch('/api/update-data', { method: 'POST' });
    if (r.status === 409) { setStatus('更新已在進行中', 'status-busy'); }
    pollUpdate();
  } catch (e) { hideMask(); btn.disabled = false; setStatus('更新啟動失敗：' + e, 'status-idle'); }
};
function pollUpdate() {
  const btn = document.getElementById('btn-update');
  const timer = setInterval(async () => {
    try {
      const r = await fetch('/api/update-status');
      const s = await r.json();
      document.getElementById('mask-text').textContent =
        `${s.message}（${s.progress}/${s.total}）`;
      if (s.done) {
        clearInterval(timer); hideMask(); btn.disabled = false;
        if (s.error) { setStatus('更新失敗：' + s.error, 'status-idle'); }
        else { setStatus('資料更新完成，重新載入日期清單…', 'status-ok'); refreshDates(); }
      }
    } catch (e) { clearInterval(timer); hideMask(); btn.disabled = false; }
  }, 1200);
}
async function refreshDates() {
  const r = await fetch('/api/dates');
  const d = await r.json();
  const dates = (d.himsst || []).sort().reverse();
  const sel = document.getElementById('date-select');
  const cur = sel.value;
  sel.innerHTML = dates.map(x => `<option value="${x}">${x}</option>`).join('');
  if (dates.includes(cur)) sel.value = cur;
  onDateChange();
}

// ── 載入最新資料（重新讀取日期清單並跳到最新日期）────────
window.loadLatest = async function () {
  const btn = document.getElementById('btn-latest');
  if (btn) btn.disabled = true;
  setStatus('重新載入日期清單…', 'status-busy');
  try {
    const r = await fetch('/api/dates');
    const d = await r.json();
    const dates = (d.himsst || []).sort().reverse();
    const sel = document.getElementById('date-select');
    sel.innerHTML = dates.map(x => `<option value="${x}">${x}</option>`).join('');
    if (dates.length) {
      sel.value = dates[0];
      onDateChange();
      setStatus('已載入最新資料：' + dates[0], 'status-ok');
    } else setStatus('無可用資料', 'status-idle');
  } catch (e) { setStatus('載入失敗：' + e, 'status-idle'); }
  if (btn) btn.disabled = false;
};

// ── 工具 ─────────────────────────────────────────────────
function layerLabel(n) {
  return { sst: '海面水溫', subtemp: '次表層水溫', currents: '表面海流',
    habitat: '棲息機率', fronts: '溫度鋒面', hotspots: '漁場熱區' }[n] || n;
}
function showMask(t) { document.getElementById('mask-text').textContent = t; document.getElementById('overlay-mask').classList.remove('hidden'); }
function hideMask() { document.getElementById('overlay-mask').classList.add('hidden'); }

async function loadEcdf() {
  try {
    const r = await fetch('/api/ecdf-summary');
    const d = await r.json();
    const el = document.getElementById('ecdf-content');
    el.className = 'ecdf-grid';
    el.innerHTML = `
      <div class="ecdf-row"><span class="ecdf-k">SST 最適範圍</span><span class="ecdf-v">${d.SST_optimal||'—'}</span></div>
      <div class="ecdf-row"><span class="ecdf-k">SST 平均</span><span class="ecdf-v">${d.SST_mean||'—'}</span></div>
      <div class="ecdf-row"><span class="ecdf-k">100m 最適範圍</span><span class="ecdf-v">${d['100mT_optimal']||'—'}</span></div>
      <div class="ecdf-row"><span class="ecdf-k">100m 平均</span><span class="ecdf-v">${d['100mT_mean']||'—'}</span></div>
      <div class="ecdf-row"><span class="ecdf-k">歷史漁獲筆數</span><span class="ecdf-v">${d.catch_count||0} / ${d.data_count||0}</span></div>`;
  } catch (e) {}
}

function tick() {
  const now = new Date();
  document.getElementById('current-time').textContent =
    now.toLocaleString('zh-TW', { hour12: false });
}
setInterval(tick, 1000); tick();


// ── 啟動時偵測背景自動更新 ───────────────────────────────
async function checkAutoUpdate() {
  try {
    const r = await fetch('/api/update-status');
    const s = await r.json();
    if (s.running) {
      const btn = document.getElementById('btn-update');
      btn.disabled = true; btn.textContent = '⟳ 自動更新中…';
      setStatus('啟動自動更新：正在向 JMA 下載最新資料…', 'status-busy');
      const timer = setInterval(async () => {
        try {
          const rr = await fetch('/api/update-status'); const ss = await rr.json();
          if (ss.total) btn.textContent = `⟳ 更新中 ${ss.progress}/${ss.total}`;
          if (ss.done) {
            clearInterval(timer);
            btn.disabled = false; btn.textContent = '⟳ 更新 JMA 資料';
            if (ss.error) { setStatus('自動更新失敗：' + ss.error + '（仍可使用現有資料）', 'status-idle'); }
            else { setStatus('自動更新完成，已載入最新資料', 'status-ok'); refreshDates(); }
          }
        } catch (e) { clearInterval(timer); btn.disabled = false; btn.textContent = '⟳ 更新 JMA 資料'; }
      }, 1500);
    }
  } catch (e) {}
}

// ── 啟動 ─────────────────────────────────────────────────
loadEcdf();
loadImageLayer('sst');
checkAutoUpdate();
