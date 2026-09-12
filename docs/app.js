/* =====================================================================
   秋刀魚漁場速預報系統 — 純前端引擎 (GitHub Pages / 靜態版)
   農業部水產試驗所 漁海況研究小組
   ===================================================================== */
'use strict';

const DATA = './data/';
let VIEW = { latN: 56, latS: 17, lonW: 114, lonE: 162 };
let ECDF = null;
let curData = null;          // 當前日期解碼後的資料
const gridCache = {};        // date -> 原始 JSON
let overlayOpacity = 0.82;

// 漁場熱區判定門檻（相對棲地適合度 HSI，0-1）
const HOTSPOT_PROB_THR = 0.5;
const MAX_SUBSURFACE_LAG_DAYS = 3;

// ── Mercator ─────────────────────────────────────────────
const D2R = Math.PI / 180;
function lat2merc(lat) { lat = Math.max(-85.05, Math.min(85.05, lat)); return Math.log(Math.tan(Math.PI/4 + lat*D2R/2)); }
function merc2lat(y) { return (2*Math.atan(Math.exp(y)) - Math.PI/2) / D2R; }

// ── 地圖 ─────────────────────────────────────────────────
const map = L.map('map', { center: [36, 143], zoom: 4, minZoom: 3, maxZoom: 9, preferCanvas: true });
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}',
  { attribution: 'Esri Ocean | JMA GOOS', maxZoom: 13 }).addTo(map);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Reference/MapServer/tile/{z}/{y}/{x}',
  { maxZoom: 13, opacity: 0.9 }).addTo(map);

const layers = {}, legends = {}, isoLayers = {};
const IMAGE_LAYERS = ['sst', 'subtemp', 'currents', 'habitat'];

function currentDate() { return document.getElementById('date-select').value; }
function setStatus(t, c) { const e = document.getElementById('status-text'); e.textContent = t; e.className = c || 'status-idle'; }
function showMask(t) { document.getElementById('mask-text').textContent = t; document.getElementById('overlay-mask').classList.remove('hidden'); }
function hideMask() { document.getElementById('overlay-mask').classList.add('hidden'); }
function layerLabel(n){return {sst:'海面水溫',subtemp:'次表層水溫',currents:'表面海流',habitat:'棲地適合度 HSI',fronts:'溫度鋒面',hotspots:'漁場熱區'}[n]||n;}

// ── 解碼網格 ─────────────────────────────────────────────
function decodeGrid(g) {
  const raw = atob(g.b64);
  const buf = new ArrayBuffer(raw.length);
  const u8 = new Uint8Array(buf);
  for (let i = 0; i < raw.length; i++) u8[i] = raw.charCodeAt(i);
  const i16 = new Int16Array(buf);
  const n = g.nx * g.ny;
  const data = new Float32Array(n);
  for (let i = 0; i < n; i++) data[i] = (i16[i] === g.nodata) ? NaN : i16[i] / g.scale;
  return { data, nx: g.nx, ny: g.ny, latN: g.latN, latS: g.latS, lonW: g.lonW, lonE: g.lonE };
}

// 網格取值（雙線性，NaN 安全）
function sample(G, lat, lon) {
  if (lat > G.latN || lat < G.latS || lon < G.lonW || lon > G.lonE) return NaN;
  const fy = (G.latN - lat) / (G.latN - G.latS) * (G.ny - 1);
  const fx = (lon - G.lonW) / (G.lonE - G.lonW) * (G.nx - 1);
  const y0 = Math.floor(fy), x0 = Math.floor(fx);
  const y1 = Math.min(y0 + 1, G.ny - 1), x1 = Math.min(x0 + 1, G.nx - 1);
  const ty = fy - y0, tx = fx - x0;
  const v00 = G.data[y0*G.nx+x0], v01 = G.data[y0*G.nx+x1], v10 = G.data[y1*G.nx+x0], v11 = G.data[y1*G.nx+x1];
  const top = lerpNan(v00, v01, tx), bot = lerpNan(v10, v11, tx);
  return lerpNan(top, bot, ty);
}
function lerpNan(a, b, t) {
  const na = isNaN(a), nb = isNaN(b);
  if (na && nb) return NaN; if (na) return b; if (nb) return a;
  return a*(1-t)+b*t;
}
function nearest(G, lat, lon) {
  if (lat > G.latN || lat < G.latS || lon < G.lonW || lon > G.lonE) return NaN;
  const y = Math.round((G.latN - lat) / (G.latN - G.latS) * (G.ny - 1));
  const x = Math.round((lon - G.lonW) / (G.lonE - G.lonW) * (G.nx - 1));
  return G.data[y*G.nx+x];
}

// ── 色彩 ─────────────────────────────────────────────────
const SST_STOPS = ['#000080','#0000ff','#00bfff','#00ff80','#80ff00','#ffff00','#ff8000','#ff0000','#800000'];
const HAB_COLORS = ['#440154','#482878','#3e4989','#31688e','#26828e','#1f9e89','#35b779','#6dcd59','#b4de2c','#fde725'];
function hex2rgb(h){return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];}
const SST_RGB = SST_STOPS.map(hex2rgb);
function rampColor(t, rgbs){ // t 0..1
  if (t<=0) return rgbs[0]; if (t>=1) return rgbs[rgbs.length-1];
  const f = t*(rgbs.length-1), i = Math.floor(f), r = f-i;
  const a=rgbs[i], b=rgbs[i+1];
  return [a[0]+(b[0]-a[0])*r, a[1]+(b[1]-a[1])*r, a[2]+(b[2]-a[2])*r];
}
function habColor(p){ // 離散 0-1
  if (isNaN(p)) return null;
  const i = Math.min(HAB_COLORS.length - 1, Math.max(0, Math.floor(p * 10)));
  return hex2rgb(HAB_COLORS[i]);
}

// ── 輸出畫布尺寸（Mercator）──────────────────────────────
function outSize() {
  const OW = 820;
  const xspan = (VIEW.lonE - VIEW.lonW) * D2R;
  const yspan = lat2merc(VIEW.latN) - lat2merc(VIEW.latS);
  const OH = Math.round(OW * yspan / xspan);
  return { OW, OH };
}
function viewBounds() { return [[VIEW.latS, VIEW.lonW], [VIEW.latN, VIEW.lonE]]; }

// 掃描每個輸出像素 → 呼叫 fn(px,py,lat,lon)
function forEachPixel(OW, OH, fn) {
  const mTop = lat2merc(VIEW.latN), mBot = lat2merc(VIEW.latS);
  for (let py = 0; py < OH; py++) {
    const my = mTop + (py/(OH-1))*(mBot - mTop);
    const lat = merc2lat(my);
    for (let px = 0; px < OW; px++) {
      const lon = VIEW.lonW + (px/(OW-1))*(VIEW.lonE - VIEW.lonW);
      fn(px, py, lat, lon);
    }
  }
}

// ── 純量疊圖（SST / 次表層）──────────────────────────────
function renderScalar(G, vmin, vmax, label, unit, alpha) {
  const { OW, OH } = outSize();
  const cv = document.createElement('canvas'); cv.width = OW; cv.height = OH;
  const ctx = cv.getContext('2d'); const img = ctx.createImageData(OW, OH); const d = img.data;
  forEachPixel(OW, OH, (px, py, lat, lon) => {
    const v = sample(G, lat, lon); const o = (py*OW+px)*4;
    if (isNaN(v)) { d[o+3] = 0; return; }
    const c = rampColor((v-vmin)/(vmax-vmin), SST_RGB);
    d[o]=c[0]; d[o+1]=c[1]; d[o+2]=c[2]; d[o+3]=Math.round(alpha*255);
  });
  ctx.putImageData(img, 0, 0);
  return { url: cv.toDataURL(), legend: { type:'gradient', label, unit, vmin, vmax, stops: SST_STOPS } };
}

// ── 相對棲地適合度 HSI ──────────────────────────────────
function probScore(v, e) {
  if (isNaN(v)) return NaN;
  if (v >= e.p25 && v <= e.p75) return 1;
  if (v > e.p10 && v < e.p25) return (v-e.p10)/((e.p25-e.p10)||1);
  if (v > e.p75 && v < e.p90) return (e.p90-v)/((e.p90-e.p75)||1);
  return 0;
}
function dayLag(a,b){ return Math.abs((Date.parse(a+'T00:00:00Z')-Date.parse(b+'T00:00:00Z'))/86400000); }
function computeHabitat() {
  const S = curData.sst, T = curData.sub && curData.sub['100m'];
  if (!ECDF) return null;
  const useSub = Boolean(T && curData.subDate && dayLag(curData.date,curData.subDate)<=MAX_SUBSURFACE_LAG_DAYS);
  const nx = S.nx, ny = S.ny;
  const prob = new Float32Array(nx*ny);
  for (let y = 0; y < ny; y++) {
    const lat = S.latN + (y/(ny-1))*(S.latS - S.latN);
    for (let x = 0; x < nx; x++) {
      const lon = S.lonW + (x/(nx-1))*(S.lonE - S.lonW);
      const sv = S.data[y*nx+x];
      if (isNaN(sv)) { prob[y*nx+x] = NaN; continue; }
      const ps = probScore(sv, ECDF.sst);
      if (!useSub) { prob[y*nx+x] = ps; continue; }
      const tv = sample(T, lat, lon), pt = probScore(tv, ECDF.temp100);
      prob[y*nx+x] = (isNaN(ps)||isNaN(pt)) ? NaN : Math.sqrt(ps*pt);
    }
  }
  return { data: prob, nx, ny, latN: S.latN, latS: S.latS, lonW: S.lonW, lonE: S.lonE,
    modelLabel: useSub ? 'SST + 100mT' : 'SST（次表層資料超過 3 日或缺少）',
    variables: useSub ? ['SST','100mT'] : ['SST'] };
}
function renderHabitat(P, alpha) {
  const { OW, OH } = outSize();
  const cv = document.createElement('canvas'); cv.width = OW; cv.height = OH;
  const ctx = cv.getContext('2d'); const img = ctx.createImageData(OW, OH); const d = img.data;
  forEachPixel(OW, OH, (px, py, lat, lon) => {
    const v = sample(P, lat, lon); const o = (py*OW+px)*4;
    const c = habColor(v);
    if (!c) { d[o+3] = 0; return; }
    d[o]=c[0]; d[o+1]=c[1]; d[o+2]=c[2]; d[o+3]=Math.round(alpha*255);
  });
  ctx.putImageData(img, 0, 0);
  return { url: cv.toDataURL(), legend: { type:'discrete', label:'秋刀魚相對棲地適合度 HSI',
    items:HAB_COLORS.map((color,i)=>({color,text:`${(i/10).toFixed(1)}–${((i+1)/10).toFixed(1)}`})),
    note:'推薦漁場：HSI > 0.5' }};
}

// ── 表面海流（箭頭畫布）──────────────────────────────────
function renderCurrents(alpha) {
  const U = curData.cur.u, V = curData.cur.v;
  const skip = parseInt(document.getElementById('cur-skip').value);
  const size = parseFloat(document.getElementById('cur-size').value);
  const { OW, OH } = outSize();
  const cv = document.createElement('canvas'); cv.width = OW; cv.height = OH;
  const ctx = cv.getContext('2d'); ctx.globalAlpha = alpha; ctx.lineWidth = 1.1*size;
  const mTop = lat2merc(VIEW.latN), mBot = lat2merc(VIEW.latS);
  const toPx = (lat, lon) => [ (lon-VIEW.lonW)/(VIEW.lonE-VIEW.lonW)*(OW-1),
                               (lat2merc(lat)-mTop)/(mBot-mTop)*(OH-1) ];
  const L = 0.16 * size;   // 箭頭長度（度/(m/s)）粗略
  for (let y = 0; y < U.ny; y += skip) {
    const lat = U.latN + (y/(U.ny-1))*(U.latS - U.latN);
    for (let x = 0; x < U.nx; x += skip) {
      const lon = U.lonW + (x/(U.nx-1))*(U.lonE - U.lonW);
      const u = U.data[y*U.nx+x], v = V.data[y*V.nx+x];
      if (isNaN(u) || isNaN(v)) continue;
      const sp = Math.sqrt(u*u+v*v); if (sp < 0.02) continue;
      const [x0, y0] = toPx(lat, lon);
      const [x1, y1] = toPx(lat + v*L, lon + u*L/Math.cos(lat*D2R));
      const c = rampColor(Math.min(sp/1.5, 1), [[0,255,255],[80,120,255],[200,0,255]]);
      ctx.strokeStyle = `rgb(${c[0]|0},${c[1]|0},${c[2]|0})`;
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1);
      const ang = Math.atan2(y1-y0, x1-x0), hl = 4*size;
      ctx.lineTo(x1 - hl*Math.cos(ang-0.4), y1 - hl*Math.sin(ang-0.4));
      ctx.moveTo(x1, y1); ctx.lineTo(x1 - hl*Math.cos(ang+0.4), y1 - hl*Math.sin(ang+0.4));
      ctx.stroke();
    }
  }
  return { url: cv.toDataURL(), legend: { type:'vector', label:'表面海流', unit:'m/s', note:'箭頭為流向，色階代表流速' } };
}

// ── 等值線（d3-contour）：填補→等值→遮陸 ─────────────────
function fillNoData(G, passes) {
  const d = Float32Array.from(G.data), nx = G.nx, ny = G.ny;
  for (let p = 0; p < passes; p++) {
    let changed = false;
    const s = Float32Array.from(d);
    for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
      if (!isNaN(s[y*nx+x])) continue;
      let sum = 0, n = 0;
      for (let dy=-1; dy<=1; dy++) for (let dx=-1; dx<=1; dx++) {
        const yy=y+dy, xx=x+dx; if (yy<0||xx<0||yy>=ny||xx>=nx) continue;
        const val = s[yy*nx+xx]; if (!isNaN(val)) { sum+=val; n++; }
      }
      if (n>0) { d[y*nx+x] = sum/n; changed = true; }
    }
    if (!changed) break;
  }
  return d;
}
function gridToLatLon(G, gx, gy) {
  const lon = G.lonW + ((gx-0.5)/(G.nx-1))*(G.lonE - G.lonW);
  const lat = G.latN + ((gy-0.5)/(G.ny-1))*(G.latS - G.latN);
  return [lat, lon];
}
function contourLines(G, values, thresholds, opts) {
  opts = opts || {};
  const filled = fillNoData(G, 4);
  const src = values || filled;
  const c = d3.contours().size([G.nx, G.ny]).thresholds(thresholds)(src);
  const out = [];
  c.forEach(cont => {
    cont.coordinates.forEach(poly => poly.forEach(ring => {
      let seg = [];
      ring.forEach(pt => {
        const [lat, lon] = gridToLatLon(G, pt[0], pt[1]);
        const masked = opts.maskLand && isNaN(nearest(G, lat, lon));
        if (masked) { if (seg.length > 2) out.push({ t: cont.value, pts: seg }); seg = []; }
        else seg.push([lat, lon]);
      });
      if (seg.length > 2) out.push({ t: cont.value, pts: seg });
    }));
  });
  return out;
}

// ── 鋒面（SST 梯度）──────────────────────────────────────
function sstGradient(G) {
  const nx=G.nx, ny=G.ny, out=new Float32Array(nx*ny);
  const dlat = Math.abs((G.latN-G.latS)/(ny-1))*111;
  const meanlat = (G.latN+G.latS)/2;
  const dlon = Math.abs((G.lonE-G.lonW)/(nx-1))*111*Math.cos(meanlat*D2R);
  for (let y=0;y<ny;y++) for (let x=0;x<nx;x++){
    const c=G.data[y*nx+x];
    if (isNaN(c)) { out[y*nx+x]=0; continue; }
    const xm=G.data[y*nx+Math.max(x-1,0)], xp=G.data[y*nx+Math.min(x+1,nx-1)];
    const ym=G.data[Math.max(y-1,0)*nx+x], yp=G.data[Math.min(y+1,ny-1)*nx+x];
    if ([xm,xp,ym,yp].some(isNaN)) { out[y*nx+x]=0; continue; }
    const gx=(xp-xm)/(2*dlon), gy=(yp-ym)/(2*dlat);
    out[y*nx+x]=Math.sqrt(gx*gx+gy*gy);
  }
  return out;
}

// ── 熱區（連通區域）──────────────────────────────────────
function extractHotspots(P, thr) {
  const nx=P.nx, ny=P.ny, lab=new Int32Array(nx*ny).fill(0);
  const dlat=Math.abs((P.latN-P.latS)/(ny-1))*111;
  const meanlat=(P.latN+P.latS)/2;
  const dlon=Math.abs((P.lonE-P.lonW)/(nx-1))*111*Math.cos(meanlat*D2R);
  const cell=dlat*dlon;
  let cur=0; const spots=[];
  for (let i=0;i<nx*ny;i++){
    if (lab[i]||isNaN(P.data[i])||P.data[i]<=thr) continue;
    cur++; const stack=[i]; lab[i]=cur;
    let sw=0, slat=0, slon=0, area=0, pmax=0, ssum=0, scnt=0;
    while (stack.length){
      const j=stack.pop(); const y=(j/nx)|0, x=j%nx;
      const lat=P.latN+(y/(ny-1))*(P.latS-P.latN);
      const lon=P.lonW+(x/(nx-1))*(P.lonE-P.lonW);
      const pv=P.data[j]; sw+=pv; slat+=lat*pv; slon+=lon*pv; area+=cell; pmax=Math.max(pmax,pv);
      const sv=sample(curData.sst,lat,lon); if(!isNaN(sv)){ssum+=sv;scnt++;}
      [[1,0],[-1,0],[0,1],[0,-1]].forEach(([dx,dy])=>{
        const xx=x+dx, yy=y+dy; if(xx<0||yy<0||xx>=nx||yy>=ny) return;
        const k=yy*nx+xx; if(!lab[k]&&!isNaN(P.data[k])&&P.data[k]>thr){lab[k]=cur;stack.push(k);}
      });
    }
    if (area<1500) continue;
    spots.push({center:[slat/sw, slon/sw], area_km2:Math.round(area), mean_prob:sw/(area/cell),
      max_prob:pmax, mean_sst: scnt? +(ssum/scnt).toFixed(2):null});
  }
  spots.sort((a,b)=> b.mean_prob*Math.log10(b.area_km2+10) - a.mean_prob*Math.log10(a.area_km2+10));
  const top = spots.slice(0,12); top.forEach((s,i)=>{s.rank=i+1; s.mean_prob=+s.mean_prob.toFixed(3);});
  return top;
}

// ── 圖層載入 ─────────────────────────────────────────────
function addImage(name, r, alpha) {
  if (layers[name]) map.removeLayer(layers[name]);
  layers[name] = L.imageOverlay(r.url, viewBounds(), { opacity: alpha, interactive: false }).addTo(map);
  legends[name] = r.legend; renderLegend();
}
function loadImageLayer(name) {
  if (!curData) return;
  const a = overlayOpacity;
  setStatus(`繪製 ${layerLabel(name)}…`, 'status-busy');
  setTimeout(() => {
    try {
      if (name === 'sst') addImage('sst', renderScalar(curData.sst, 0, 32, '海面水溫 SST', '°C', a), a);
      else if (name === 'subtemp') {
        const dep = document.getElementById('sub-depth').value;
        addImage('subtemp', renderScalar(curData.sub[dep], 0, 25, dep+' 水溫', '°C', a), a);
      }
      else if (name === 'currents') addImage('currents', renderCurrents(a), a);
      else if (name === 'habitat') {
        const P = computeHabitat(); if (!P) { setStatus('缺少 ECDF 或 SST，無法計算 HSI','status-idle'); return; }
        curData._prob = P; addImage('habitat', renderHabitat(P, a), a);
      }
      setStatus(`${layerLabel(name)} 已繪製`, 'status-ok');
    } catch(e){ setStatus('繪製失敗：'+e, 'status-idle'); console.error(e); }
  }, 10);
}
function loadFronts() {
  const thr = parseFloat(document.getElementById('front-th').value);
  const G = curData.sst;
  const grad = sstGradient(G);
  const gG = { data: grad, nx:G.nx, ny:G.ny, latN:G.latN, latS:G.latS, lonW:G.lonW, lonE:G.lonE };
  const lines = contourLines(gG, grad, [thr], { maskLand:false });
  if (layers.fronts) map.removeLayer(layers.fronts);
  const grp = L.layerGroup();
  lines.forEach(l => L.polyline(l.pts, { color:'#ff2d2d', weight:2, opacity:0.9 }).addTo(grp));
  grp.addTo(map); layers.fronts = grp;
  legends.fronts = { type:'line', label:'溫度鋒面', color:'#ff2d2d', note:`門檻 ${thr} °C/km · ${lines.length} 段` };
  renderLegend(); setStatus(`偵測到 ${lines.length} 段鋒面`, 'status-ok');
}
function loadIsotherms(which) {
  const G = which==='sst' ? curData.sst : curData.sub[document.getElementById('sub-depth').value];
  const iv = parseFloat(document.getElementById(which==='sst'?'sst-iso-int':'subtemp-iso-int').value);
  const vmax = which==='sst'?32:25;
  const th = []; for (let t=0; t<=vmax; t+=iv) th.push(t);
  const lines = contourLines(G, null, th, { maskLand:true });
  if (isoLayers[which]) map.removeLayer(isoLayers[which]);
  const grp = L.layerGroup();
  const seen = {};
  lines.forEach(l => {
    L.polyline(l.pts, { color:'#111', weight:0.9, opacity:0.85, interactive:false }).addTo(grp);
    const key = l.t.toFixed(1);
    if (!seen[key] && l.pts.length > 6) {
      seen[key] = true;
      const mid = l.pts[Math.floor(l.pts.length/2)];
      L.marker(mid, { interactive:false, icon: L.divIcon({ className:'', html:`<span class="iso-label">${l.t}°</span>` }) }).addTo(grp);
    }
  });
  grp.addTo(map); isoLayers[which] = grp;
  setStatus(`${layerLabel(which)}等溫線（間距 ${iv}°C）已繪製`, 'status-ok');
}
function loadHotspots() {
  const P = curData._prob || computeHabitat();
  if (!P) { setStatus('缺次表層資料，無法萃取熱區','status-idle'); return; }
  curData._prob = P;
  const spots = extractHotspots(P, HOTSPOT_PROB_THR);
  drawHotspots(spots); renderHotspotList(spots);
  setStatus(`標示 ${spots.length} 個推薦漁場`, 'status-ok');
  return spots;
}
function drawHotspots(spots) {
  if (layers.hotspots) map.removeLayer(layers.hotspots);
  const grp = L.layerGroup();
  spots.forEach(s => {
    L.marker(s.center, { icon: L.divIcon({ className:'', html:`<div class="hotspot-marker">${s.rank}</div>`, iconSize:[30,30], iconAnchor:[15,15] }) })
      .bindPopup(`<div class="hs-popup-title">推薦漁場 #${s.rank}</div>座標：${s.center[0].toFixed(2)}°N, ${s.center[1].toFixed(2)}°E<br>平均 HSI：${s.mean_prob.toFixed(2)}（最高 ${s.max_prob.toFixed(2)}）<br>面積：約 ${s.area_km2.toLocaleString()} km²<br>${s.mean_sst!=null?'平均 SST：'+s.mean_sst+' °C':''}`)
      .addTo(grp);
  });
  grp.addTo(map); layers.hotspots = grp;
}
function renderHotspotList(spots) {
  const panel = document.getElementById('hotspot-panel'), list = document.getElementById('hotspot-list');
  if (!spots.length) { panel.style.display='none'; return; }
  panel.style.display='block';
  list.innerHTML = spots.map(s => `<div class="hotspot-item" onclick="flyTo(${s.center[0]},${s.center[1]})">
    <div class="hs-rank">${s.rank}</div><div class="hs-body">
    <div class="hs-coord">${s.center[0].toFixed(2)}°N, ${s.center[1].toFixed(2)}°E</div>
    <div class="hs-meta">HSI ${s.mean_prob.toFixed(2)} · ${s.area_km2.toLocaleString()} km²${s.mean_sst!=null?' · '+s.mean_sst+'°C':''}</div></div></div>`).join('');
}
window.flyTo = (lat, lon) => map.flyTo([lat, lon], 6, { duration: 0.8 });

// ── UI 事件 ──────────────────────────────────────────────
window.toggleLayer = function(name, on) {
  if (name==='sst') document.getElementById('opt-sst').classList.toggle('show', on);
  if (name==='subtemp') document.getElementById('opt-subtemp').classList.toggle('show', on);
  if (name==='currents') document.getElementById('opt-currents').classList.toggle('show', on);
  if (name==='fronts') document.getElementById('opt-fronts').classList.toggle('show', on);
  if ((name==='sst'||name==='subtemp') && !on && isoLayers[name]) {
    map.removeLayer(isoLayers[name]); delete isoLayers[name];
    const chk=document.getElementById(name==='sst'?'sst-iso':'subtemp-iso'); if(chk) chk.checked=false;
  }
  if (on) { name==='fronts'?loadFronts():name==='hotspots'?loadHotspots():loadImageLayer(name); }
  else {
    if (layers[name]) { map.removeLayer(layers[name]); delete layers[name]; }
    delete legends[name];
    if (name==='hotspots') document.getElementById('hotspot-panel').style.display='none';
    renderLegend();
  }
};
window.reloadLayer = function(name){ const c=document.querySelector(`.layer-chk[data-layer="${name}"]`); if(c&&c.checked){ name==='fronts'?loadFronts():loadImageLayer(name);} };
window.toggleIso = function(w, on){ if(on) loadIsotherms(w); else if(isoLayers[w]){map.removeLayer(isoLayers[w]); delete isoLayers[w];} };
window.reloadIso = function(w){ const c=document.getElementById(w==='sst'?'sst-iso':'subtemp-iso'); if(c&&c.checked) loadIsotherms(w); };
window.onSubDepthChange = function(){ reloadLayer('subtemp'); reloadIso('subtemp'); };
window.setOpacity = function(v){ overlayOpacity=parseFloat(v); IMAGE_LAYERS.forEach(n=>{ if(layers[n]) layers[n].setOpacity(overlayOpacity); }); };

window.onDateChange = async function() {
  await loadDate(currentDate());
  IMAGE_LAYERS.forEach(n=>{ if(layers[n]) loadImageLayer(n); });
  if (layers.fronts) loadFronts();
  if (layers.hotspots) loadHotspots();
  ['sst','subtemp'].forEach(w=>{ if(isoLayers[w]) loadIsotherms(w); });
};

// ── 載入最新資料（重新讀取 manifest 並跳到最新日期）──────
window.loadLatest = async function () {
  const btn = document.getElementById('btn-latest');
  if (btn) btn.disabled = true;
  setStatus('重新載入資料清單…', 'status-busy');
  try {
    const man = await (await fetch(DATA + 'manifest.json?t=' + Date.now())).json();
    const sel = document.getElementById('date-select');
    sel.innerHTML = man.dates.map(d => `<option value="${d}">${d}</option>`).join('');
    if (man.dates.length) {
      sel.value = man.dates[0];
      delete gridCache[man.dates[0]];   // 確保重新抓取最新檔
      await onDateChange();
      setStatus('已載入最新資料：' + man.dates[0], 'status-ok');
    } else setStatus('無可用資料', 'status-idle');
  } catch (e) { setStatus('載入失敗：' + e, 'status-idle'); }
  if (btn) btn.disabled = false;
};

// ── 一鍵速預報 ───────────────────────────────────────────
let lastForecast = null;
window.runForecast = async function() {
  showMask('速預報分析中，請稍候…');
  await new Promise(r=>setTimeout(r,30));
  try {
    setChk('sst',true);
    addImage('sst', renderScalar(curData.sst, 0, 32, '海面水溫 SST', '°C', overlayOpacity), overlayOpacity);
    const P = computeHabitat();
    let spots = [];
    if (P) { curData._prob=P; setChk('habitat',true); addImage('habitat', renderHabitat(P, overlayOpacity), overlayOpacity);
             spots = extractHotspots(P,HOTSPOT_PROB_THR); setChk('hotspots',true); drawHotspots(spots); renderHotspotList(spots); }
    setChk('fronts',true); document.getElementById('opt-fronts').classList.add('show'); loadFronts();
    let area = 0;
    if (P){ const dlat=Math.abs((P.latN-P.latS)/(P.ny-1))*111, dlon=Math.abs((P.lonE-P.lonW)/(P.nx-1))*111*Math.cos((P.latN+P.latS)/2*D2R), cell=dlat*dlon;
      for (let i=0;i<P.data.length;i++) if(!isNaN(P.data[i])&&P.data[i]>HOTSPOT_PROB_THR) area+=cell; }
    lastForecast = { date: currentDate(), spots, area: Math.round(area), ecdf: ECDF.summary,
      modelLabel: P ? P.modelLabel : '無法計算' };
    setStatus(`✓ ${currentDate()} 速預報完成：${spots.length} 個推薦漁場 · HSI > ${HOTSPOT_PROB_THR} 海域 ${Math.round(area).toLocaleString()} km²`, 'status-ok');
  } catch(e){ setStatus('速預報失敗：'+e,'status-idle'); console.error(e); }
  hideMask();
};
function setChk(n,on){ const c=document.querySelector(`.layer-chk[data-layer="${n}"]`); if(c) c.checked=on; }

// ── 報告下載 ─────────────────────────────────────────────
window.downloadReport = function() {
  if (!lastForecast) { alert('請先執行一鍵速預報'); return; }
  const d = lastForecast, e = d.ecdf||{};
  const rows = d.spots.map(s=>`<tr><td>${s.rank}</td><td>${s.center[0].toFixed(2)}°N, ${s.center[1].toFixed(2)}°E</td><td>${s.mean_prob.toFixed(2)}</td><td>${s.area_km2.toLocaleString()}</td><td>${s.mean_sst!=null?s.mean_sst:'—'}</td></tr>`).join('');
  const paramRows = Object.values(e.parameters||{}).map(p=>`<tr><td>${p.label}</td><td>${p.core[0]}–${p.core[1]} ${p.unit}</td><td>${p.probable[0]}–${p.probable[1]} ${p.unit}</td><td>${p.d_max_value} ${p.unit}</td></tr>`).join('');
  const html = `<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8"><title>秋刀魚漁場速預報報告 ${d.date}</title>
<style>body{font-family:'Noto Sans TC',sans-serif;max-width:820px;margin:30px auto;color:#22303f;padding:0 20px}h1{color:#0d2a4a;border-bottom:3px solid #e07a1f;padding-bottom:8px}h2{color:#14395f;margin-top:24px}table{width:100%;border-collapse:collapse;margin:12px 0}th,td{border:1px solid #d9e2ec;padding:8px 10px;text-align:center;font-size:14px}th{background:#14395f;color:#fff}tr:nth-child(even){background:#f5f9fc}.kpi{display:flex;gap:16px;margin:16px 0}.card{flex:1;background:#f0f4f8;border-radius:10px;padding:14px;text-align:center}.card b{display:block;font-size:24px;color:#e07a1f}.foot{margin-top:30px;color:#5b6b7c;font-size:12px;border-top:1px solid #d9e2ec;padding-top:10px}</style></head><body>
<h1>🎯 秋刀魚漁場速預報報告</h1><p>資料日期：${d.date}｜農業部水產試驗所 漁海況研究小組</p>
<div class="kpi"><div class="card"><b>${d.spots.length}</b>推薦漁場熱區</div><div class="card"><b>${d.area.toLocaleString()}</b>HSI > ${HOTSPOT_PROB_THR} 海域 (km²)</div></div><p>作業模型：${d.modelLabel}</p>
<h2>CPUE 加權 ECDF 環境窗</h2><table><tr><th>參數</th><th>核心 P25–P75</th><th>可能 P10–P90</th><th>最大 ECDF 差異位置</th></tr>${paramRows}</table>
<h2>推薦漁場熱區</h2><table><tr><th>排名</th><th>中心座標</th><th>平均 HSI</th><th>面積 (km²)</th><th>平均SST</th></tr>${rows||'<tr><td colspan=5>無</td></tr>'}</table>
<p class="foot">資料來源：日本氣象廳 JMA GOOS。HSI 為歷史正 CPUE 樣本導出的相對適合度，不是校準後的出現機率；僅供規劃航線與現場判讀，仍須併用氣象、法規與船上探測。</p></body></html>`;
  const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'}));
  a.download=`秋刀魚速預報_${d.date}.html`; a.click();
};

// ── 圖例 ─────────────────────────────────────────────────
function renderLegend() {
  const box = document.getElementById('legend-box');
  let html = '';
  ['sst','subtemp','currents','habitat','fronts'].forEach(k=>{
    const lg=legends[k]; if(!lg) return;
    html+='<div class="legend-block"><div class="legend-title">'+lg.label+(lg.unit?' ('+lg.unit+')':'')+'</div>';
    if (lg.type==='gradient'){
      const g=lg.stops.map((c,i)=>`${c} ${(i/(lg.stops.length-1)*100).toFixed(0)}%`).join(',');
      html+=`<div class="legend-bar" style="background:linear-gradient(90deg,${g})"></div><div class="legend-scale"><span>${lg.vmin}</span><span>${lg.vmax}</span></div>`;
    } else if (lg.type==='discrete'){
      lg.items.forEach(it=>html+=`<div class="legend-item"><span class="legend-sw" style="background:${it.color}"></span>${it.text}</div>`);
      if(lg.note) html+=`<div class="legend-note">${lg.note}</div>`;
    }
    else if (lg.type==='line'){ html+=`<div class="legend-item"><span class="legend-sw" style="background:${lg.color};height:3px"></span>${lg.note||''}</div>`; }
    else if (lg.type==='vector'){ html+=`<div class="legend-item">${lg.note||''}</div>`; }
    html+='</div>';
  });
  box.innerHTML=html; box.classList.toggle('show', html!=='');
}

// ── 滑鼠取值 ─────────────────────────────────────────────
let vt=null;
map.on('mousemove', e=>{ clearTimeout(vt); vt=setTimeout(()=>probe(e.latlng),100); });
function probe(ll){
  if (!curData || ll.lat<VIEW.latS||ll.lat>VIEW.latN||ll.lng<VIEW.lonW||ll.lng>VIEW.lonE){ document.getElementById('live-value').textContent=''; return; }
  const parts=[`${ll.lat.toFixed(2)}°N ${ll.lng.toFixed(2)}°E`];
  const sv=sample(curData.sst,ll.lat,ll.lng); if(!isNaN(sv)) parts.push(`SST ${sv.toFixed(1)}°C`);
  if (curData.sub){ const dep=document.getElementById('sub-depth').value; const tv=sample(curData.sub[dep],ll.lat,ll.lng); if(!isNaN(tv)) parts.push(`${dep} ${tv.toFixed(1)}°C`); }
  if (curData.cur){ const u=sample(curData.cur.u,ll.lat,ll.lng), v=sample(curData.cur.v,ll.lat,ll.lng); if(!isNaN(u)&&!isNaN(v)) parts.push(`流速 ${Math.sqrt(u*u+v*v).toFixed(2)}m/s`); }
  document.getElementById('live-value').textContent=parts.join(' ｜ ');
}

// ── 載入資料 ─────────────────────────────────────────────
async function loadDate(date) {
  if (!gridCache[date]) {
    setStatus('載入資料 '+date+'…','status-busy');
    const r = await fetch(DATA+date+'.json'); gridCache[date] = await r.json();
  }
  const j = gridCache[date];
  curData = { date, sst: decodeGrid(j.sst), subDate:j.subDate||null, curDate:j.curDate||null };
  if (j.sub) { curData.sub = {}; for (const k in j.sub) curData.sub[k]=decodeGrid(j.sub[k]); }
  if (j.cur) { curData.cur = { u: decodeGrid(j.cur.u), v: decodeGrid(j.cur.v) }; }
  renderFreshness();
}
let ecdfChartState=null, ecdfResizeTimer=null;
function setupEcdfChart(curves, summaries){
  const sel=document.getElementById('ecdf-param');
  if(!sel||!curves||!summaries)return;
  ecdfChartState={curves,summaries};
  const keys=Object.keys(summaries).filter(k=>curves[k]);
  sel.innerHTML=keys.map(k=>`<option value="${k}">${summaries[k].label}</option>`).join('');
  sel.value=keys.includes('sst')?'sst':keys[0];
  sel.onchange=()=>drawEcdfChart(sel.value);
  drawEcdfChart(sel.value);
  if(!window.__ecdfResizeBound){
    window.__ecdfResizeBound=true;
    window.addEventListener('resize',()=>{clearTimeout(ecdfResizeTimer);ecdfResizeTimer=setTimeout(()=>{const e=document.getElementById('ecdf-param');if(e?.value)drawEcdfChart(e.value);},120);});
  }
}
function drawEcdfChart(key){
  const canvas=document.getElementById('ecdf-chart'), note=document.getElementById('ecdf-chart-note');
  const curve=ecdfChartState?.curves?.[key], meta=ecdfChartState?.summaries?.[key];
  if(!canvas||!curve||!meta)return;
  const w=Math.max(240,Math.floor(canvas.clientWidth||286)),h=190,dpr=window.devicePixelRatio||1;
  canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);canvas.style.height=h+'px';
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const m={l:34,r:10,t:12,b:30},pw=w-m.l-m.r,ph=h-m.t-m.b;
  const xmin=curve.p10,xmax=curve.p90,span=(xmax-xmin)||1;
  const sx=x=>m.l+(x-xmin)/span*pw, sy=y=>m.t+(1-y)*ph;
  ctx.fillStyle='#eaf3f9';ctx.fillRect(sx(curve.p25),m.t,sx(curve.p75)-sx(curve.p25),ph);
  ctx.font='10px system-ui';ctx.textAlign='right';ctx.textBaseline='middle';
  [0,.25,.5,.75,1].forEach(y=>{ctx.strokeStyle='#d9e2ec';ctx.lineWidth=1;ctx.setLineDash([]);ctx.beginPath();ctx.moveTo(m.l,sy(y));ctx.lineTo(w-m.r,sy(y));ctx.stroke();ctx.fillStyle='#5b6b7c';ctx.fillText(y.toFixed(2).replace(/0+$/,'').replace(/\.$/,''),m.l-5,sy(y));});
  ctx.strokeStyle='#8394a7';ctx.beginPath();ctx.moveTo(m.l,m.t);ctx.lineTo(m.l,h-m.b);ctx.lineTo(w-m.r,h-m.b);ctx.stroke();
  ctx.textAlign='center';ctx.textBaseline='top';
  [xmin,(xmin+xmax)/2,xmax].forEach(x=>{ctx.fillStyle='#5b6b7c';ctx.fillText(Number(x.toFixed(2)).toString(),sx(x),h-m.b+5);});
  ctx.fillText(meta.unit,m.l+pw/2,h-12);
  const plot=(ys,color,dash,width)=>{ctx.save();ctx.beginPath();ctx.rect(m.l,m.t,pw,ph);ctx.clip();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();let started=false;curve.v.forEach((x,i)=>{if(x<xmin||x>xmax)return;const px=sx(x),py=sy(ys[i]);if(!started){ctx.moveTo(px,py);started=true;}else ctx.lineTo(px,py);});ctx.stroke();ctx.restore();};
  plot(curve.cdf,'#64748b',[5,3],1.7);plot(curve.weightedCdf,'#e07a1f',[],2.4);
  if(curve.dMaxValue>=xmin&&curve.dMaxValue<=xmax){ctx.strokeStyle='#1b6ca8';ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(sx(curve.dMaxValue),m.t);ctx.lineTo(sx(curve.dMaxValue),h-m.b);ctx.stroke();}
  const defaultText=`藍底為核心 P25–P75；X 軸聚焦 P10–P90。最大 |F−G|=${curve.dMaxAbs}，位置 ${curve.dMaxValue} ${meta.unit}。`;
  note.textContent=defaultText;canvas.setAttribute('aria-label',`${meta.label} ECDF。${defaultText}`);
  canvas.onmousemove=ev=>{const r=canvas.getBoundingClientRect(),xv=xmin+Math.max(0,Math.min(1,(ev.clientX-r.left-m.l)/pw))*span;let best=0;for(let i=1;i<curve.v.length;i++)if(Math.abs(curve.v[i]-xv)<Math.abs(curve.v[best]-xv))best=i;note.textContent=`${curve.v[best]} ${meta.unit}｜F(x) ${curve.cdf[best].toFixed(3)}｜CPUE 加權 G(x) ${curve.weightedCdf[best].toFixed(3)}`;};
  canvas.onmouseleave=()=>{note.textContent=defaultText;};
}
function fillEcdf() {
  const d=ECDF.summary, el=document.getElementById('ecdf-content'); el.className='ecdf-grid';
  const params=Object.values(d.parameters||{});
  const primary=params.filter(p=>['SST','100mT'].includes(p.column));
  const secondary=params.filter(p=>!['SST','100mT'].includes(p.column));
  const row=p=>`<div class="ecdf-row"><span class="ecdf-k">${p.label}</span><span class="ecdf-v">${p.core[0]}–${p.core[1]} ${p.unit}</span></div>`;
  el.innerHTML=primary.map(row).join('')+
    `<details class="ecdf-more"><summary>查看全部 7 項參數</summary>${secondary.map(row).join('')}</details>`+
    `<div class="method-note">核心窗＝CPUE 加權 P25–P75；HSI 為相對適合度，不是出現機率。</div>`+
    `<div class="ecdf-row"><span class="ecdf-k">歷史樣本</span><span class="ecdf-v">${d.catch_count||0} 筆（${(d.year_range||[]).join('–')}）</span></div>`;
  setupEcdfChart(ECDF.parameters,d.parameters);
}
function renderFreshness(){
  const el=document.getElementById('data-freshness'); if(!el||!curData)return;
  const age=date=>date?Math.max(0,Math.floor((Date.now()-Date.parse(date+'T00:00:00Z'))/86400000)):null;
  const entries=[['SST',curData.date,0],['100mT',curData.subDate,curData.subDate?dayLag(curData.date,curData.subDate):null],['海流',curData.curDate,curData.curDate?dayLag(curData.date,curData.curDate):null]];
  el.innerHTML=entries.map(([name,date,lag])=>{const days=age(date), stale=days==null||days>MAX_SUBSURFACE_LAG_DAYS||lag==null||lag>MAX_SUBSURFACE_LAG_DAYS; return `<div class="fresh-row"><span>${name}</span><span class="fresh-badge ${stale?'stale':'fresh'}">${date||'缺資料'}${days?` · 距今 ${days} 日`:''}${lag?` · 較 SST 落後 ${lag} 日`:''}</span></div>`}).join('');
}
function tick(){ document.getElementById('current-time').textContent=new Date().toLocaleString('zh-TW',{hour12:false}); }

async function init() {
  try {
    const cacheBust='?t='+Date.now();
    const man = await (await fetch(DATA+'manifest.json'+cacheBust,{cache:'no-store'})).json();
    VIEW = man.view;
    map.fitBounds(viewBounds());
    ECDF = await (await fetch(DATA+'ecdf.json'+cacheBust,{cache:'no-store'})).json();
    fillEcdf();
    const sel = document.getElementById('date-select');
    sel.innerHTML = man.dates.map(d=>`<option value="${d}">${d}</option>`).join('');
    await loadDate(man.dates[0]);
    loadImageLayer('sst');
  } catch(e){ setStatus('初始化失敗：'+e,'status-idle'); console.error(e); }
  setInterval(tick,1000); tick();
}
init();
