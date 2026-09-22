# -*- coding: utf-8 -*-
"""
forecast.py — 秋刀魚漁場「當日速報 + 往後三日預報」的海況外推引擎。

為什麼要自建外推
────────────────
JMA NEAR-GOOS 公開產品目錄（HIMSST / MGDSST / NPR-4DVAR / MOVE / COBE-SST2）
**只有分析場，沒有任何公開的海況預報產品**。三日預報因此無法直接下載，必須
由 JMA 分析場外推。

已驗證的方案（見 config.py 與設計文件 §5）
──────────────────────────────────────────
    SST(t+n) = SST(t) + α × 大尺度趨勢 × n

  · 大尺度趨勢：先對最近 FORECAST_TREND_DAYS 日做逐格最小二乘斜率，再以
    FORECAST_TREND_SCALE_DEG 度的箱形平均濾掉雲隙與同化雜訊，保留隨緯度
    變化的季節升降溫率。
  · α：收縮係數，以分割樣本法選定（訓練期前半、測試期後半）。
  · 逐格斜率與總變化量均設上限，並以基準場的有效遮罩為準，不填補陸地或缺值。

以 2026-07-02~09-20 共 81 日連續 HIMSST 分析場驗證，測試期（後半 34 個起報
日，未參與調參）相對持續性法的 RMSE 改進為 +8.6/+8.7/+8.1%（全域）與
+8.8/+9.7/+9.8%（漁場區，lead 1/2/3）。

經量化驗證為有害而預設關閉的成分（程式碼保留，供日後重測）
──────────────────────────────────────────────────────────
  · 表面海流半拉格朗日平流 `advect()`：lead1 −24.4%、lead3 −14.6%。
    HIMSST 是多衛星融合分析場，NPRSUBC 是獨立的 4DVAR 流場分析，兩者誤差
    不相關；用後者平流前者只會把鋒面搬到錯的位置。
  · 預報場 3×3 平滑：lead1 −17.4%。
  · 未經大尺度化的逐格趨勢：lead3 −4.1%。

次表層水溫（100 m）變化尺度遠長於 3 日，採「持續 + 強收縮趨勢」，不做平流。
表面海流採持續場。**沒有任何一項是 JMA 官方預報；介面與報告必須標示清楚。**

東界問題
────────
NPRSUBT / NPRSUBC 為「日本近海（jpn）」產品，東界僅至 163.45°E / 163.5°E。
其以東無次表層資訊，HSI 自動降階為 SST 單因子。本模組不會以邊界值外推填滿
東側海域。

回溯驗證
────────
`verify_hindcast()` 以 D−n 的資料做 n 日預報，與 D 的實測 SST 比對，回報
RMSE、MAE、偏差，以及相對純持續性法的改進率，輸出到 manifest.json 並直接
顯示於網頁——預報若沒有比持續性法好，使用者有權利知道。
"""

from __future__ import annotations

import numpy as np

import config


# ──────────────────────────────────────────────────────────────
#  基本工具
# ──────────────────────────────────────────────────────────────
def smooth3(a, passes=1):
    """NaN 安全的 3x3 平均平滑。"""
    a = np.asarray(a, dtype=float)
    for _ in range(max(0, int(passes))):
        valid = np.isfinite(a)
        filled = np.where(valid, a, 0.0)
        acc = np.zeros_like(filled)
        cnt = np.zeros_like(filled)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                acc += np.roll(np.roll(filled, dy, axis=0), dx, axis=1)
                cnt += np.roll(np.roll(valid.astype(float), dy, axis=0), dx, axis=1)
        out = np.where(cnt > 0, acc / np.maximum(cnt, 1e-9), np.nan)
        a = np.where(valid, out, np.nan)      # 只平滑原本有值處，不擴張到陸地
    return a


def linear_trend(stack, days):
    """
    逐格最小二乘斜率 (unit/day)。

    Args:
        stack : (T, ny, nx)，時間由舊到新，可含 NaN
        days  : (T,) 相對天數（例 [-6,-5,...,0]）
    Returns:
        slope (ny, nx)；有效樣本少於 3 個的格點為 NaN
    """
    stack = np.asarray(stack, dtype=float)
    t = np.asarray(days, dtype=float)[:, None, None]
    valid = np.isfinite(stack)
    n = valid.sum(axis=0)

    x = np.where(valid, t, 0.0)
    y = np.where(valid, stack, 0.0)
    sx = x.sum(axis=0)
    sy = y.sum(axis=0)
    sxx = (x * x).sum(axis=0)
    sxy = (x * y).sum(axis=0)

    denom = n * sxx - sx * sx
    with np.errstate(invalid='ignore', divide='ignore'):
        slope = (n * sxy - sx * sy) / denom
    slope = np.where((n >= 3) & (np.abs(denom) > 1e-9), slope, np.nan)
    return slope


def _bilinear_sample(grid, lats, lons, tgt_lat, tgt_lon):
    """
    在 (lats, lons) 規則網格上以雙線性內插取 (tgt_lat, tgt_lon) 的值。
    lats 可為降序；超出範圍回傳 NaN。tgt_* 與輸出同形狀。
    """
    grid = np.asarray(grid, dtype=float)
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)

    desc = lats[0] > lats[-1]
    if desc:
        lats_a = lats[::-1]
        grid_a = grid[::-1, :]
    else:
        lats_a, grid_a = lats, grid

    ny, nx = grid_a.shape
    fy = np.interp(tgt_lat, lats_a, np.arange(ny), left=np.nan, right=np.nan)
    fx = np.interp(tgt_lon, lons, np.arange(nx), left=np.nan, right=np.nan)

    ok = np.isfinite(fy) & np.isfinite(fx)
    fy_s = np.where(ok, fy, 0.0)
    fx_s = np.where(ok, fx, 0.0)

    y0 = np.floor(fy_s).astype(int)
    x0 = np.floor(fx_s).astype(int)
    y1 = np.clip(y0 + 1, 0, ny - 1)
    x1 = np.clip(x0 + 1, 0, nx - 1)
    y0 = np.clip(y0, 0, ny - 1)
    x0 = np.clip(x0, 0, nx - 1)
    ty = fy_s - y0
    tx = fx_s - x0

    def lerp(a, b, f):
        na, nb = np.isnan(a), np.isnan(b)
        out = np.where(na, b, np.where(nb, a, a * (1 - f) + b * f))
        return np.where(na & nb, np.nan, out)

    top = lerp(grid_a[y0, x0], grid_a[y0, x1], tx)
    bot = lerp(grid_a[y1, x0], grid_a[y1, x1], tx)
    val = lerp(top, bot, ty)
    return np.where(ok, val, np.nan)


def regrid(grid, src_lats, src_lons, dst_lats, dst_lons):
    """把來源網格雙線性重取樣到目標 lat/lon 網格（超出來源範圍為 NaN）。"""
    LON, LAT = np.meshgrid(np.asarray(dst_lons, float), np.asarray(dst_lats, float))
    return _bilinear_sample(grid, src_lats, src_lons, LAT, LON)


# ──────────────────────────────────────────────────────────────
#  半拉格朗日平流
# ──────────────────────────────────────────────────────────────
def advect(field, lats, lons, u, v, days, substeps=4):
    """
    以流場 (u, v) 對 field 做 days 日的半拉格朗日回溯平流。

    Args:
        field : (ny, nx) 與 lats/lons 對齊的純量場
        u, v  : 同網格的東向／北向流速 (m/s)，NaN 代表無流場資訊
        days  : 預報時距（日）
        substeps : 分幾個次步回溯，抑制大位移時的軌跡誤差
    Returns:
        (advected_field, advected_mask)
        advected_mask 為 True 代表該格確實使用了流場資訊；
        無流場處原樣保留（持續性），不以邊界值外推。
    """
    field = np.asarray(field, dtype=float)
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    LON, LAT = np.meshgrid(lons, lats)

    has_flow = np.isfinite(u) & np.isfinite(v)
    if not has_flow.any() or days <= 0:
        return field.copy(), np.zeros_like(field, dtype=bool)

    u0 = np.where(has_flow, u, 0.0)
    v0 = np.where(has_flow, v, 0.0)

    dt = days * 86400.0 / max(1, substeps)
    lat_p = LAT.copy()
    lon_p = LON.copy()
    for _ in range(max(1, substeps)):
        # 於目前出發點取流速（回溯，故往上游走）
        uu = _bilinear_sample(u0, lats, lons, lat_p, lon_p)
        vv = _bilinear_sample(v0, lats, lons, lat_p, lon_p)
        uu = np.where(np.isfinite(uu), uu, 0.0)
        vv = np.where(np.isfinite(vv), vv, 0.0)
        dlat = vv * dt / 111_000.0
        coslat = np.cos(np.radians(np.clip(lat_p, -89.0, 89.0)))
        dlon = uu * dt / (111_000.0 * np.maximum(coslat, 1e-3))
        lat_p = np.clip(lat_p - dlat, lats.min(), lats.max())
        lon_p = lon_p - dlon

    adv = _bilinear_sample(field, lats, lons, lat_p, lon_p)
    out = np.where(np.isfinite(adv) & has_flow, adv, field)
    return out, has_flow & np.isfinite(adv)


# ──────────────────────────────────────────────────────────────
#  大尺度趨勢
# ──────────────────────────────────────────────────────────────
def _box_sum_1d(x, k, axis):
    """以累積和做 O(N) 的滑動窗和（窗長 k，置中，邊界截斷）。"""
    n = x.shape[axis]
    half = k // 2
    cs = np.cumsum(x, axis=axis)
    zero = np.zeros_like(np.take(cs, [0], axis=axis))
    cs = np.concatenate([zero, cs], axis=axis)          # cs[i] = sum(x[:i])
    idx = np.arange(n)
    hi = np.minimum(idx + half + 1, n)
    lo = np.maximum(idx - half, 0)
    return np.take(cs, hi, axis=axis) - np.take(cs, lo, axis=axis)


def box_mean(a, k):
    """
    k×k 箱形平均（NaN 安全）。以累積和實作，耗時與 k 無關，
    因此在 0.1° 原生網格（k≈63）上仍是毫秒級。k 強制為奇數且 >= 1。
    """
    a = np.asarray(a, dtype=float)
    k = max(1, int(k) | 1)
    if k == 1:
        return a.copy()
    valid = np.isfinite(a)
    f = np.where(valid, a, 0.0)

    s = _box_sum_1d(_box_sum_1d(f, k, 0), k, 1)
    c = _box_sum_1d(_box_sum_1d(valid.astype(float), k, 0), k, 1)
    with np.errstate(invalid='ignore', divide='ignore'):
        out = s / np.maximum(c, 1e-9)
    return np.where(c > 0, out, np.nan)


def large_scale_trend(stack, day_offsets, lats, scale_deg=None,
                      max_per_day=None):
    """
    由時間堆疊求「大尺度」逐格升降溫率 (°C/day)。

    先做逐格最小二乘斜率，再以 scale_deg 度的箱形平均濾掉雲隙與同化雜訊。
    箱形邊長以「度」指定，因此在 0.1° 原生網格與 0.2° 靜態網格上代表同一
    物理尺度。
    """
    scale_deg = config.FORECAST_TREND_SCALE_DEG if scale_deg is None else scale_deg
    max_per_day = config.FORECAST_MAX_TREND_PER_DAY if max_per_day is None else max_per_day

    stack = np.asarray(stack, dtype=float)
    if stack.shape[0] < 3:
        return None

    slope = linear_trend(stack, day_offsets)
    slope = np.clip(slope, -max_per_day, max_per_day)

    lats = np.asarray(lats, dtype=float)
    step = abs(float(lats[1] - lats[0])) if lats.size > 1 else 0.1
    k = int(round(scale_deg / max(step, 1e-6)))
    return box_mean(slope, k)


# ──────────────────────────────────────────────────────────────
#  SST 預報
# ──────────────────────────────────────────────────────────────
def forecast_sst(sst_stack, day_offsets, lats, lons, u=None, v=None,
                 leads=(1, 2, 3), alpha=None):
    """
    由最近數日 SST 分析場外推 1–N 日 SST 預報。

        SST(t+n) = [平流(SST₀, n)] + α × 大尺度趨勢 × n

    平流預設關閉（經回溯驗證為有害，見模組說明）。

    Args:
        sst_stack   : list/array of (ny, nx)，時間由舊到新，最後一筆為基準日 D0
        day_offsets : 對應的相對天數（最後一筆為 0，例 [-4,...,-1,0]）
        u, v        : 已重取樣到 SST 網格的表面流 (m/s)；僅在啟用平流時使用
        leads       : 預報時距清單（日）
    Returns:
        dict{lead: {'sst': array, 'advected_frac': float, 'trend_used': bool}}
    """
    alpha = config.FORECAST_TREND_ALPHA if alpha is None else alpha
    stack = np.asarray(sst_stack, dtype=float)
    base = stack[-1]
    valid = np.isfinite(base)

    slope = large_scale_trend(stack, day_offsets, lats)
    do_adv = (config.FORECAST_ADVECT_CURRENT and u is not None and v is not None)
    clip_tot = config.FORECAST_MAX_TOTAL_CHANGE

    out = {}
    for n in leads:
        if do_adv:
            fld, adv_mask = advect(base, lats, lons, u, v, n)
        else:
            fld, adv_mask = base.copy(), np.zeros(base.shape, dtype=bool)

        if slope is not None:
            delta = np.where(np.isfinite(slope), alpha * slope * n, 0.0)
            fld = fld + np.clip(delta, -clip_tot, clip_tot)

        # 預報值不得偏離基準場超過總變化上限，且不填補陸地／原始缺值
        fld = np.where(valid, np.clip(fld, base - clip_tot, base + clip_tot), np.nan)
        if config.FORECAST_SMOOTH_PASSES:
            fld = smooth3(fld, config.FORECAST_SMOOTH_PASSES)
            fld = np.where(valid, fld, np.nan)

        out[n] = {
            'sst': fld,
            'advected_frac': float(adv_mask[valid].mean()) if valid.any() else 0.0,
            'trend_used': slope is not None,
        }
    return out


def forecast_subsurface(stack, day_offsets, lats, leads=(1, 2, 3)):
    """
    次表層水溫預報：持續 + 強收縮的大尺度趨勢，不做平流
    （100 m 溫度場在 3 日內位移不顯著，平流只會引入誤差）。

    Args:
        stack : list of (ny, nx)，時間由舊到新，最後一筆為最新分析場
    Returns:
        dict{lead: array}
    """
    stack = np.asarray(stack, dtype=float)
    base = stack[-1]
    valid = np.isfinite(base)
    slope = large_scale_trend(stack, day_offsets, lats, max_per_day=0.15)

    out = {}
    for n in leads:
        if slope is None:
            out[n] = base.copy()
            continue
        delta = np.where(np.isfinite(slope), config.FORECAST_SUB_ALPHA * slope * n, 0.0)
        fld = base + delta
        out[n] = np.where(valid, np.clip(fld, base - 0.8, base + 0.8), np.nan)
    return out


# ──────────────────────────────────────────────────────────────
#  回溯驗證
# ──────────────────────────────────────────────────────────────
def verify_hindcast(sst_by_date, dates_sorted, lats, lons,
                    leads=None, trend_days=None, region=None, max_bases=20):
    """
    滾動回溯驗證：對每個可用的起報日 B，以截至 B 的資料做 n 日預報，
    與 B+n 的實測 SST 比對，並與純持續性法（直接用 B 當預報）對照。

    Args:
        sst_by_date  : dict{'YYYY-MM-DD': (ny,nx)}
        dates_sorted : 由舊到新的日期字串列表
        region       : (lat_min, lat_max, lon_min, lon_max)，None 代表全域
        max_bases    : 最多取最近幾個起報日（控制建置時間）
    Returns:
        {'region': [...], 'leads': {n: {...}}, 'n_base_dates': int} 或 None
    """
    from datetime import datetime

    leads = tuple(leads or config.FORECAST_VERIFY_LEADS)
    trend_days = trend_days or config.FORECAST_TREND_DAYS
    if len(dates_sorted) < trend_days + max(leads) + 1:
        return None

    def d(s):
        return datetime.strptime(s, '%Y-%m-%d')

    mask_region = None
    if region is not None:
        la_min, la_max, lo_min, lo_max = region
        LON, LAT = np.meshgrid(np.asarray(lons, float), np.asarray(lats, float))
        mask_region = (LAT >= la_min) & (LAT <= la_max) & (LON >= lo_min) & (LON <= lo_max)

    results = {}
    n_bases_used = 0
    for lead in leads:
        sq_fc, sq_pe = [], []
        err_fc = []
        bases = 0
        # 起報日必須有足夠的歷史（trend_days）與對應的驗證日
        for i in range(trend_days - 1, len(dates_sorted) - lead):
            base_date = dates_sorted[i]
            target = dates_sorted[i + lead]
            if (d(target) - d(base_date)).days != lead:
                continue                      # 資料有斷日，跳過
            hist = dates_sorted[max(0, i - trend_days + 1):i + 1]
            if len(hist) < 3:
                continue
            stack = [sst_by_date[x] for x in hist]
            offs = [(d(x) - d(base_date)).days for x in hist]
            fc = forecast_sst(stack, offs, lats, lons, leads=(lead,))[lead]['sst']

            obs = sst_by_date[target]
            persist = sst_by_date[base_date]
            m = np.isfinite(obs) & np.isfinite(fc) & np.isfinite(persist)
            if mask_region is not None:
                m = m & mask_region
            if m.sum() < 500:
                continue
            e = fc[m] - obs[m]
            sq_fc.append(np.square(e))
            sq_pe.append(np.square(persist[m] - obs[m]))
            err_fc.append(e)
            bases += 1
            if bases >= max_bases:
                break

        if not sq_fc:
            continue
        e_all = np.concatenate(err_fc)
        rmse_fc = float(np.sqrt(np.concatenate(sq_fc).mean()))
        rmse_pe = float(np.sqrt(np.concatenate(sq_pe).mean()))
        results[lead] = {
            'lead_days': int(lead),
            'n_base_dates': bases,
            'n_points': int(e_all.size),
            'rmse_c': round(rmse_fc, 3),
            'mae_c': round(float(np.abs(e_all).mean()), 3),
            'bias_c': round(float(e_all.mean()), 3),
            'rmse_persistence_c': round(rmse_pe, 3),
            'skill_vs_persistence_pct': round((1.0 - rmse_fc / rmse_pe) * 100.0, 1)
            if rmse_pe > 0 else 0.0,
        }
        n_bases_used = max(n_bases_used, bases)

    if not results:
        return None
    return {
        'region': list(region) if region else None,
        'trend_days': int(trend_days),
        'alpha': config.FORECAST_TREND_ALPHA,
        'scale_deg': config.FORECAST_TREND_SCALE_DEG,
        'n_base_dates': n_bases_used,
        'leads': results,
        'period': [dates_sorted[0], dates_sorted[-1]],
    }
