# 西北太平洋秋刀魚漁場速預報系統

## 農業部水產試驗所 · 漁海況研究小組

整合日本氣象廳（JMA）NEAR-GOOS 海洋資料，以互動式網頁地圖提供西北太平洋秋刀魚**當日速報與往後三日預報**：海面水溫、次表層水溫、表面海流、相對棲地適合度（HSI）、溫度鋒面、等溫線、漁場熱區與一鍵速預報。

**線上版本**：<https://petercttseng-ux.github.io/saury-forecast/>

### v6.0 主要變更

| 項目 | 變更 |
| --- | --- |
| 涵蓋範圍 | 東界由 162°E **擴至 180°E**（HIMSST 原生即 100–180°E，原先被顯示範圍切掉） |
| 預報 | 新增 **＋1 / ＋2 / ＋3 日預報場**，並內建每日回溯驗證（對照持續性法） |
| 資料來源 | 新增 **MGDSST**（全球 0.25°）作為 HIMSST 遲到／破洞時的備援補值 |
| HSI | 163.45°E 以東無 JMA 次表層產品，改為**逐格降階**為 SST 單因子（原先整片為空值） |
| 解析器 | 修正 `line.strip()` 吃掉前置空白導致整列數值錯位的既有錯誤；並改為向量化（約快 4–5 倍） |
| 建置 | 每次建置清理過期日期檔，`docs/data` 由 ~80 MB 降至約 6 MB |

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
   - 海面水溫 SST（HIMSST 0.1°×0.1°，至 180°E）
   - 次表層水溫（NPRSUBT，50 / 100 / 200 / 400 m）
   - 表面海流向量（NPRSUBC）：可調箭頭大小與空間解析度（密度）
   - 秋刀魚相對棲地適合度 HSI（CPUE 加權 ECDF）
   - 七項環境參數的一般／CPUE 加權 ECDF 互動比較曲線
   - 溫度鋒面偵測（SST 梯度等值線，門檻可調）
   - 等溫線圖層：海面水溫與次表層水溫皆可獨立開關，並可設定間距（1/2/3/5°C），線上標註溫度
2. 一鍵秋刀魚漁場速預報：自動計算 D0 至 D+3 的相對 HSI、疊合 SST 與鋒面，萃取高適合度漁場熱區並排序，並列出首選熱區的三日位移
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

1. `python data_downloader.py --count 16` 下載各 JMA 產品最近 16 日資料（需涵蓋趨勢視窗與回溯驗證）
2. `python build_static.py` 產生最新靜態資料（8 個分析日 + 3 個預報日，並清理過期檔）
3. 雙擊 `deploy_pages.bat` 推送到 GitHub
4. GitHub repo → Settings → Pages → Source：Deploy from a branch → Branch `main`、Folder `/docs` → Save
5. 約 1 分鐘後開啟：`https://petercttseng-ux.github.io/saury-forecast/`

> Pages 網址由 repo 名稱決定；前端使用相對路徑，改 repo 名亦可正常運作。

### 自動更新（GitHub Action）

`.github/workflows/update-data.yml` 每日（台灣時間 05:30）自動下載最新 JMA 資料、重算速報與三日預報、重建 `docs/data` 並提交，Pages 隨即更新；亦可在 Actions 分頁手動 Run workflow。工作流程會在日誌印出當日的預報技巧數字，並在 HIMSST 檔案不足時直接失敗（不發布無效預報）。

一次性設定：repo → Settings → Actions → General → Workflow permissions → 選 **Read and write permissions** → Save。

---

## CPUE 加權 ECDF 與相對 HSI

以 `Saury-csv.txt` 的 2,879 筆正 CPUE 作業紀錄，對 SST、Chl-a、SSHA、EKE、NPP、MLD 與 100 m 水溫同時計算一般 ECDF 與 CPUE 加權 ECDF。P25–P75 定義核心適生窗，P10–P90 定義可能適生窗；即時圖層以 SST 與 100 m 水溫分數的幾何平均形成 0–1 相對 HSI。

> **解讀限制**：資料沒有未作業海域或零漁獲樣本，所以 HSI 是歷史正漁獲條件下的相對適合度，不是校準後的魚群出現機率。HSI 圖層採 0.1 分級；推薦熱區以 HSI **> 0.5** 且面積至少 1,500 km² 判定。

> 次表層水溫若較 SST 落後超過 3 日，系統會自動退化為 SST-only HSI，並在畫面標示各資料來源日期與新鮮度。

介面可切換七項參數，並比較一般作業樣本 `F(x)` 與 CPUE 加權 `G(x)`；藍底顯示核心 P25–P75，垂直虛線標示 `|F-G|` 最大位置。完整方法、參數範圍、資料源與驗證規格見 [分析與速報系統設計](SAURY_ECDF_AND_FORECAST_DESIGN.md)。

## 三日預報：方法與限制

**JMA NEAR-GOOS 沒有公開的海況預報產品**（產品目錄只有分析場與海冰圖），因此 ＋1~＋3 日場由 JMA 分析場外推：

```
SST(t+n) = SST(t) + α × 大尺度趨勢 × n
```

趨勢為最近 5 日逐格最小二乘斜率經 6.2° 箱形平均大尺度化，α = 0.60。次表層水溫為持續場加收縮趨勢，表面海流為持續場。

方案以 81 日連續分析場、前半調參後半驗證選定。測試期（34 個起報日，未參與調參）相對持續性法的 RMSE 改進為 **+8.6 / +8.7 / +8.1%**（全域）與 **+8.8 / +9.7 / +9.8%**（漁場區）。

經實測為有害而關閉的成分（程式碼保留，數據見設計文件 §5.3）：表面海流平流（+1 日 −24.4%）、預報場平滑（−17.4%）、未大尺度化的逐格趨勢（+3 日 −4.1%）。

每次建置都會重算滾動回溯驗證並顯示在網頁與報告上。**這不是 JMA 官方預報。**

## 涵蓋範圍的硬限制

| 經度帶 | SST | 100 m 水溫／海流 | HSI 模式 |
| --- | --- | --- | --- |
| 114–163.45°E | ✅ HIMSST | ✅ NPR-4DVAR | SST × 100 m 水溫（雙因子） |
| 163.45–180°E | ✅ HIMSST | ❌ 無任何 JMA 產品 | **降階為 SST 單因子** |

系統逐格判定模式組成、在地圖上以虛線標示 163.45°E 界線，並在介面與報告顯示雙／單因子網格占比。**不以邊界值向東外推填補。** 秋刀魚主漁場在 9–11 月常延伸至 160–175°E，此界線落在核心作業海域內，使用者必須知道該區少了一個因子。

## 資料來源

- HIMSST（SST，0–60°N / 100–180°E / 0.1°）：https://www.data.jma.go.jp/goos/data/pub/JMA-product/him_sst_pac_D/
- NPRSUBT（次表層水溫，～163.45°E）：https://www.data.jma.go.jp/goos/data/pub/JMA-product/npr_subt_jpn_D/
- NPRSUBC（表面海流，～163.5°E）：https://www.data.jma.go.jp/goos/data/pub/JMA-product/npr_subc_jpn_D/
- MGDSST（全球 SST 0.25°，備援補值）：https://www.data.jma.go.jp/goos/data/pub/JMA-product/mgd_sst_glb_D/

---

農業部水產試驗所 漁海況研究小組
