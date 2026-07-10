# -*- coding: utf-8 -*-
"""
西北太平洋秋刀魚漁場速預報系統 - Flask Web Server (Leaflet 版)
農業部水產試驗所 漁海況研究小組
"""

import threading
import numpy as np
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_from_directory

import config
from data_parser import DataManager
from ecdf_analyzer import SauryECDFAnalyzer, HabitatPredictor
import overlay_renderer as ovr
import analysis

app = Flask(__name__)
# 樣板自動重載 + 靜態檔不快取，確保改版後立即生效
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


@app.after_request
def _no_cache(resp):
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


data_manager = DataManager()
ecdf_analyzer = SauryECDFAnalyzer()
habitat_predictor = None
_data_loaded = False
_load_lock = threading.Lock()

_update_state = {'running': False, 'progress': 0, 'total': 0, 'message': '', 'done': False, 'error': None}


def ensure_data_loaded(force=False):
    global _data_loaded, habitat_predictor
    with _load_lock:
        if _data_loaded and not force:
            return
        data_manager.himsst_cache.clear()
        data_manager.nprsubt_cache.clear()
        data_manager.nprsubc_cache.clear()
        data_manager.load_himsst_files()
        data_manager.load_nprsubt_files()
        data_manager.load_nprsubc_files()
        if ecdf_analyzer.data is None:
            if ecdf_analyzer.load_data():
                ecdf_analyzer.analyze_sst()
                ecdf_analyzer.analyze_100m_temp()
                habitat_predictor = HabitatPredictor(ecdf_analyzer)
        _data_loaded = True


def latest_date():
    dates = sorted(data_manager.himsst_cache.keys(), reverse=True)
    return dates[0] if dates else None


def _nearest_cached_date(cache, date):
    keys = sorted(cache.keys())
    if not keys:
        return None
    le = [k for k in keys if k <= date]
    return le[-1] if le else keys[0]


def get_nprsubt_near(date):
    return data_manager.get_nprsubt(_nearest_cached_date(data_manager.nprsubt_cache, date))


def get_nprsubc_near(date):
    return data_manager.get_nprsubc(_nearest_cached_date(data_manager.nprsubc_cache, date))


def compute_habitat(date):
    if habitat_predictor is None:
        return None
    sst_data = data_manager.get_himsst(date)
    nprsubt_data = get_nprsubt_near(date)
    if sst_data is None or nprsubt_data is None:
        return None
    pred = habitat_predictor.predict(sst_data, nprsubt_data)
    if pred is None:
        return None
    lats = np.asarray(pred['lats']); lons = np.asarray(pred['lons'])
    lat_m = (lats >= config.VIEW_LAT_MIN - 0.5) & (lats <= config.VIEW_LAT_MAX + 0.5)
    lon_m = (lons >= config.VIEW_LON_MIN - 0.5) & (lons <= config.VIEW_LON_MAX + 0.5)
    prob = pred['probability'][np.ix_(lat_m, lon_m)]
    sst = sst_data['sst'][np.ix_(lat_m, lon_m)]
    return prob, sst, lats[lat_m], lons[lon_m]


@app.route('/')
def index():
    ensure_data_loaded()
    dates = sorted(data_manager.himsst_cache.keys(), reverse=True)
    return render_template('index.html', dates=dates,
                           view={'lat_min': config.VIEW_LAT_MIN, 'lat_max': config.VIEW_LAT_MAX,
                                 'lon_min': config.VIEW_LON_MIN, 'lon_max': config.VIEW_LON_MAX})


@app.route('/api/dates')
def api_dates():
    ensure_data_loaded()
    return jsonify(data_manager.get_available_dates())


@app.route('/api/ecdf-summary')
def api_ecdf_summary():
    ensure_data_loaded()
    return jsonify(ecdf_analyzer.get_summary())


@app.route('/api/overlay/<layer>')
def api_overlay(layer):
    ensure_data_loaded()
    date = request.args.get('date', '') or latest_date()
    depth = request.args.get('depth', '100m')
    alpha = int(request.args.get('alpha', 210))
    try:
        if layer == 'sst':
            d = data_manager.get_himsst(date)
            if d is None:
                return jsonify({'error': f'找不到 {date} 的 SST 資料'}), 404
            return jsonify(ovr.render_sst(d, alpha=alpha))
        if layer == 'subtemp':
            d = get_nprsubt_near(date)
            if d is None:
                return jsonify({'error': f'找不到 {date} 的次表層水溫資料'}), 404
            return jsonify(ovr.render_subtemp(d, depth=depth, alpha=alpha))
        if layer == 'currents':
            d = get_nprsubc_near(date)
            if d is None:
                return jsonify({'error': f'找不到 {date} 的海流資料'}), 404
            skip = int(request.args.get('skip', config.CURRENT_ARROW_SKIP))
            arrow_size = float(request.args.get('arrow_size', 1.0))
            return jsonify(ovr.render_currents(d, skip=skip, arrow_size=arrow_size, alpha=alpha))
        if layer == 'habitat':
            hb = compute_habitat(date)
            if hb is None:
                return jsonify({'error': '棲息機率計算失敗（缺 SST 或次表層資料）'}), 404
            prob, sst, lats, lons = hb
            return jsonify(ovr.render_habitat(prob, lats, lons, alpha=alpha))
        return jsonify({'error': f'未知圖層: {layer}'}), 400
    except Exception as e:
        return jsonify({'error': f'{layer} 渲染失敗: {e}'}), 500


@app.route('/api/fronts')
def api_fronts():
    ensure_data_loaded()
    date = request.args.get('date', '') or latest_date()
    threshold = float(request.args.get('threshold', 0.05))
    d = data_manager.get_himsst(date)
    if d is None:
        return jsonify({'error': f'找不到 {date} 的 SST 資料'}), 404
    geojson, stats = analysis.detect_fronts(d['sst'], d['lats'], d['lons'], threshold=threshold)
    return jsonify({'geojson': geojson, 'stats': stats, 'date': date})


@app.route('/api/hotspots')
def api_hotspots():
    ensure_data_loaded()
    date = request.args.get('date', '') or latest_date()
    threshold = float(request.args.get('prob', 0.6))
    hb = compute_habitat(date)
    if hb is None:
        return jsonify({'error': '棲息機率計算失敗'}), 404
    prob, sst, lats, lons = hb
    spots = analysis.extract_hotspots(prob, lats, lons, sst=sst, prob_threshold=threshold)
    return jsonify({'hotspots': spots, 'count': len(spots), 'date': date, 'prob_threshold': threshold})


@app.route('/api/forecast')
def api_forecast():
    ensure_data_loaded()
    date = request.args.get('date', '') or latest_date()
    if date is None:
        return jsonify({'error': '尚無可用資料，請先更新資料'}), 404
    result = {'date': date, 'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M')}
    result['ecdf'] = ecdf_analyzer.get_summary()
    hb = compute_habitat(date)
    if hb is not None:
        prob, sst, lats, lons = hb
        result['habitat'] = ovr.render_habitat(prob, lats, lons)
        spots = analysis.extract_hotspots(prob, lats, lons, sst=sst, prob_threshold=0.6)
        result['hotspots'] = spots
        cell = np.abs(np.gradient(lats))[:, None] * 111.0 * \
               (np.abs(np.gradient(lons))[None, :] * 111.0 * np.cos(np.radians(lats.mean())))
        high_mask = np.where(np.isnan(prob), False, prob >= 0.6)
        result['high_prob_area_km2'] = round(float(cell[high_mask].sum()), 0)
    else:
        result['hotspots'] = []
        result['high_prob_area_km2'] = 0
    d = data_manager.get_himsst(date)
    if d is not None:
        geojson, stats = analysis.detect_fronts(d['sst'], d['lats'], d['lons'], threshold=0.05)
        result['fronts'] = geojson
        result['front_stats'] = stats
        result['sst_overlay'] = ovr.render_sst(d)
    return jsonify(result)


def _nearest(grid, lats, lons, lat, lon):
    lats = np.asarray(lats); lons = np.asarray(lons)
    if lat < min(lats.min(), lats.max()) or lat > max(lats.min(), lats.max()):
        return None
    if lon < lons.min() or lon > lons.max():
        return None
    i = int(np.abs(lats - lat).argmin())
    j = int(np.abs(lons - lon).argmin())
    v = grid[i, j]
    return None if np.isnan(v) else round(float(v), 2)



@app.route('/api/isotherms')
def api_isotherms():
    ensure_data_loaded()
    layer = request.args.get('layer', 'sst')
    date = request.args.get('date', '') or latest_date()
    depth = request.args.get('depth', '100m')
    interval = float(request.args.get('interval', 2))
    if layer == 'subtemp':
        d = get_nprsubt_near(date)
        if d is None:
            return jsonify({'error': f'找不到 {date} 的次表層水溫資料'}), 404
        grid = d[f'temp_{depth}']; lats = d['lats']; lons = d['lons']
        vmin, vmax = config.SUBTEMP_VMIN, config.SUBTEMP_VMAX
    else:
        d = data_manager.get_himsst(date)
        if d is None:
            return jsonify({'error': f'找不到 {date} 的 SST 資料'}), 404
        grid = d['sst']; lats = d['lats']; lons = d['lons']
        vmin, vmax = config.SST_VMIN, config.SST_VMAX
    geojson, labels = analysis.compute_isotherms(grid, lats, lons, vmin, vmax, interval=interval)
    return jsonify({'geojson': geojson, 'labels': labels, 'interval': interval, 'date': date})


@app.route('/api/value')
def api_value():
    ensure_data_loaded()
    date = request.args.get('date', '') or latest_date()
    depth = request.args.get('depth', '100m')
    try:
        lat = float(request.args.get('lat')); lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({'value': None})
    out = {}
    d_sst = data_manager.get_himsst(date)
    if d_sst is not None:
        out['sst'] = _nearest(d_sst['sst'], d_sst['lats'], d_sst['lons'], lat, lon)
    d_sub = get_nprsubt_near(date)
    if d_sub is not None and f'temp_{depth}' in d_sub:
        out['subtemp'] = _nearest(d_sub[f'temp_{depth}'], d_sub['lats'], d_sub['lons'], lat, lon)
        out['depth'] = depth
    d_cur = get_nprsubc_near(date)
    if d_cur is not None:
        out['current'] = _nearest(d_cur['speed'], d_cur['lats'], d_cur['lons'], lat, lon)
    return jsonify(out)


def _run_update(count):
    global _update_state
    try:
        from data_downloader import JMADataDownloader

        def cb(cur, total, msg):
            _update_state.update({'progress': cur, 'total': total, 'message': msg})

        dl = JMADataDownloader()
        _update_state.update({'message': '開始下載 HIMSST…'})
        dl.download_himsst(count, cb)
        _update_state.update({'message': '開始下載 NPRSUBT…'})
        dl.download_nprsubt(count, cb)
        _update_state.update({'message': '開始下載 NPRSUBC…'})
        dl.download_nprsubc(count, cb)
        ensure_data_loaded(force=True)
        _update_state.update({'message': '資料更新完成', 'done': True})
    except Exception as e:
        _update_state.update({'error': str(e), 'message': f'更新失敗: {e}', 'done': True})
    finally:
        _update_state['running'] = False


@app.route('/api/update-data', methods=['POST'])
def api_update_data():
    global _update_state
    if _update_state['running']:
        return jsonify({'status': 'already_running'}), 409
    count = int(request.args.get('count', config.DOWNLOAD_COUNT))
    _update_state = {'running': True, 'progress': 0, 'total': count * 3,
                     'message': '準備中…', 'done': False, 'error': None}
    threading.Thread(target=_run_update, args=(count,), daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/update-status')
def api_update_status():
    return jsonify(_update_state)


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)



def start_auto_update():
    """伺服器啟動時，於背景自動下載最新 JMA 資料。"""
    if not getattr(config, 'AUTO_UPDATE_ON_START', False):
        return
    if _update_state.get('running'):
        return
    count = getattr(config, 'AUTO_UPDATE_COUNT', config.DOWNLOAD_COUNT)
    _update_state.update({'running': True, 'progress': 0, 'total': count * 3,
                          'message': '啟動自動更新中…', 'done': False, 'error': None})
    threading.Thread(target=_run_update, args=(count,), daemon=True).start()


if __name__ == '__main__':
    print('=' * 60)
    print('  秋刀魚漁場速預報系統 (Leaflet)  http://localhost:5000')
    print('=' * 60)
    start_auto_update()
    app.run(debug=False, host='0.0.0.0', port=5000)
