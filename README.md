# 西北太平洋秋刀魚漁場速預報系統（Leaflet 版 v3.0）

## 農業部水產試驗所 · 漁海況研究小組

### 系統概述

本系統整合日本氣象廳（JMA）GOOS 海洋資料，以互動式網頁地圖提供西北太平洋秋刀魚漁場的即時速預報。相較舊版桌面 GUI／整張靜態圖，本版改採 **Leaflet 互動地圖 + 後端透明疊圖** 架構：可自由平移縮放、圖層自由開關、滑鼠即時判讀水溫，並新增溫度鋒面偵測、漁場熱區自動萃取、一鍵速預報與報告輸出。

### 架構說明

後端（Flask）以 matplotlib 將各海洋欄位重取樣為 **Web Mercator 投影的透明 PNG**，land／無資料區為透明；前端 Leaflet 以海洋底圖（Esri Ocean Basemap）提供海岸線與地名，資料疊圖精準對齊。此設計免除 cartopy 安裝負擔，並讓地圖操作流暢。

```
瀏覽器 (Leaflet)  ── imageOverlay ──►  Flask API  ──►  matplotlib 渲染 (Web Mercator, 透明)
      ▲                                     │
      └──── GeoJSON 鋒面 / 熱區標記 / 即時取值 ┘
```

### 主要功能

1. **疊加圖層（可自由開關、調透明度）**
   - 海面水溫 SST（HIMSST 0.1°×0.1°）
   - 次表層水溫（NPRSUBT，50 / 100 / 200 / 400 m）
   - 表面海流向量（NPRSUBC）：可調**箭頭大小**（0.5–2×）與**空間解析度／密度**（疏／中／密／很密）
   - 秋刀魚棲息機率預測（ECDF）
   - 溫度鋒面偵測（SST 梯度等值線，門檻可調）
   - **等溫線圖層**：海面水溫與次表層水溫皆可獨立開關等溫線，並可設定間距（1/2/3/5°C），線上標註溫度值

2. **🎯 一鍵秋刀魚漁場速預報**
   - 自動抓取最新資料日期，計算棲息機率、疊合 SST 底圖與溫度鋒面
   - 自動萃取高機率**漁場熱區**（連通區域），標示中心座標、面積、平均機率與平均水溫
   - 熱區依「平均機率 × 面積」綜合評分排序，點擊即飛航定位

3. **溫度鋒面偵測**
   - 計算 SST 水平梯度（°C/km），以等值線描繪鋒面（秋刀魚常聚集於鋒面帶）
   - 門檻可於 0.02–0.15 °C/km 調整

4. **速預報報告輸出**
   - 一鍵下載美編 HTML 報告：KPI 摘要、ECDF 最適環境、推薦漁場熱區清單

5. **滑鼠即時判讀**：游標移動即顯示該點經緯度、SST、次表層水溫與流速

6. **JMA 資料更新**：網頁「更新 JMA 資料」按鈕即可背景下載最新資料，附進度顯示

### 系統需求

- Python 3.8+，Windows 10/11（或任何可執行 Python 的環境）
- 網路連線（更新 JMA 資料 / 載入 Leaflet 底圖）

### 安裝與啟動

```powershell
pip install -r requirements.txt
python app.py
```

或直接雙擊 `run_web.bat`（自動安裝套件、啟動伺服器並開啟瀏覽器）。

啟動後開啟 http://localhost:5000

> 註：本版已**不再需要 cartopy**，海岸線由 Leaflet 底圖提供。

### API 一覽

| 端點 | 說明 |
|------|------|
| `GET /api/dates` | 可用資料日期 |
| `GET /api/ecdf-summary` | ECDF 最適環境摘要 |
| `GET /api/overlay/<sst\|subtemp\|currents\|habitat>` | 各圖層透明疊圖（含邊界與圖例）；海流可帶 `arrow_size`／`skip` |
| `GET /api/fronts` | 溫度鋒面 GeoJSON（`threshold` 可調） |
| `GET /api/isotherms` | 等溫線 GeoJSON 與標註（`layer`／`interval`／`depth` 可調） |
| `GET /api/hotspots` | 漁場熱區清單（`prob` 門檻可調） |
| `GET /api/forecast` | 一鍵速預報（棲息機率＋熱區＋鋒面＋SST 底圖） |
| `GET /api/value` | 指定經緯度的即時數值 |
| `POST /api/update-data` · `GET /api/update-status` | 背景更新 JMA 資料與進度 |

### ECDF 棲息機率說明

系統以 `Saury-csv.txt` 歷史秋刀魚 CPUE 資料，對 **SST** 與 **100m 水溫** 建立經驗累積分布函數（ECDF），取核心範圍（25–75 百分位）為最適區間，結合當日海況計算每個網格點的聯合棲息機率（0–1），再萃取高機率連通海域作為推薦漁場。

> 註：次表層水溫／海流資料通常較 SST 落後約 1 日，系統會自動採用最接近可用日期之資料。

### 檔案結構

```
Saury0710/
├── app.py               # Flask 主程式（Leaflet 版 API）
├── config.py            # 系統配置
├── geo_utils.py         # Web Mercator 投影與網格重取樣
├── overlay_renderer.py  # 透明疊圖渲染（免 cartopy）
├── analysis.py          # 鋒面偵測 + 漁場熱區萃取
├── data_parser.py       # JMA 資料解析
├── data_downloader.py   # JMA 資料下載
├── ecdf_analyzer.py     # 秋刀魚棲息地 ECDF 分析
├── Saury-csv.txt        # 秋刀魚漁獲歷史資料
├── requirements.txt
├── run_web.bat          # 一鍵啟動
├── templates/index.html # 前端頁面
├── static/              # css / js / images
└── data/                # himsst / nprsubt / nprsubc 資料
```

### GitHub Pages 靜態版（純前端，免伺服器）

`docs/` 為**純前端版本**，所有運算（疊圖上色、ECDF 棲息機率、鋒面、等溫線、熱區、滑鼠取值）改由瀏覽器端 JavaScript 執行（Canvas + d3-contour），資料由 `build_static.py` 預先轉成精簡靜態檔（`docs/data/*.json`，Int16 量化）。可直接掛在 GitHub Pages，無需 Python 伺服器。

啟用步驟：
1. 執行 `python build_static.py` 產生最新靜態資料（已內建最近 8 日）
2. 雙擊 `deploy_pages.bat` 推送到 GitHub
3. GitHub repo → Settings → Pages → Source: Deploy from a branch → Branch `main`、Folder `/docs` → Save
4. 約 1 分鐘後開啟：`https://petercttseng-ux.github.io/<repo 名稱>/`

> 註：Pages 網址由 repo 名稱決定。目前 repo 名為 `saury-forecast`，網址即 `https://petercttseng-ux.github.io/saury-forecast/`。前端使用相對路徑，改 repo 名亦可正常運作。
> 靜態版為資料快照（預設最近 8 日）；要更新資料，重跑 `build_static.py` 後再 `deploy_pages.bat` 即可（亦可日後加 GitHub Action 自動化）。

#### 自動更新（GitHub Action）

`.github/workflows/update-data.yml` 會每日（台灣時間 04:00）自動下載最新 JMA 資料、重建 `docs/data` 並提交，GitHub Pages 隨即更新；亦可在 repo 的 **Actions** 分頁手動觸發（Run workflow）。

一次性設定：repo → Settings → Actions → General → Workflow permissions → 選 **Read and write permissions** → Save（否則 Action 無法推送）。

### 資料來源

- HIMSST：https://www.data.jma.go.jp