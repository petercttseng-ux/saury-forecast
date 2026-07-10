# -*- coding: utf-8 -*-
"""
build_static.py — 將 JMA 資料預處理成 GitHub Pages 用的精簡靜態資產。
在專案根目錄執行：  python build_static.py
輸出到 docs/data/：manifest.json / ecdf.json / <YYYY-MM-DD>.json
"""
import os, json, base64, glob, re, datetime
import numpy as np
import config
from data_parser import HIMSSTParser, NPRSUBTParser, NPRSUBCParser
from ecdf_analyzer import SauryECDFAnalyzer

OUT_DIR = os.path.join(os.path.dirname(__file__), 'docs', 'data')
N_DATES = 8
SST_STEP, SUB_STEP, CUR_STEP = 2, 2, 2
NODATA = -32768
SCALE = 100.0
LATN, LATS = config.VIEW_LAT_MAX, config.VIEW_LAT_MIN
LONW, LONE = config.VIEW_LON_MIN, config.VIEW_LON_MAX


def _orient(arr, lats, lons):
    lats = np.asarray(lats, float); lons = np.asarray(lons, float)
    if lats[0] < lats[-1]:
        lats = lats[::-1]; arr = arr[::-1, :]
    if lons[0] > lons[-1]:
        lons = lons[::-1]; arr = arr[:, ::-1]
    return arr, lats, lons


def enc_grid(arr, lats, lons, step):
    arr, lats, lons = _orient(np.asarray(arr, float), lats, lons)
    latm = (lats <= LATN + 1e-6) & (lats >= LATS - 1e-6)
    lonm = (lons >= LONW - 1e-6) & (lons <= LONE + 1e-6)
    arr = arr[np.ix_(latm, lonm)]
    la = lats[latm]; lo = lons[lonm]
    arr = arr[::step, ::step]; la = la[::step]; lo = lo[::step]
    q = np.where(np.isfinite(arr), np.round(arr * SCALE), NODATA)
    q = np.clip(q, NODATA, 32767).astype('<i2')
    return {'ny': int(arr.shape[0]), 'nx': int(arr.shape[1]),
            'latN': round(float(la[0]), 5), 'latS': round(float(la[-1]), 5),
            'lonW': round(float(lo[0]), 5), 'lonE': round(float(lo[-1]), 5),
            'scale': SCALE, 'nodata': NODATA,
            'b64': base64.b64encode(q.tobytes()).decode('ascii')}


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


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    himp, subp, curp = HIMSSTParser(), NPRSUBTParser(), NPRSUBCParser()
    him_idx = _index(str(config.HIMSST_DIR))
    sub_idx = _index(str(config.NPRSUBT_DIR))
    cur_idx = _index(str(config.NPRSUBC_DIR))
    dates = sorted(him_idx.keys(), reverse=True)[:N_DATES]
    print('dates:', dates)

    def nearest_key(idx, d):
        ks = sorted(idx.keys()); le = [k for k in ks if k <= d]
        return le[-1] if le else (ks[0] if ks else None)

    manifest = {'dates': [],
                'view': {'latN': LATN, 'latS': LATS, 'lonW': LONW, 'lonE': LONE},
                'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}

    for d in dates:
        sst = himp.parse_file(him_idx[d])
        subd = nearest_key(sub_idx, d); sub = subp.parse_file(sub_idx[subd]) if subd else None
        curd = nearest_key(cur_idx, d); cur = curp.parse_file(cur_idx[curd]) if curd else None
        out = {'date': d, 'sst': enc_grid(sst['sst'], sst['lats'], sst['lons'], SST_STEP)}
        if sub is not None:
            out['sub'] = {dep: enc_grid(sub['temp_' + dep], sub['lats'], sub['lons'], SUB_STEP)
                          for dep in ['50m', '100m', '200m', '400m']}
            out['subDate'] = subd
        if cur is not None:
            out['cur'] = {'u': enc_grid(cur['u'], cur['lats'], cur['lons'], CUR_STEP),
                          'v': enc_grid(cur['v'], cur['lats'], cur['lons'], CUR_STEP)}
            out['curDate'] = curd
        path = os.path.join(OUT_DIR, d + '.json')
        json.dump(out, open(path, 'w'), separators=(',', ':'))
        print('  %s: %d KB' % (d, os.path.getsize(path) // 1024))
        manifest['dates'].append(d)

    an = SauryECDFAnalyzer()
    if an.load_data():
        an.analyze_sst(); an.analyze_100m_temp()

        def pack(res, n=160):
            sv = res['sorted_values']; cdf = res['cdf']
            idx = np.linspace(0, len(sv) - 1, min(n, len(sv))).astype(int)
            return {'v': [round(float(x), 3) for x in sv[idx]],
                    'cdf': [round(float(x), 4) for x in cdf[idx]],
                    'min': round(float(res['min']), 2), 'max': round(float(res['max']), 2),
                    'mean': round(float(res['mean']), 2),
                    'p25': round(float(res['percentiles']['low']), 2),
                    'p75': round(float(res['percentiles']['high']), 2)}

        ecdf = {'sst': pack(an.ecdf_results['sst']),
                'temp100': pack(an.ecdf_results['100m_temp']),
                'summary': an.get_summary()}
        json.dump(ecdf, open(os.path.join(OUT_DIR, 'ecdf.json'), 'w'), separators=(',', ':'))
        print('  ecdf.json done')

    json.dump(manifest, open(os.path.join(OUT_DIR, 'manifest.json'), 'w'),
              ensure_ascii=False, separators=(',', ':'))
    total = sum(os.path.getsize(os.path.join(OUT_DIR, f)) for f in os.listdir(OUT_DIR))
    print('TOTAL docs/data = %d KB' % (total // 1024))


if __name__ == '__main__':
    main()
