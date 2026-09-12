# 西北太平洋秋刀魚漁場速預報系統

## 農業部水產試驗所 · 漁海況研究小組

整合日本氣象廳（JMA）GOOS 海洋資料，以互動式網頁地圖提供西北太平洋秋刀魚漁場速報：海面水溫、次表層水溫、表面海流、相對棲地適合度（HSI）、溫度鋒面、等溫線、漁場熱區與一鍵預報。

本專案提供兩種版本：

- **Flask 伺服器版**（`app.py` 等）：後端以 matplotlib 即時渲染 Web Mercator 透明疊圖，本機執行。
- **純前端靜態版**（`docs/`）：所有運算改由瀏覽器 JavaScript 執行（Canvas + d3-contour），可直接掛在 GitHub Pages，免伺服器。

---

## A. Flask 伺服器版（本機）

### 啟動

```powershell
pip install -r requirements.txt
python app.py
```

或直接雙擊 `run_web.bat`（自動安裝套件、啟動伺服器並開啟瀏覽器），然後開啟 http://localhost:5000

> 本版不需要 cartopy，海岸線由前端 Leaflet 底圖提供。

### 主要功能

1. 疊加圖層（可自由開關、調透明度）
   - 海面水溫 SST（HIMSST 0.1°×0.1°）
   - 次表層水溫（NPRSUBT，50 / 100 / 200 / 400 m）
   - 表面海流向量（NPRSUBC）：可調箭頭大小與空間解析度（密度）
   - 秋刀魚相對棲地適合度 HSI（CPUE 加權 ECDF）
   - 七項環境參數的一般／CPUE 加權 ECDF 互動比較曲線
   - 溫度鋒面偵測（SST 梯度等值線，門檻可調）
   - 等溫線圖層：海面水溫與次表層水溫皆可獨立開關，並可設定間距（1/2/3/5°C），線上標註溫度
2. 一鍵秋刀魚漁場速報：自動計算相對 HSI、疊合 SST 與鋒面，萃取高適合度漁場熱區並排序
3. 速預報報告輸出（HTML）
4. 滑鼠即時判讀經緯度、SST、次表層水溫、流速
5. JMA 資料更新按鈕（背景下載＋進度）

### API 一覽

| 端點 | 說明 |
|------|------|
| `GET /api/dates` | 可用資料日期 |
| `GET /api/data-status` | 各來源實際日期、時間差與新鮮度 |
| `GET /api/ecdf-summary` | ECDF 最適環境摘要 |
| `GET /api/overlay/<sst\|subtemp\|currents\|habitat>` | 各圖層透明疊圖；海流可帶 `arrow_size`／`skip` |
| `GET /api/fronts` | 溫度鋒面 GeoJSON（`threshold` 可調） |
| `GET /api/isotherms` | 等溫線 GeoJSON 與標註（`layer`／`interval`／`depth` 可調） |
| `GET /api/hotspots` | 漁場熱區清單（`prob` 門檻可調，預設 0.5，採嚴格大於） |
| `GET /api/forecast` | 一鍵速預報 |
| `GET /api/value` | 指定經緯度的即時數值 |
| `POST /api/update-data` · `GET /api/update-status` | 背景更新 JMA 資料與進度 |

---

## B. 純前端靜態版（GitHub Pages）

`docs/` 內含純前端版本，運算全部在瀏覽器執行（Canvas 疊圖上色、d3-contour 等溫線/鋒面、JS 版 CPUE 加權 ECDF、相對 HSI 與熱區）。資料由 `build_static.py` 預先轉成精簡靜態檔（`docs/data/*.json`，Int16 量化，每日約 1MB）。

### 部署步驟

1. `python data_downloader.py --count 10` 下載各 JMA 產品最近 10 日資料
2. `python build_static.py` 產生最新靜態資料（預設最近 8 日）
3. 雙擊 `deploy_pages.bat` 推送到 GitHub
4. GitHub repo → Settings → Pages → Source：Deploy from a branch → Branch `main`、Folder `/docs` → Save
5. 約 1 分鐘後開啟：`https://petercttseng-ux.github.io/saury-forecast/`

> Pages 網址由 repo 名稱決定；前端使用相對路徑，改 repo 名亦可正常運作。

### 自動更新（GitHub Action）

`.github/workflows/update-data.yml` 每日（台灣時間 04:00）自動下載最新 JMA 資料、重建 `docs/data` 並提交，Pages 隨即更新；亦可在 Actions 分頁手動 Run workflow。

一次性設定：repo → Settings → Actions → General → Workflow permissions → 選 **Read and write permissions** → Save。

---

## CPUE 加權 ECDF 與相對 HSI

以 `Saury-csv.txt` 的 2,879 筆正 CPUE 作業紀錄，對 SST、Chl-a、SSHA、EKE、NPP、MLD 與 100 m 水溫同時計算一般 ECDF 與 CPUE 加權 ECDF。P25–P75 定義核心適生窗，P10–P90 定義可能適生窗；即時圖層以 SST 與 100 m 水溫分數的幾何平均形成 0–1 相對 HSI。

> **解讀限制**：資料沒有未作業海域或零漁獲樣本，所以 HSI 是歷史正漁獲條件下的相對適合度，不是校準後的魚群出現機率。HSI 圖層採 0.1 分級；推薦熱區以 HSI **> 0.5** 且面積至少 1,500 km² 判定。

> 次表層水溫若較 SST 落後超過 3 日，系統會自動退化為 SST-only HSI，並在畫面標示各資料來源日期與新鮮度。

介面可切換七項參數，並比較一般作業樣本 `F(x)` 與 CPUE 加權 `G(x)`；藍底顯示核心 P25–P75，垂直虛線標示 `|F-G|` 最大位置。完整方法、參數範圍、資料源與驗證規格見 [分析與速報系統設計](SAURY_ECDF_AND_FORECAST_DESIGN.md)。

## 資料來源

- HIMSST：https://www.data.jma.go.jp/goos/data/pub/JMA-product/him_sst_pac_D/
- NPRSUBT：https://www.data.jma.go.jp/goos/data/pub/JMA-product/npr_subt_jpn_D/
- NPRSUBC：https://www.data.jma.go.jp/goos/data/pub/JMA-product/npr_subc_jpn_D/

---

農業部水產試驗所 漁海況研究小組
