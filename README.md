# 🎀 KpopStickerStudio — 無損像素保留 K-pop 貼圖與梗圖引擎

> 🚀 **專案現況**：已從原 `任務/03_Kpop_AI貼圖與梗圖產生器` 獨立升格為純無損 CLI 引擎（已移除 Web UI 與啟動器，專注核心引擎與 AI Skill 連動；原 `任務/03` 目錄已整併移除）。  
> **最高紅線（零修圖原則）**：100% 保留原始像素——**絕不進行 AI 修臉、美肌、重繪或自動濾鏡**；僅執行精準裁切、等比無損縮小、可選離線去背（白邊＋微陰影）、圓角／梗圖白條與飯圈風格描邊壓字，預設以**無損 PNG** 輸出至 `C:\Users\yexia\Pictures\貼圖\`。

---

## 🚀 雙入口架構（AI 自動跑 ＋ 本機 CLI 共用同一核心）

1. **入口 A（主力：搭配 AGY `05-Kpop追星` Skill 對話自動跑）**
   - 在任一對話中直接貼上照片（或提供本機／D 槽圖片路徑）並說明要做貼圖。
   - AI 自動辨識成員與構圖，透過互動選單提供 5 組量身設計詞條與版型選項。
   - 點選確認後，自動呼叫 `make_sticker.py` 產出無損 PNG 至 `C:\Users\yexia\Pictures\貼圖\<成員名>_<詞條>.png`，並進行視覺驗收與微調，免切換工作區。
2. **入口 B（本機 CLI 直呼 / 腳本批次處理）**
   - 底層 `src/sticker_maker/` 完全模組化解耦，可直接透過命令列參數指定裁切框、模式、字體與文字座標。

---

## ⚙️ 預設規格（集中於 `config.json`）

| 項目 | 預設值 | 說明 |
| :--- | :--- | :--- |
| **預設輸出資料夾** | `C:\Users\yexia\Pictures\貼圖` | 可用 `--out-dir` 隨時覆蓋指定位置 |
| **檔名規則** | `[人]_[字].png` | 自動過濾非法字元；同名自動補 `_02` 防覆蓋（`--overwrite` 可覆蓋） |
| **預設格式** | **無損 PNG** | 支援 `--format png \| webp \| jpg` |
| **預設模式** | `original`（原圖裁切＋壓字） | 另提供 `cutout`（離線去背＋白邊）與 `meme-bar`（外加純底文字條，零遮擋原圖） |
| **解析度上限** | `original` / `meme-bar`：`1024px`<br>`cutout`：`512px` | 設 `--max-size 0` 可保留裁切原解析度；原圖小於上限時**絕不硬放大** |
| **去背模型** | `birefnet-portrait`（備援 `isnet-general-use`） | 僅替換 Alpha 遮罩，100% 保留原 RGB 像素；預設 `8px` 白邊＋微陰影 |
| **字體與配色** | `bold`（預設黑體）＋ `classic`（白字黑邊） | 支援 `bold` / `heavy` / `sans` / `serif` / `kai` / `kr`（含韓文自動切換）；配色內建 `classic` / `heavy` / `yellow` / `pink` / `blue` / `dark` / `bar` |
| **排版比例** | `text_scale: 0.11` / `stroke_ratio: 0.068` | 預設對齊底部 `bottom`，支援 `--text-xy` 歸一化座標與 `--angle` 旋轉 |

---

## 💻 CLI 直接使用範例

```powershell
# 1. 原圖 1:1 裁切＋底部白字細黑邊（無損 PNG，存至 C:\Users\yexia\Pictures\貼圖\Wonhee_在幹嘛.png）
.\.venv\Scripts\python.exe make_sticker.py "D:\path\to\photo.jpg" --person "Wonhee" --text "在幹嘛" --aspect 1:1

# 2. 離線去背＋8px 平滑白邊＋微陰影（512px 透明 PNG，正方形畫布）
.\.venv\Scripts\python.exe make_sticker.py "D:\path\to\photo.jpg" --person "Ahyeon" --text "吃瓜中" --mode cutout --square-canvas

# 3. 梗圖白條模式（零遮擋偶像原圖）
.\.venv\Scripts\python.exe make_sticker.py "D:\path\to\photo.jpg" --person "Rora" --text "已讀亂回" --mode meme-bar --bar-pos bottom

# 4. 精準指定裁切框與文字位置（0.0~1.0 歸一化座標，或 --auto-trim 自動除白黑邊）
.\.venv\Scripts\python.exe make_sticker.py "D:\path\to\photo.jpg" --person "Minju" --text "收到！" --crop 0.1,0.05,0.9,0.85 --text-xy 0.5,0.88 --style yellow

# 5. JSON 批次大量產圖（自動除白黑邊＋依團體／成員資料夾歸檔＋產出驗收縮圖表）
.\.venv\Scripts\python.exe make_batch.py jobs.json --verify-sheet verify.jpg --json
```

---

## 📂 專案結構

```text
KpopStickerStudio/
├── config.json                  # 預設輸出路徑、尺寸上限、去背模型與字體樣式組態
├── make_sticker.py              # 單張 CLI 快捷入口
├── make_batch.py                # 批次 JSON 產圖與驗收拼圖入口
├── requirements.txt             # 依賴套件清單
├── src/sticker_maker/
│   ├── __init__.py
│   ├── batch.py                 # 批次任務排程、團體/成員分類輸出與驗收拼圖
│   ├── cli.py                   # 命令列參數解析、字型缺字檢查與 JSON 輸出
│   ├── config.py                # 組態載入
│   ├── cutout.py                # 離線去背＋平滑白邊＋遮罩品質防呆
│   ├── fonts.py                 # 本機繁中／韓文字體解析與缺字 (.notdef) 偵測
│   ├── naming.py                # 「人_字」安全命名與防覆蓋
│   └── renderer.py              # 自動除邊／無損裁切／縮放／圓角／梗圖條／描邊壓字
└── tests/
    └── test_studio.py           # 核心渲染、批次管線與 CLI 邊界測試
```

---

## 🛠️ 安裝與測試

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```
