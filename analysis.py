# -*- coding: utf-8 -*-
"""
秋刀魚漁場速預報 - 海洋特徵分析模組
Ocean feature analysis for saury fishing-ground nowcast.

提供:
  1. 溫度鋒面偵測 (SST gradient front detection) -> GeoJSON 線段
  2. 漁場熱區萃取 (habitat hotspot extraction)   -> 中心座標 / 面積 / 均值
"""

import numpy as np


# ──────────────────────────────────────────────────────────────
#  溫度鋒面偵測
# ──────────────────────────────────────────────────────────────
def compute_sst_gradient(sst, lats, lons):
    """
    計算 SST 水平梯度大小 (°C / km)。

    回傳與 sst 同形狀的梯度陣列（NaN 保留）。
    """
    sst = np.asarray(sst, dtype=float)
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)

    # 每格對應的距離 (km)
    dlat = np.abs(np.gradient(lats)) * 111.0                    # 緯向
    dlon = np.abs(np.gradient(lons)) * 111.0 * np.cos(np.radians(lats.mean()))

    gy, gx = np.gradient(sst)                                   # 沿 row(緯), col(經)
    gy_km = gy / dlat[:, None]
    gx_km = gx / dlon[None, :]
    grad = np.sqrt(gy_km ** 2 + gx_km ** 2)
    return grad


def detect_fronts(sst, lats, lons, threshold=0.05, lat_min=None, lat_max=None,
                  lon_min=None, lon_max=None):
    """
    以 SST 梯度等值線偵測溫度鋒面。

    Args:
        threshold: 鋒面梯度門檻 (°C/km)，預設 0.05 (=5°C/100km)
    Returns:
        GeoJSON FeatureCollection（LineString），可直接給 Leaflet L.geoJSON
        以及 stats: {'threshold', 'max_gradient', 'front_count'}
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    grad = compute_sst_gradient(sst, lats, lons)
    grad_filled = np.where(np.isnan(grad), 0.0, grad)

    lon_grid, lat_grid = np.meshgrid(lons, lats)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    cs = ax.contour(lon_grid, lat_grid, grad_filled, levels=[threshold])

    features = []
    seg_count = 0
    # 相容新舊 matplotlib：優先 allsegs
    segs = []
    if hasattr(cs, 'allsegs') and cs.allsegs:
        for level_segs in cs.allsegs:
            segs.extend(level_segs)
    plt.close(fig)

    for seg in segs:
        if len(seg) < 4:
            continue
        coords = [[round(float(x), 4), round(float(y), 4)] for x, y in seg]
        features.append({
            'type': 'Feature',
            'properties': {'kind': 'front'},
            'geometry': {'type': 'LineString', 'coordinates': coords}
        })
        seg_count += 1

    geojson = {'type': 'FeatureCollection', 'features': features}
    stats = {
        'threshold': threshold,
        'max_gradient': float(np.nanmax(grad)) if np.isfinite(np.nanmax(grad)) else 0.0,
        'front_count': seg_count
    }
    return geojson, stats


# ──────────────────────────────────────────────────────────────
#  漁場熱區萃取
# ──────────────────────────────────────────────────────────────
def extract_hotspots(prob, lats, lons, sst=None, prob_threshold=0.6,
                     min_area_km2=1500, max_spots=12):
    """
    從棲息機率網格萃取高機率連通熱區。

    Args:
        prob           : 棲息機率網格 (0-1)，與 lats/lons 對齊
        sst            : （可選）同網格 SST，用於計算熱區平均水溫
        prob_threshold : 熱區判定門檻
        min_area_km2   : 最小面積（過濾雜點）
        max_spots      : 最多回傳幾個熱區（依機率×面積排序）
    Returns:
        list[dict]，每個熱區含 center/area/mean_prob/mean_sst/rank/polygon
    """
    from scipy import ndimage

    prob = np.asarray(prob, dtype=float)
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)

    mask = np.where(np.isnan(prob), False, prob >= prob_threshold)
    if not mask.any():
        return []

    labeled, n = ndimage.label(mask)

    # 每格面積 (km^2)
    dlat_km = np.abs(np.gradient(lats)) * 111.0
    dlon_km = np.abs(np.gradient(lons)) * 111.0 * np.cos(np.radians(lats.mean()))
    cell_area = dlat_km[:, None] * dlon_km[None, :]

    lon_grid, lat_grid = np.meshgrid(lons, lats)

    spots = []
    for lab in range(1, n + 1):
        m = labeled == lab
        area = float(cell_area[m].sum())
        if area < min_area_km2:
            continue
        pvals = prob[m]
        weights = pvals  # 以機率為權重求加權中心
        wsum = weights.sum()
        c_lat = float((lat_grid[m] * weights).sum() / wsum)
        c_lon = float((lon_grid[m] * weights).sum() / wsum)
        spot = {
            'center': [round(c_lat, 3), round(c_lon, 3)],
            'area_km2': round(area, 0),
            'mean_prob': round(float(pvals.mean()), 3),
            'max_prob': round(float(pvals.max()), 3),
            'lat_range': [round(float(lat_grid[m].min()), 2), round(float(lat_grid[m].max()), 2)],
            'lon_range': [round(float(lon_grid[m].min()), 2), round(float(lon_grid[m].max()), 2)],
        }
        if sst is not None:
            svals = sst[m]
            svals = svals[~np.isnan(svals)]
            spot['mean_sst'] = round(float(svals.mean()), 2) if svals.size else None
        spots.append(spot)

    # 綜合排序分數：平均機率 × log(面積)
    spots.sort(key=lambda s: s['mean_prob'] * np.log10(s['area_km2'] + 10), reverse=True)
    spots = spots[:max_spots]
    for i, s in enumerate(spots, 1):
        s['rank'] = i
    return spots


# ──────────────────────────────────────────────────────────────
#  等溫線（isotherms）
# ──────────────────────────────────────────────────────────────
def compute_isotherms(grid, lats, lons, vmin, vmax, interval=2,
                      lon_min=None, lon_max=None, lat_min=None, lat_max=None):
    """
    產生等溫線 GeoJSON（LineString，每條含 temp 屬性）與標註點。

    Returns:
        geojson : FeatureCollection，properties.temp 為該線溫度
        labels  : list[{lat, lon, temp}]，每個溫度層級一個標註（取最長線段中點）
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    grid = np.asarray(grid, dtype=float)
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    levels = np.arange(np.floor(vmin), np.ceil(vmax) + interval, interval)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    fig = plt.figure(); ax = fig.add_subplot(111)
    masked = np.ma.masked_invalid(grid)   # 遮蔽 NaN，避免資料邊界產生假等溫線
    cs = ax.contour(lon_grid, lat_grid, masked, levels=levels)

    features, labels = [], []
    lvls = list(cs.levels)
    allsegs = cs.allsegs if hasattr(cs, 'allsegs') else []
    plt.close(fig)

    for li, segs in enumerate(allsegs):
        temp = round(float(lvls[li]), 1)
        if temp < vmin - 0.001:
            continue
        longest = None; longest_len = 0
        for seg in segs:
            if len(seg) < 3:
                continue
            coords = [[round(float(x), 4), round(float(y), 4)] for x, y in seg]
            features.append({
                'type': 'Feature',
                'properties': {'temp': temp},
                'geometry': {'type': 'LineString', 'coordinates': coords}
            })
            if len(seg) > longest_len:
                longest_len = len(seg); longest = seg
        if longest is not None:
            mid = longest[len(longest) // 2]
            labels.append({'lat': round(float(mid[1]), 3),
                           'lon': round(float(mid[0]), 3), 'temp': temp})

    return {'type': 'FeatureCollection', 'features': features}, labels
