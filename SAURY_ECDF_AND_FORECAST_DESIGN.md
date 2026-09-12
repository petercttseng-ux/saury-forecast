# 西北太平洋秋刀魚 ECDF 分析與漁海況速報系統設計

更新日期：2026-09-12

## 1. 分析目的與資料範圍

`Saury-csv.txt` 包含 2006–2010 年、6–11 月共 2,879 筆臺灣秋刀魚漁業正 CPUE 作業紀錄，欄位為年月、經緯度、CPUE、SST、Chl-a、SSHA、EKE、NPP、MLD 與 100 m 水溫。所有欄位均無缺值，亦無完全重複列；有 57 筆重複的「年、月、緯度、經度」鍵，但其環境值或 CPUE 不完全相同，推測是同一月／位置的重複作業觀測，因此保留並列為資料限制。

這是一份只有正 CPUE 與實際作業位置的資料，缺少未作業海域與零漁獲樣本。因此可建立「相對棲地適合度」，不能把 0–1 分數解讀為秋刀魚出現率或捕獲率。

## 2. CPUE 加權 ECDF 方法

對每一環境參數 `x` 建立一般 ECDF `F(x)`，並以 CPUE 為權重建立 `Gcpue(x)`。`|F(x)-Gcpue(x)|` 最大的位置代表環境分布與高 CPUE 分布差異最明顯的指標點。此作法與 Tseng et al. (2013) 所述的 CPUE 加權 ECDF 邏輯一致；該研究以 SST、Chl-a 與 NPP 得到 14–16 °C、0.4–0.6 mg m⁻³、600–800 mg C m⁻² d⁻¹ 的高 CPUE 範圍。

作業圖的相對 HSI 以 0.1 為分類間距（0.0–0.1 至 0.9–1.0）；只有 HSI 嚴格大於 0.5 且連通面積至少 1,500 km² 的海域列為推薦漁場。

本系統另定義可重現的環境窗：

- 核心環境窗：CPUE 加權 ECDF 的 P25–P75。
- 可能環境窗：CPUE 加權 ECDF 的 P10–P90。
- 單變數適合度：核心窗內為 1；在 P10–P25 與 P75–P90 線性遞減；窗外為 0。
- 多變數 HSI：可用且時效合格的單變數適合度取幾何平均。

## 3. 由 `Saury-csv.txt` 得到的環境參數範圍

| 參數 | CPUE 加權核心 P25–P75 | 可能 P10–P90 | 最大 ECDF 差異位置 | 單位 |
| --- | ---: | ---: | ---: | --- |
| 海面水溫 SST | 13.5–16.6 | 12.2–18.0 | 15.2 | °C |
| 葉綠素 a | 0.41–0.77 | 0.30–1.10 | 0.54 | mg m⁻³ |
| 海面高度異常 SSHA | 3.77–11.87 | -0.19–15.83 | 1.40 | cm |
| 渦動動能 EKE | 10.9–111.1 | 4.0–262.0 | 23.2 | cm² s⁻² |
| 淨初級生產力 NPP | 527.8–895.0 | 417.9–1214.3 | 1178.9 | mg C m⁻² d⁻¹ |
| 混合層深度 MLD | 14.3–26.6 | 11.1–37.9 | 20.4 | m |
| 100 m 水溫 | 3.0–6.3 | 2.2–8.8 | 3.2 | °C |

注意：最大 ECDF 差異位置是一個診斷點，不等於完整適合範圍。歷史研究的 SST、Chl-a、NPP 範圍可作外部合理性比較，但不能直接取代本資料的加權分位數，也不能在未驗證前混合成同一套門檻。

## 4. 海洋遙測與作業海況資料源

| 參數 | 建議主要來源 | 時空解析度／更新 | 系統用途 |
| --- | --- | --- | --- |
| SST | [JMA HIMSST](https://www.data.jma.go.jp/goos/data/pub/JMA-product/him_sst_pac_D/) | 0.1°、每日；融合地球同步／極軌衛星與現場觀測 | 每日 SST、溫度鋒面、HSI 主因子 |
| 50/100/200/400 m 水溫 | [JMA NPRSUBT](https://www.data.jma.go.jp/goos/data/pub/JMA-product/npr_subt_jpn_D/) | 約 0.1°、每日；NPR-4DVAR 同化 | 100 m 水溫 HSI、垂直結構 |
| 表面海流 | [JMA NPRSUBC](https://www.data.jma.go.jp/goos/data/pub/JMA-product/npr_subc_jpn_D/) | 約 0.1°、每日 | 洋流箭頭、鋒面與漂移判讀 |
| Chl-a、初級生產力 | [Copernicus Ocean Colour GLO L4 NRT 009_102](https://data.marine.copernicus.eu/product/OCEANCOLOUR_GLO_BGC_L4_NRT_009_102/description) | 4 km、每日／每月；多衛星融合、部分日資料為無缺口插補 | 食物場代理、三因子 ECDF HSI |
| SSHA、地轉流 | [Copernicus Sea Level L4 NRT 008_046](https://data.marine.copernicus.eu/product/SEALEVEL_GLO_PHY_L4_NRT_008_046/description) | 0.125°、每日、多任務衛星測高 | 暖冷渦、SSHA；由流速異常推算 EKE |
| 100 m 水溫、MLD、流場預報 | [Copernicus Global Physics Forecast 001_024](https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description) | 1/12°、逐時／每日、每日更新、10 日預報 | JMA 延遲時備援及未來 1–10 日預測 |
| 歷史衛星影像／產品交叉查核 | [NASA Ocean Color](https://data.nasa.gov/dataset/ocean-color) | L2/L3/SMI，多種時間合成 | Chl-a、SST 與長期回溯驗證 |

Copernicus 下載需帳號／憑證；憑證不可寫入靜態網站或版本庫。靜態頁面只接收經伺服器裁切、去識別並量化後的網格 JSON。

本次建置已取得 JMA HIMSST 至 2026-09-11，以及 NPRSUBT／NPRSUBC 至 2026-09-10；三項來源相對最新 SST 的時間差均在正式模型的 3 日門檻內。靜態速報包含 2026-09-04 至 2026-09-11 共 8 個連續日期。

## 5. 速報系統架構

```text
JMA / Copernicus / NASA
          │
          ▼
每日擷取器（重試、checksum、來源日期）
          │
          ▼
品質閘門（範圍、缺值、覆蓋率、時效、單位、網格方向）
          │
          ▼
統一網格與時間對齊（西北太平洋；保留原始來源日期）
          │
          ├── SST 梯度／等溫線／海流／渦旋衍生量
          └── ECDF 單變數 SI → 幾何平均 HSI
                              │
                              ▼
熱區連通元件、面積與航線優先序
                              │
                              ▼
Leaflet 互動地圖、來源時效、HTML 速報報告
```

現行可立即運作的模型使用 SST 與 100 m 水溫。當次表層資料相對 SST 落後超過 3 日時，系統自動降級為 SST 單因子 HSI，並在介面與報告顯示模型組成；不得把過舊的 100 m 水溫靜默混入當日結果。Chl-a、NPP、SSHA、EKE 與 MLD 已完成環境窗分析，但必須在相同日期／網格資料管線與獨立回溯驗證完成後，才加入正式每日 HSI。

## 6. 操作流程

1. 選擇資料日期並先查看「海況資料時效」。
2. 開啟 SST、溫度鋒面與海流，確認黑潮／親潮交會及鋒面位置。
3. 執行「一鍵秋刀魚漁場速預報」。
4. 優先檢視 HSI 較高、面積較大且鄰近溫度鋒面的連通區。
5. 下載 HTML 速報報告；出航前再與船上魚探、天氣、海象、油耗與作業法規交叉判讀。

## 7. 上線前驗證門檻

- 以年份留一法或 rolling-origin 做 2006–2010 回溯驗證，避免把同年相鄰網格同時放入訓練與測試造成空間洩漏。
- 報告 HSI 門檻下的 CPUE 捕獲覆蓋率、作業努力覆蓋率、熱區面積與可靠度曲線；因沒有真正 absence，不使用「準確率」單一指標。
- 每日檢查來源日期、缺值率、海域覆蓋率、物理合理範圍、網格方向、單位與異常跳變。
- 每季用新漁獲紀錄重估環境窗，但版本化保存門檻，不在漁季中無紀錄地調整。
- 明確標示 HSI 是決策支援，不是捕獲保證；任何安全、法規或禁漁限制均優先於模型結果。

## 8. 主要參考

- [Tseng et al. (2013), Spatial and temporal variability of the Pacific saury distribution in the northwestern Pacific Ocean](https://academic.oup.com/icesjms/article/70/5/991/643838)
- [JMA HIMSST 產品說明](https://www.data.jma.go.jp/goos/data/pub/JMA-product/him_sst_pac_D/Readme_him_sst_pac_D)
- [JMA NPRSUBT 產品說明](https://www.data.jma.go.jp/goos/data/pub/JMA-product/npr_subt_jpn_D/Readme_npr_subt_jpn_D)
- [JMA NPRSUBC 產品說明](https://www.data.jma.go.jp/goos/data/pub/JMA-product/npr_subc_jpn_D/Readme_npr_subc_jpn_D)
