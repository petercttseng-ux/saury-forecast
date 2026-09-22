# -*- coding: utf-8 -*-
"""
grid_io.py — JMA NEAR-GOOS 固定欄寬文字網格的向量化解碼工具。

原本 data_parser.py 以 Python 迴圈逐格 int()，一個 HIMSST 檔就是 48 萬次呼叫；
每日要讀 12 天 × 4 種產品時會明顯拖慢 GitHub Actions。這裡以 numpy 一次
解出整個區塊，速度約快兩個數量級，數值結果與原解析器一致。

欄位為右靠、可含負號與前置空白（例：' 050'、'-050'、'9999'）。
"""

import numpy as np


def decode_fixed_width(lines, ncols, width, missing=None, fill=np.nan,
                       factor=1.0, special=None):
    """
    將固定欄寬的數字文字列解碼為 float 陣列。

    Args:
        lines   : list[str]，每列至少 ncols*width 個字元（不足補空白）
        ncols   : 每列欄位數
        width   : 每欄字元數
        missing : 缺值碼（整數）；命中者填 fill
        fill    : 缺值填入值
        factor  : 單位換算係數（例 0.1 代表 0.1°C）
        special : dict{整數碼: 取代值(物理單位)}，例 {888: -2.0} 代表海冰

    Returns:
        (len(lines), ncols) 的 float64 陣列
    """
    n = len(lines)
    need = ncols * width
    buf = bytearray(n * need)
    for i, ln in enumerate(lines):
        b = ln.encode('ascii', 'replace')
        if len(b) >= need:
            buf[i * need:(i + 1) * need] = b[:need]
        else:
            buf[i * need:i * need + len(b)] = b
            # 不足處補 '9'，使其落在缺值判定之外亦不致誤解為 0
            buf[i * need + len(b):(i + 1) * need] = b'9' * (need - len(b))

    a = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(n, ncols, width)

    # 負號偵測（欄內任一位置出現 '-'）
    neg = (a == 45).any(axis=2)
    # '-' 與 ' ' 都視為 '0'，其餘保持原樣
    a = np.where((a == 45) | (a == 32), 48, a)

    vals = np.zeros((n, ncols), dtype=np.int32)
    for k in range(width):
        digit = a[:, :, k].astype(np.int32) - 48
        np.clip(digit, 0, 9, out=digit)
        vals = vals * 10 + digit

    out = vals.astype(np.float64)
    if special:
        for code, repl in special.items():
            out = np.where(vals == code, repl / factor, out)
    if missing is not None:
        out = np.where(vals == missing, np.nan, out)

    out = out * factor
    out = np.where(neg & np.isfinite(out), -out, out)
    if fill is not np.nan:
        out = np.where(np.isnan(out), fill, out)
    return out


def read_records(filepath, expect_min_lines=None):
    """讀檔並回傳去掉換行的列表；行數不足時回傳 None。"""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.read().split('\n')
    while lines and lines[-1] == '':
        lines.pop()
    if expect_min_lines is not None and len(lines) < expect_min_lines:
        return None
    return lines


def parse_header_date(line):
    """JMA header 為年月日各 4 位（例 '2026   9  11'）。"""
    from datetime import datetime
    s = line.rstrip('\n')
    return datetime(int(s[0:4]), int(s[4:8]), int(s[8:12]))
