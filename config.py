# -*- coding: utf-8 -*-
"""
JMA海洋氣象資料桌面GUI系統 - 配置檔案
Configuration file for the JMA Ocean Weather Desktop GUI System
"""

import os
from pathlib import Path

# ============================================================================
# 基本目錄配置
# ============================================================================
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
HIMSST_DIR = DATA_DIR / "himsst"
NPRSUBT_DIR = DATA_DIR / "nprsubt"
NPRSUBC_DIR = DATA_DIR / "nprsubc"

# 確保目錄存在
for d in [DATA_DIR, HIMSST_DIR, NPRSUBT_DIR, NPRSUBC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================================
# JMA資料URL配置
# ============================================================================
JMA_BASE_URL = "https://www.data.jma.go.jp/goos/data/pub/JMA-product"
HIMSST_BASE_URL = f"{JMA_BASE_URL}/him_sst_pac_D"
NPRSUBT_BASE_URL = f"{JMA_BASE_URL}/npr_subt_jpn_D"
NPRSUBC_BASE_URL = f"{JMA_BASE_URL}/npr_subc_jpn_D"

# 下載資料筆數
DOWNLOAD_COUNT = 10

# ============================================================================
# HIMSST資料格式配置
# 格式：0.0-60.0N, 100.0E-180.0E, 0.1°x0.1°
# 601筆記錄：1筆header + 600筆data
# 每筆data：800個3位數值（0.1°C單位）
# ============================================================================
HIMSST_LAT_START = 59.95
HIMSST_LAT_END = 0.05
HIMSST_LON_START = 100.05
HIMSST_LON_END = 179.95
HIMSST_RESOLUTION = 0.1
HIMSST_ROWS = 600
HIMSST_COLS = 800
HIMSST_MISSING_VALUE = 999
HIMSST_ICE_VALUE = 888
HIMSST_UNIT_FACTOR = 0.1  # 資料為0.1°C單位

# ============================================================================
# NPRSUBT資料格式配置
# 格式：16.8N-56.2N, 113.545455E-163.454545E, 1/10°x1/11°
# 1585筆記錄：1筆header + 4個396筆記錄區塊（50m, 100m, 200m, 400m）
# 每筆data：550個4位數值（0.01°C單位）
# ============================================================================
NPRSUBT_LAT_START = 56.2
NPRSUBT_LAT_END = 16.8
NPRSUBT_LON_START = 113.545455
NPRSUBT_LON_END = 163.454545
NPRSUBT_LAT_RES = 0.1      # 1/10度
NPRSUBT_LON_RES = 1/11     # 1/11度
NPRSUBT_ROWS = 395         # 每個深度區塊的資料行數
NPRSUBT_COLS = 550
NPRSUBT_DEPTHS = [50, 100, 200, 400]  # 可用深度（公尺）
NPRSUBT_MISSING_VALUE = 9999
NPRSUBT_UNIT_FACTOR = 0.01  # 資料為0.01°C單位
NPRSUBT_BLOCK_SIZE = 396    # 包含深度資訊行的區塊大小

# ============================================================================
# NPRSUBC資料格式配置（表面海流）
# 格式：16.75N-56.25N, 113.5E-163.5E, 1/10°x1/11°
# 795筆記錄：1筆header + 2個397筆記錄區塊（東向分量/北向分量）
# 每筆data：551個4位數值（1 cm/sec單位）
# ============================================================================
NPRSUBC_LAT_START = 56.25
NPRSUBC_LAT_END = 16.75
NPRSUBC_LON_START = 113.5
NPRSUBC_LON_END = 163.5
NPRSUBC_LAT_RES = 0.1      # 1/10度
NPRSUBC_LON_RES = 1/11     # 1/11度
NPRSUBC_ROWS = 396
NPRSUBC_COLS = 551
NPRSUBC_BLOCK_SIZE = 397    # 包含方向資訊行的區塊大小
NPRSUBC_MISSING_VALUE = 9999
NPRSUBC_UNIT_FACTOR = 0.01  # 轉換為m/s

# ============================================================================
# 視覺化配置
# ============================================================================
# 初始顯示範圍
VIEW_LAT_MIN = 17.0
VIEW_LAT_MAX = 56.0
VIEW_LON_MIN = 114.0
VIEW_LON_MAX = 162.0

# 色彩映射
SST_CMAP = 'jet'
TEMP_CMAP = 'RdYlBu_r'
CURRENT_CMAP = 'plasma'

# 溫度範圍
SST_VMIN = 0
SST_VMAX = 32
SUBTEMP_VMIN = 0
SUBTEMP_VMAX = 25

# 等溫線間隔選項
ISOTHERM_INTERVALS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
DEFAULT_ISOTHERM_INTERVAL = 2

# 海流箭頭密度
CURRENT_ARROW_SKIP = 15

# ============================================================================
# GUI配置
# ============================================================================
WINDOW_TITLE = "西北太平洋秋刀魚漁場資訊服務系統"
ORGANIZATION_LABEL = "農業部水產試驗所 漁海況研究小組"
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 1000
DPI = 100

# ============================================================================
# 秋刀魚棲息地分析配置（ECDF）
# ============================================================================
SAURY_DATA_FILE = BASE_DIR / "Saury-csv.txt"
ECDF_PERCENTILES = {
    'very_low': 0.10,     # 10% - 非常低機率
    'low': 0.25,          # 25% - 低機率
    'moderate': 0.50,     # 50% - 中等機率
    'high': 0.75,         # 75% - 高機率
    'very_high': 0.90     # 90% - 非常高機率
}

# 顏色對應（用於秋刀魚棲息地分布圖）
HABITAT_COLORS = {
    'very_high': '#1a5f1a',   # 深綠色 - 非常適合
    'high': '#4ade4a',        # 亮綠色 - 適合
    'moderate': '#ffff00',    # 黃色 - 中等
    'low': '#ffa500',         # 橙色 - 較不適合
    'very_low': '#ff4444'     # 紅色 - 不適合
}

# ============================================================================
# 啟動自動更新設定
# ============================================================================
AUTO_UPDATE_ON_START = True   # 伺服器啟動時自動連 JMA 下載最新資料
AUTO_UPDATE_COUNT = 10        # 每種資料下載最新筆數
