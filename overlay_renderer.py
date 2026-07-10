# -*- coding: utf-8 -*-
"""
Leaflet 透明疊圖渲染器（免 cartopy）
Overlay renderer for Leaflet imageOverlay.

將海洋欄位資料重取樣為 Web Mercator 影像，輸出去背 PNG(base64) + 地理邊界，
陸地/無資料 (NaN) 皆為透明，交由 Leaflet 底圖顯示海岸線。
"""

import io
import base64
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize, BoundaryNorm

import config
from geo_utils import resample_to_mercator, regrid_nearest

# ── 色彩映射 ──────────────────────────────────────────────
SST_STOPS = ['#000080', '#0000ff', '#00bfff', '#00ff80', '#80ff00',
             '#ffff00', '#ff8000', '#ff0000', '#800000']
SST_CMAP = LinearSegmentedColormap.from_list('sst', SST_STOPS, N=256)

HAB_LEVELS = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
HAB_COLORS = ['#cccccc', '#ffff00', '#80ff00', '#00cc00', '#006600']
HAB_CMAP = LinearSegmentedColormap.from_list('habitat', HAB_COLORS, N=len(HAB_COLORS))
HAB_NORM = BoundaryNorm(HAB_LEVELS, HAB_CMAP.N)

# 顯示範圍
LAT_MIN, LAT_MAX = config.VIEW_LAT_MIN, config.VIEW_LAT_MAX
LON_MIN, LON_MAX = config.VIEW_LON_MIN, config.VIEW_LON_MAX


def _rgba_png_b64(rgba):
    """把 (H,W,4) uint8 陣列輸出成 base64 PNG（純影像，無邊框）"""
    from PIL import Image
    img = Image.fromarray(rgba, mode='RGBA')
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _colorize(merc, cmap, norm, alpha=210):
    """把數值網格上色為 RGBA，NaN -> 透明"""
    finite = np.isfinite(merc)
    rgba = np.zeros((merc.shape[0], merc.shape[1], 4), dtype=np.uint8)
    if finite.any():
        vals = np.where(finite, merc, norm.vmin if hasattr(norm, 'vmin') else 0)
        colored = cmap(norm(vals))            # (H,W,4) float 0-1
        rgba[..., :3] = (colored[..., :3] * 255).astype(np.uint8)
        rgba[..., 3] = np.where(finite, alpha, 0).astype(np.uint8)
    return rgba


def _hex_gradient(stops):
    return [{'pos': i / (len(stops) - 1), 'color': c} for i, c in enumerate(stops)]


# ── SST / 次表層水溫（連續場）────────────────────────────
def render_scalar(grid, lats, lons, vmin, vmax, label, unit='°C',
                  stops=None, alpha=210):
    stops = stops or SST_STOPS
    cmap = LinearSegmentedColormap.from_list('c', stops, N=256)
    norm = Normalize(vmin=vmin, vmax=vmax)
    merc, bounds = resample_to_mercator(grid, lats, lons,
                                        LAT_MIN, LAT_MAX, LON_MIN, LON_MAX)
    rgba = _colorize(merc, cmap, norm, alpha=alpha)
    return {
        'image': _rgba_png_b64(rgba),
        'bounds': bounds,
        'legend': {
            'type': 'gradient', 'label': label, 'unit': unit,
            'vmin': vmin, 'vmax': vmax, 'stops': _hex_gradient(stops)
        }
    }


def render_sst(sst_data, alpha=210):
    return render_scalar(sst_data['sst'], sst_data['lats'], sst_data['lons'],
                         config.SST_VMIN, config.SST_VMAX, '海面水溫 SST', '°C',
                         SST_STOPS, alpha)


def render_subtemp(nprsubt_data, depth='100m', alpha=210):
    key = f'temp_{depth}'
    return render_scalar(nprsubt_data[key], nprsubt_data['lats'], nprsubt_data['lons'],
                         config.SUBTEMP_VMIN, config.SUBTEMP_VMAX,
                         f'{depth} 水溫', '°C', SST_STOPS, alpha)


# ── 棲息機率（離散場）──────────────────────────────────────
def render_habitat(prob, lats, lons, alpha=200):
    merc, bounds = resample_to_mercator(prob, lats, lons,
                                        LAT_MIN, LAT_MAX, LON_MIN, LON_MAX)
    rgba = _colorize(merc, HAB_CMAP, HAB_NORM, alpha=alpha)
    return {
        'image': _rgba_png_b64(rgba),
        'bounds': bounds,
        'legend': {
            'type': 'discrete', 'label': '秋刀魚棲息機率', 'unit': '',
            'items': [
                {'color': '#cccccc', 'text': '低 (<20%)'},
                {'color': '#ffff00', 'text': '中低 (20–40%)'},
                {'color': '#80ff00', 'text': '中 (40–60%)'},
                {'color': '#00cc00', 'text': '高 (60–80%)'},
                {'color': '#006600', 'text': '極高 (>80%)'},
            ]
        }
    }


# ── 表面海流（向量場 -> quiver PNG）────────────────────────
def render_currents(nprsubc_data, skip=None, arrow_size=1.0, alpha=230):
    """skip: 空間解析度(取樣間隔，越大越稀疏)；arrow_size: 箭頭大小倍率(0.5~2.0)。"""
    u = nprsubc_data['u']; v = nprsubc_data['v']
    lats = np.asarray(nprsubc_data['lats'], dtype=float)
    lons = np.asarray(nprsubc_data['lons'], dtype=float)
    if skip is None:
        skip = config.CURRENT_ARROW_SKIP

    # 轉為升序
    if lats[0] > lats[-1]:
        lats = lats[::-1]; u = u[::-1, :]; v = v[::-1, :]

    from geo_utils import lat_to_mercator_y
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    us = u[::skip, ::skip]; vs = v[::skip, ::skip]
    lon_s = lon_grid[::skip, ::skip]; lat_s = lat_grid[::skip, ::skip]
    speed = np.sqrt(us ** 2 + vs ** 2)

    # 以 Mercator y 當作繪圖縱座標，確保與底圖對齊
    y_s = lat_to_mercator_y(lat_s)
    y_top = lat_to_mercator_y(LAT_MAX); y_bot = lat_to_mercator_y(LAT_MIN)

    W, H = 1400, 1400
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(LON_MIN, LON_MAX)
    ax.set_ylim(y_bot, y_top)
    ax.axis('off')
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    # 箭頭大小：scale 越小箭頭越長，故與 arrow_size 成反比；線寬與 arrow_size 成正比
    arrow_size = max(0.4, min(2.5, float(arrow_size)))
    q_scale = 6.0 / arrow_size
    q_width = 0.0022 * (0.6 + 0.7 * arrow_size)
    mask = np.isfinite(us) & np.isfinite(vs)
    q = ax.quiver(lon_s[mask], y_s[mask], us[mask], vs[mask], speed[mask],
                  cmap='cool', scale=q_scale, width=q_width, headwidth=3.2,
                  headlength=4, alpha=alpha / 255.0, pivot='mid')

    buf = io.BytesIO()
    fig.savefig(buf, format='png', transparent=True, dpi=100)
    plt.close(fig)
    b64 = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')

    bounds = [[LAT_MIN, LON_MIN], [LAT_MAX, LON_MAX]]
    return {
        'image': b64, 'bounds': bounds,
        'legend': {'type': 'vector', 'label': '表面海流', 'unit': 'm/s',
                   'note': '箭頭方向為流向，色階代表流速'},
        'settings': {'skip': int(skip), 'arrow_size': round(float(arrow_size), 2)}
    }
