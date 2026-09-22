# -*- coding: utf-8 -*-
"""
build_static.py — 把 JMA 分析場轉成 GitHub Pages 用的精簡靜態資產。

產出（docs/data/）
  manifest.json      視圖範圍、分析日與預報日清單、資料時效、預報方法與回溯驗證數據
  ecdf.json          CPUE 加權 ECDF 曲線與環境窗
  <YYYY-MM-DD>.json  每日網格（Int16 量化 + base64）；kind = analysis | forecast

與舊版的差異
  1. 經度範圍擴至 180°E（HIMSST 原生即 100–180°E）。
  2. 新增當日速報之後的 +1~+3 日預報場（forecast.py）。
  3. 逐格記錄 HSI 可用的模式組成：163.45°E 以東無 JMA 次表層產品，
     前端據此自動降階為 SST 單因子，而非以邊界值外推。
  4. HIMSST 缺漏時以 MGDSST（全球 0.25°）補值，並在 manifest 標示補值比例。
  5. 每次建置會清掉不在 manifest 內的舊日期檔，避免 repo 無限膨脹。

在專案根目錄執行：python build_static.py
"""

import os
import re
import glob
import json
import base64
import datetime

import numpy as np

import config
import forecast as F
from data_parser import HIMSSTParser, NPRSUBTParser, NPRSUBCParser, MGDSSTParser
from ecdf_analyzer import SauryECDFAnalyzer

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'data')

N_DATES = config.STATIC_HISTORY_DAYS
SST_STEP = config.STATIC_SST_STEP
SUB_STEP = config.STATIC_SUB_STEP
CUR_STEP = config.STATIC_CUR_STEP
LEADS = tuple(range(1, config.FORECAST_LEAD_DAYS + 1))

NODATA = -32768
SCALE = 100.0
LATN, LATS = config.VIEW_LAT_MAX, config.VIEW_LAT_MIN
LONW, LONE = config.VIEW_LON_MIN, config.VIEW_LON_MAX


# ──────────────────────────────────────────────────────────────
#  網格編碼
# ──────────────────────────────────────────────────────────────
def _orient(arr, lats, lons):
    """統一為 row 0 = 最北、col 0 = 最西。"""
    lats = np.asarray(lats, float)
    lons = np.asarray(lons, float)
    if lats[0] < lats[-1]:
        lats = lats[::-1]
        arr = arr[::-1, :]
    if lons[0] > lons[-1]:
        lons = lons[::-1]
        arr = arr[:, ::-1]
    return arr, lats, lons


def clip_to_view(arr, lats, lons, step):
    """裁到顯示範圍並降取樣；回傳 (arr, lats, lons)。"""
    arr, lats, lons = _orient(np.asarray(arr, float), lats, lons)
    latm = (lats <= LATN + 1e-6) & (lats >= LATS - 1e-6)
    lonm = (lons >= LONW - 1e-6) & (lons <= LONE + 1e-6)
    arr = arr[np.ix_(latm, lonm)]
    la, lo = lats[latm], lons[lonm]
    return arr[::step, ::step], la[::step], lo[::step]


def enc_grid(arr, lats, lons, step=1, already_clipped=False):
    """Int16 量化 + base64 編碼。"""
    if already_clipped:
        arr = np.asarray(arr, float)
        la, lo = np.asarray(lats, float), np.asarray(lons, float)
    else:
        arr, la, lo = clip_to_view(arr, lats, lons, step)
    q = np.where(np.isfinite(arr), np.round(arr * SCALE), NODATA)
    q = np.clip(q, NODATA, 32767).astype('<i2')
    return {
        'ny': int(arr.shape[0]), 'nx': int(arr.shape[1]),
        'latN': round(float(la[0]), 5), 'latS': round(float(la[-1]), 5),
        'lonW': round(float(lo[0]), 5), 'lonE': round(float(lo[-1]), 5),
        'scale': SCALE, 'nodata': NODATA,
        'b64': base64.b64encode(q.tobytes()).decode('ascii'),
    }


# ──────────────────────────────────────────────────────────────
#  檔案索引
# ──────────────────────────────────────────────────────────────
def _date_of(fp):
    m = re.search(r'D(\d{8})', os.path.basename(fp))
    return m.group(1) if m else None


def _index(folder):
    out = {}
    for fp in glob.glob(os.path.join(folder, '*.txt')):
        d = _date_of(fp)
        if d:
            out['%s-%s-%s' % (d[:4], d[4:6], d[6:8])] = fp
    return out


def _nearest_le(idx, d):
    """取不晚於 d 的最近日期鍵。"""
    ks = sorted(k for k in idx if k <= d)
    return ks[-1] if ks else None


def _shift(date_str, days):
    d = datetime.datetime.strptime(date_str, '%Y-%m-%d') + datetime.timedelta(days=days)
    return d.strftime('%Y-%m-%d')


def _daydiff(a, b):
    fmt = '%Y-%m-%d'
    return abs((datetime.datetime.strptime(a, fmt) - datetime.datetime.strptime(b, fmt)).days)


# ──────────────────────────────────────────────────────────────
#  主流程
# ──────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    himp, subp, curp, mgdp = HIMSSTParser(), NPRSUBTParser(), NPRSUBCParser(), MGDSSTParser()

    him_idx = _index(str(config.HIMSST_DIR))
    sub_idx = _index(str(config.NPRSUBT_DIR))
    cur_idx = _index(str(config.NPRSUBC_DIR))
    mgd_idx = _index(str(config.MGDSST_DIR))

    if not him_idx:
        raise SystemExit('找不到任何 HIMSST 資料，請先執行 python data_downloader.py')

    # 趨勢需要 FORECAST_TREND_DAYS 日；驗證再多取一些
    want = max(N_DATES, config.FORECAST_TREND_DAYS + max(LEADS) + 4)
    all_dates = sorted(him_idx.keys(), reverse=True)[:want]
    all_dates.sort()
    show_dates = all_dates[-N_DATES:]
    base_date = all_dates[-1]
    print('分析日（載入）:', all_dates[0], '~', all_dates[-1], '共', len(all_dates), '日')
    print('基準日（當日速報）:', base_date)

    # ── 讀 SST（HIMSST 為主，MGDSST 補洞）────────────────────
    sst_full, sst_lats, sst_lons = {}, None, None
    mgd_fill_frac = {}
    for d in all_dates:
        rec = himp.parse_file(him_idx[d])
        if rec is None:
            continue
        a = rec['sst']
        sst_lats, sst_lons = rec['lats'], rec['lons']

        # 以 MGDSST 補 HIMSST 的缺值（僅補「海上有值但 HIMSST 缺」之處）
        if d in mgd_idx:
            mg = mgdp.parse_file(mgd_idx[d])
            if mg is not None:
                mgr = F.regrid(mg['sst'], mg['lats'], mg['lons'], sst_lats, sst_lons)
                hole = (~np.isfinite(a)) & np.isfinite(mgr)
                if hole.any():
                    a = np.where(hole, mgr, a)
                    mgd_fill_frac[d] = round(float(hole.mean()), 5)
        sst_full[d] = a

    if base_date not in sst_full:
        raise SystemExit('基準日 SST 解析失敗：' + base_date)

    # ── 裁到顯示範圍（預報在裁切後的網格上算，省時且與輸出一致）──
    sst_view = {}
    v_lats = v_lons = None
    for d, a in sst_full.items():
        arr, la, lo = clip_to_view(a, sst_lats, sst_lons, SST_STEP)
        sst_view[d] = arr
        v_lats, v_lons = la, lo
    print('顯示網格: %d×%d  (%.2f~%.2f°N, %.2f~%.2f°E)'
          % (len(v_lats), len(v_lons), v_lats[-1], v_lats[0], v_lons[0], v_lons[-1]))

    # ── 次表層與海流 ─────────────────────────────────────────
    # 需要兩組日期：(a) 每個顯示日各自對應的最新一筆，(b) 預報趨勢所需的時間序列。
    sub_key = _nearest_le(sub_idx, base_date)
    cur_key = _nearest_le(cur_idx, base_date)

    sub_need = {k for k in (_nearest_le(sub_idx, d) for d in show_dates) if k}
    sub_need |= set(sorted([k for k in sub_idx if k <= base_date])[-config.FORECAST_TREND_DAYS:])
    cur_need = {k for k in (_nearest_le(cur_idx, d) for d in show_dates) if k}

    sub_view, sub_lats, sub_lons = {}, None, None
    for d in sorted(sub_need):
        rec = subp.parse_file(sub_idx[d])
        if rec is None:
            continue
        stacked = {}
        for dep in ('50m', '100m', '200m', '400m'):
            arr, la, lo = clip_to_view(rec['temp_' + dep], rec['lats'], rec['lons'], SUB_STEP)
            stacked[dep] = arr
            sub_lats, sub_lons = la, lo
        sub_view[d] = stacked

    cur_view, cur_lats, cur_lons = {}, None, None
    for d in sorted(cur_need):
        rec = curp.parse_file(cur_idx[d])
        if rec is None:
            continue
        u, la, lo = clip_to_view(rec['u'], rec['lats'], rec['lons'], CUR_STEP)
        v, _, _ = clip_to_view(rec['v'], rec['lats'], rec['lons'], CUR_STEP)
        cur_view[d] = (u, v)
        cur_lats, cur_lons = la, lo

    # ── 三日 SST 預報 ────────────────────────────────────────
    hist = [d for d in all_dates if d in sst_view][-config.FORECAST_TREND_DAYS:]
    stack = [sst_view[d] for d in hist]
    offs = [-_daydiff(d, base_date) for d in hist]
    print('預報趨勢視窗:', hist)
    fc = F.forecast_sst(stack, offs, v_lats, v_lons, leads=LEADS)

    # 次表層預報（僅用不晚於基準日的序列）
    sub_fc = {}
    sub_hist = sorted([d for d in sub_view if d <= base_date])[-config.FORECAST_TREND_DAYS:]
    if sub_hist:
        sub_base = sub_hist[-1]
        for dep in ('50m', '100m', '200m', '400m'):
            st = [sub_view[d][dep] for d in sub_hist]
            o = [-_daydiff(d, sub_base) for d in sub_hist]
            sub_fc[dep] = F.forecast_subsurface(st, o, sub_lats, leads=LEADS)

    # ── 回溯驗證（每日重算，數字直接上網頁）──────────────────
    verify = F.verify_hindcast(sst_view, sorted(sst_view), v_lats, v_lons,
                               region=config.FORECAST_VERIFY_REGION, max_bases=20)
    verify_global = F.verify_hindcast(sst_view, sorted(sst_view), v_lats, v_lons,
                                      region=None, max_bases=20)
    if verify:
        print('回溯驗證（漁場區）:',
              {k: v['skill_vs_persistence_pct'] for k, v in verify['leads'].items()})

    # ── 輸出每日檔 ───────────────────────────────────────────
    written = []

    def write_day(date, sst_arr, kind, lead=0, sub_block=None, cur_block=None,
                  sub_date=None, cur_date=None):
        out = {
            'date': date,
            'kind': kind,
            'lead': lead,
            'sst': enc_grid(sst_arr, v_lats, v_lons, already_clipped=True),
        }
        if sub_block is not None:
            out['sub'] = {dep: enc_grid(sub_block[dep], sub_lats, sub_lons, already_clipped=True)
                          for dep in sub_block}
            out['subDate'] = sub_date
        if cur_block is not None:
            out['cur'] = {'u': enc_grid(cur_block[0], cur_lats, cur_lons, already_clipped=True),
                          'v': enc_grid(cur_block[1], cur_lats, cur_lons, already_clipped=True)}
            out['curDate'] = cur_date
        if kind == 'forecast':
            out['baseDate'] = base_date
        if date in mgd_fill_frac:
            out['mgdFillFrac'] = mgd_fill_frac[date]
        path = os.path.join(OUT_DIR, date + '.json')
        with open(path, 'w') as f:
            json.dump(out, f, separators=(',', ':'))
        written.append(date + '.json')
        print('  %-12s %-9s %5d KB' % (date, kind, os.path.getsize(path) // 1024))

    # 分析日：每日各自對應不晚於該日的最新次表層／海流分析場
    for d in show_dates:
        if d not in sst_view:
            continue
        sd = _nearest_le(sub_idx, d)
        cd = _nearest_le(cur_idx, d)
        write_day(d, sst_view[d], 'analysis',
                  sub_block=sub_view.get(sd), cur_block=cur_view.get(cd),
                  sub_date=sd if sd in sub_view else None,
                  cur_date=cd if cd in cur_view else None)

    # 預報日：海流採持續場（沿用基準日分析場）
    cur_base_block = cur_view.get(cur_key)
    forecast_dates = []
    for n in LEADS:
        fdate = _shift(base_date, n)
        sblock = {dep: sub_fc[dep][n] for dep in sub_fc} if sub_fc else None
        write_day(fdate, fc[n]['sst'], 'forecast', lead=n,
                  sub_block=sblock, cur_block=cur_base_block,
                  sub_date=sub_hist[-1] if sub_hist else None,
                  cur_date=cur_key if cur_base_block else None)
        forecast_dates.append({'date': fdate, 'lead': n})

    # ── ECDF ────────────────────────────────────────────────
    an = SauryECDFAnalyzer()
    if an.load_data():
        an.analyze_all()
        curves = an.get_curve_data()
        ecdf = {'sst': curves['sst'], 'temp100': curves['100m_temp'],
                'parameters': curves, 'summary': an.get_summary()}
        with open(os.path.join(OUT_DIR, 'ecdf.json'), 'w') as f:
            json.dump(ecdf, f, separators=(',', ':'))
        written.append('ecdf.json')
        print('  ecdf.json done')

    # ── manifest ────────────────────────────────────────────
    def _verify_payload(v):
        if not v:
            return None
        return {'region': v['region'], 'period': v['period'],
                'nBaseDates': v['n_base_dates'],
                'leads': {str(k): x for k, x in v['leads'].items()}}

    manifest = {
        'dates': [d for d in show_dates if d in sst_view],
        'baseDate': base_date,
        'forecasts': forecast_dates,
        'view': {'latN': LATN, 'latS': LATS, 'lonW': LONW, 'lonE': LONE},
        'subsurfaceEastLimit': config.SUBSURFACE_EAST_LIMIT,
        'currentEastLimit': config.CURRENT_EAST_LIMIT,
        'maxSubsurfaceLagDays': config.MAX_SUBSURFACE_LAG_DAYS,
        'hotspotThreshold': config.HOTSPOT_PROB_THRESHOLD,
        'sources': {
            'sst': {'product': 'HIMSST (him_sst_pac_D)', 'latest': base_date,
                    'domain': '0–60°N, 100–180°E, 0.1°'},
            'subsurface': {'product': 'NPR-4DVAR (npr_subt_jpn_D)', 'latest': sub_key,
                           'domain': '16.8–56.2°N, 113.5–163.45°E, 0.1°×1/11°'},
            'current': {'product': 'NPR-4DVAR (npr_subc_jpn_D)', 'latest': cur_key,
                        'domain': '16.75–56.25°N, 113.5–163.5°E, 0.1°×1/11°'},
            'sstBackup': {'product': 'MGDSST (mgd_sst_glb_D)',
                          'latest': max(mgd_idx) if mgd_idx else None,
                          'domain': '全球 0.25°', 'usedForFill': bool(mgd_fill_frac)},
        },
        'forecastMethod': {
            'formula': 'SST(t+n) = SST(t) + α × 大尺度趨勢 × n',
            'trendDays': config.FORECAST_TREND_DAYS,
            'scaleDeg': config.FORECAST_TREND_SCALE_DEG,
            'alpha': config.FORECAST_TREND_ALPHA,
            'advection': bool(config.FORECAST_ADVECT_CURRENT),
            'subsurface': '持續場 + 收縮趨勢（α=%.2f），不做平流' % config.FORECAST_SUB_ALPHA,
            'currents': '持續場（沿用基準日分析場）',
            'note': 'JMA 未發布公開海況預報產品，本預報由 JMA 分析場外推，非 JMA 官方預報。',
        },
        'verification': _verify_payload(verify),
        'verificationGlobal': _verify_payload(verify_global),
        'benchmark': config.FORECAST_BENCHMARK,
        'generated': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    }
    with open(os.path.join(OUT_DIR, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(',', ':'))
    written.append('manifest.json')

    # ── 清掉不在本次輸出內的舊日期檔 ─────────────────────────
    keep = set(written)
    removed = 0
    for fn in os.listdir(OUT_DIR):
        if fn.endswith('.json') and fn not in keep:
            os.remove(os.path.join(OUT_DIR, fn))
            removed += 1
    if removed:
        print('  清除舊資料檔 %d 個' % removed)

    total = sum(os.path.getsize(os.path.join(OUT_DIR, f)) for f in os.listdir(OUT_DIR))
    print('TOTAL docs/data = %d KB (%d 檔)' % (total // 1024, len(os.listdir(OUT_DIR))))


if __name__ == '__main__':
    main()
