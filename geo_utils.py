# -*- coding: utf-8 -*-
"""
地理投影與網格重取樣工具
Geo projection / regridding utilities (Web Mercator, EPSG:3857)

供 Leaflet imageOverlay 使用：將 lat/lon 規則網格資料重取樣為
「經度線性、緯度為 Mercator-y 線性」的影像，如此以正確的地理
邊界 imageOverlay 疊在 Leaflet（預設 Web Mercator）上時像素可精準對齊。
"""

import numpy as np

# Web Mercator 緯度上限
MERCATOR_MAX_LAT = 85.05112878


def lat_to_mercator_y(lat):
    """緯度 -> Web Mercator 正規化 y（弧度形式，僅供線性內插用）"""
    lat = np.clip(lat, -MERCATOR_MAX_LAT, MERCATOR_MAX_LAT)
    return np.log(np.tan(np.pi / 4.0 + np.radians(lat) / 2.0))


def mercator_y_to_lat(y):
    """Mercator y -> 緯度"""
    return np.degrees(2.0 * np.arctan(np.exp(y)) - np.pi / 2.0)


def resample_to_mercator(grid, src_lats, src_lons,
                         lat_min, lat_max, lon_min, lon_max,
                         out_h=None, out_w=None):
    """
    將 (lat, lon) 規則網格資料重取樣到 Web Mercator 影像網格。

    回傳:
        merc_grid : 2D array，row 0 = 最北（影像上方），欄 0 = 最西
        bounds    : [[lat_min, lon_min], [lat_max, lon_max]]（給 Leaflet）
    NaN 會被保留（後續轉為透明）。
    """
    src_lats = np.asarray(src_lats, dtype=float)
    src_lons = np.asarray(src_lons, dtype=float)

    # 來源網格若為降序（北->南）先轉為升序方便內插
    if src_lats[0] > src_lats[-1]:
        src_lats = src_lats[::-1]
        grid = grid[::-1, :]
    if src_lons[0] > src_lons[-1]:
        src_lons = src_lons[::-1]
        grid = grid[:, ::-1]

    if out_w is None:
        out_w = min(1400, max(600, len(src_lons)))
    if out_h is None:
        out_h = min(1400, max(600, len(src_lats)))

    # 目標經度：線性
    tgt_lons = np.linspace(lon_min, lon_max, out_w)

    # 目標緯度：Mercator-y 線性 -> 反算回緯度
    y_top = lat_to_mercator_y(lat_max)
    y_bot = lat_to_mercator_y(lat_min)
    tgt_y = np.linspace(y_top, y_bot, out_h)   # row 0 = 北
    tgt_lats = mercator_y_to_lat(tgt_y)

    # 對每一維做線性內插（先沿經度，再沿緯度）
    # 沿經度內插
    col_idx = np.interp(tgt_lons, src_lons, np.arange(len(src_lons)))
    # 沿緯度內插
    row_idx = np.interp(tgt_lats, src_lats, np.arange(len(src_lats)))

    c0 = np.floor(col_idx).astype(int)
    c1 = np.clip(c0 + 1, 0, len(src_lons) - 1)
    cf = col_idx - c0
    r0 = np.floor(row_idx).astype(int)
    r1 = np.clip(r0 + 1, 0, len(src_lats) - 1)
    rf = row_idx - r0

    def bilinear(a):
        # 以 NaN-aware 方式雙線性內插
        top = _lerp(a[r0][:, c0], a[r0][:, c1], cf)
        bot = _lerp(a[r1][:, c0], a[r1][:, c1], cf)
        return _lerp(top, bot, rf[:, None])

    merc = bilinear(grid)

    bounds = [[float(lat_min), float(lon_min)], [float(lat_max), float(lon_max)]]
    return merc, bounds


def _lerp(a, b, f):
    """線性內插，任一端為 NaN 時取另一端（避免邊界破洞擴散）"""
    out = a * (1 - f) + b * f
    na = np.isnan(a)
    nb = np.isnan(b)
    out = np.where(na & ~nb, b, out)
    out = np.where(nb & ~na, a, out)
    out = np.where(na & nb, np.nan, out)
    return out


def regrid_nearest(grid, src_lats, src_lons, dst_lats, dst_lons):
    """把資料以最近鄰重取樣到目標 lat/lon 網格（供欄位對齊，如 100m 水溫對到 SST 網格）"""
    src_lats = np.asarray(src_lats, dtype=float)
    src_lons = np.asarray(src_lons, dtype=float)
    lat_idx = np.abs(dst_lats[:, None] - src_lats[None, :]).argmin(axis=1)
    lon_idx = np.abs(dst_lons[:, None] - src_lons[None, :]).argmin(axis=1)
    return grid[np.ix_(lat_idx, lon_idx)]
