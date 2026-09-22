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
MGDSST_DIR = DATA_DIR / "mgdsst"

# 確保目錄存在
for d in [DATA_DIR, HIMSST_DIR, NPRSUBT_DIR, NPRSUBC_DIR, MGDSST_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================================
# JMA資料URL配置
# 主站 www.data.jma.go.jp 偶有連線不穩，備援站 ds.data.jma.go.jp 內容相同。
# ============================================================================
JMA_BASE_URL = "https://www.data.jma.go.jp/goos/data/pub/JMA-product"
JMA_MIRROR_URL = "https://ds.data.jma.go.jp/gmd/goos/data/pub/JMA-product"
HIMSST_BASE_URL = f"{JMA_BASE_URL}/him_sst_pac_D"
NPRSUBT_BASE_URL = f"{JMA_BASE_URL}/npr_subt_jpn_D"
NPRSUBC_BASE_URL = f"{JMA_BASE_URL}/npr_subc_jpn_D"
MGDSST_BASE_URL = f"{JMA_BASE_URL}/mgd_sst_glb_D"

# 下載資料筆數
# 需 >= FORECAST_TREND_DAYS + FORECAST_LEAD_DAYS + 1；取 16 是為了讓每日的
# 滾動回溯驗證在 lead=3 時仍有 ~8 個起報日，統計不致於太雜訊。
DOWNLOAD_COUNT = 16

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
# MGDSST資料格式配置（全球每日海面水溫，HIMSST 遲到或破洞時的備援）
# 格式：89.875S-89.875N, 0.125E-359.875E, 0.25°x0.25°
# 721筆記錄：1筆header + 720筆data（由北向南）
# 每筆data：1440個3位數值（0.1°C單位）
# ============================================================================
MGDSST_LAT_START = 89.875
MGDSST_LAT_END = -89.875
MGDSST_LON_START = 0.125
MGDSST_LON_END = 359.875
MGDSST_RESOLUTION = 0.25
MGDSST_ROWS = 720
MGDSST_COLS = 1440
MGDSST_MISSING_VALUE = 999
MGDSST_ICE_VALUE = 888
MGDSST_UNIT_FACTOR = 0.1

# ============================================================================
# 次表層／海流產品的實際東界（JMA npr_*_jpn_D 為「日本近海」域）
# 以東無任何 JMA 次表層或海流產品，HSI 必須自動降階為 SST 單因子。
# ============================================================================
SUBSURFACE_EAST_LIMIT = 163.45   # NPRSUBT 東界
CURRENT_EAST_LIMIT = 163.5       # NPRSUBC 東界

# ============================================================================
# 視覺化配置
# ============================================================================
# 初始顯示範圍（秋刀魚漁場主軸：西北太平洋至換日線西側）
VIEW_LAT_MIN = 17.0
VIEW_LAT_MAX = 56.0
VIEW_LON_MIN = 114.0
VIEW_LON_MAX = 180.0

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

# 推薦漁場判定門檻（相對棲地適合度 HSI，前後端共用之單一權威設定）
# 僅 HSI 嚴格大於此值的網格才納入推薦漁場。
HOTSPOT_PROB_THRESHOLD = 0.5

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
AUTO_UPDATE_COUNT = 16        # 每種資料下載最新筆數

# ============================================================================
# 三日預報設定（JMA 未發布任何公開海況預報產品，本系統以分析場外推）
#
#   SST(t+n) = SST(t) + α × 大尺度趨勢 × n
#
# 方案是用 2026-07-02~09-20 共 81 日連續 HIMSST 分析場、以「前半調參／後半驗證」
# 的分割樣本法選出的（詳見 SAURY_ECDF_AND_FORECAST_DESIGN.md §5）。
# 測試期（2026-08-18~09-20，34 個起報日，未參與調參）相對持續性法的改進：
#   全域   +8.6% / +8.7% / +8.1%（lead 1/2/3）
#   漁場區 +8.8% / +9.7% / +9.8%
#
# 已驗證為「有害」而關閉的成分（保留程式碼與數據，避免日後重蹈）：
#   · 表面海流半拉格朗日平流：lead1 −24.4%、lead3 −14.6%
#     （HIMSST 為融合分析場，與 NPRSUBC 4DVAR 流場誤差獨立，平流會錯置鋒面）
#   · 預報場 3×3 平滑：lead1 −17.4%
#   · 未經大尺度化的逐格趨勢：lead3 −4.1%
# ============================================================================
FORECAST_LEAD_DAYS = 3              # 預報時距（日）
FORECAST_TREND_DAYS = 5             # 逐格線性趨勢的回溯日數
FORECAST_TREND_SCALE_DEG = 6.2      # 趨勢大尺度化的箱形平均邊長（度）
FORECAST_TREND_ALPHA = 0.60         # 趨勢收縮係數（分割樣本驗證最佳值）
FORECAST_MAX_TREND_PER_DAY = 0.30   # 逐格趨勢上限 (°C/day)，抑制雲隙雜訊放大
FORECAST_MAX_TOTAL_CHANGE = 1.50    # 預報期間 SST 總變化上限 (°C)
FORECAST_ADVECT_CURRENT = False     # 經驗證有害，預設關閉（見上方數據）
FORECAST_SMOOTH_PASSES = 0          # 經驗證有害，預設關閉
FORECAST_SUB_ALPHA = 0.35           # 次表層水溫趨勢收縮（100 m 變化慢，更保守）
FORECAST_VERIFY_LEADS = (1, 2, 3)   # 每日回溯驗證的時距
FORECAST_VERIFY_REGION = (35.0, 50.0, 140.0, 180.0)   # 驗證統計的漁場範圍

# 固定基準線：一次性的分割樣本驗證結果（2026-07-02~09-20 共 81 日連續分析場，
# 前 33 個起報日調參、後 34 個起報日驗證）。每日的滾動驗證樣本少、會有起伏，
# 這組數字提供穩定的對照，於網頁上與當日滾動驗證並列顯示。
FORECAST_BENCHMARK = {
    'period': ['2026-07-02', '2026-09-20'],
    'method': '分割樣本（前半調參／後半驗證），後半 34 個起報日',
    'region': [35.0, 50.0, 140.0, 162.0],
    'skill_pct': {'1': 8.8, '2': 9.7, '3': 9.8},
    'skill_pct_global': {'1': 8.6, '2': 8.7, '3': 8.1},
    'rmse_c': {'3': 0.584},
    'rmse_persistence_c': {'3': 0.647},
}

# 資料時效門檻：次表層資料落後 SST 超過此日數即降階為 SST 單因子 HSI
MAX_SUBSURFACE_LAG_DAYS = 3

# 靜態網站輸出設定
STATIC_HISTORY_DAYS = 8         # 保留的分析日（含當日速報）
STATIC_SST_STEP = 2             # SST 取樣間隔（×0.1° = 0.2°）
STATIC_SUB_STEP = 3             # 次表層取樣間隔
STATIC_CUR_STEP = 3             # 海流取樣間隔
