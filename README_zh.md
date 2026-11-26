# KpopStickerStudio

[English](README.md) | [中文 (繁體)](README_zh.md)

專注於無損像素保留的命令列貼圖與梗圖渲染引擎。僅執行裁切、只縮不放的等比縮放、可選離線去背描邊、圓角、外掛梗圖文字條與多語系描邊壓字，不對來源圖片進行生成式改圖、美肌或色彩濾鏡處理。

---

## 檔案清單與元件職責

| 檔案 / 目錄 | 角色定位 | 核心職責 |
|---|---|---|
| [`make_sticker.py`](make_sticker.py) | 單張 CLI 執行入口 | 解析命令列參數並渲染單張貼圖或梗圖 |
| [`make_batch.py`](make_batch.py) | 批次 CLI 執行入口 | 讀取 JSON 批次工作清單並可選輸出視覺驗收縮圖表 |
| [`config.json`](config.json) | 預設組態檔 | 記錄預設輸出路徑、解析度上限、去背模型與字體樣式預設值 |
| [`src/sticker_maker/renderer.py`](src/sticker_maker/renderer.py) | 核心渲染管線 | 處理 EXIF 轉正、純色外框除邊、歸一化／比例裁切、縮放與文字合成 |
| [`src/sticker_maker/cutout.py`](src/sticker_maker/cutout.py) | 離線去背模組 | 執行 `birefnet-portrait`（備援 `isnet-general-use`）、Alpha 平滑、白邊陰影與遮罩品質檢查 |
| [`src/sticker_maker/fonts.py`](src/sticker_maker/fonts.py) | 字體與缺字檢查器 | 載入本機繁中／韓文／CJK 字體並偵測不支援之缺字方框 (`.notdef`) |
| [`src/sticker_maker/naming.py`](src/sticker_maker/naming.py) | 輸出命名防護模組 | 過濾檔名非法字元、格式化 `<人名>_<文字>.<副檔名>` 並防止同名覆蓋 |
| [`src/sticker_maker/batch.py`](src/sticker_maker/batch.py) | 批次執行與驗收拼圖 | 依團體／成員分類輸出貼圖並合成帶檔名與尺寸標籤的驗收拼圖 |
| [`src/sticker_maker/config.py`](src/sticker_maker/config.py) | 組態載入器 | 讀取 `config.json` 並自動展開使用者家目錄 `~` 路徑 |
| [`tests/test_studio.py`](tests/test_studio.py) | 自動化測試集 | 驗證像素保留、自動除邊、缺字偵測、批次輸出與 CLI 行為 |

---

## 處理模式與預設組態

### 渲染模式

| 模式 (`--mode`) | 說明 | 預設最長邊上限 (`--max-size`) |
|---|---|---|
| `original` | 裁切原圖、僅於超過上限時等比縮小，並疊加描邊文字 | `1024 px` |
| `cutout` | 執行離線去背且保留前景原始 RGB 像素，附加白邊與陰影 | `512 px` |
| `meme-bar` | 在圖片上方或下方外掛純色文字條，避免文字遮擋原圖主體 | `1024 px` |

### 預設參數 (`config.json`)

| 設定項目 | 預設值 | 說明 |
|---|---|---|
| `default_output_dir` | `~/Pictures/貼圖` | 可透過 `--out-dir` 覆蓋指定路徑 |
| `default_format` | `png` | 支援 `png`（無損）、`webp`（無損）與 `jpg`（品質 95、4:4:4） |
| `default_cutout_model` | `birefnet-portrait` | 失敗時自動降級使用 `isnet-general-use` |
| `default_font_preset` | `bold` | 支援 `bold`、`heavy`、`sans`、`serif`、`kai`、`kr`（偵測韓文自動切換） |
| `default_text_style` | `classic` | 內建 `classic`、`heavy`、`yellow`、`pink`、`blue`、`dark`、`bar` |
| `default_text_scale` | `0.11` | 文字高度相對於輸出短邊之比例；描邊比例預設為 `0.068` |

### 字型缺字防呆機制

Windows 常見中文字型（如 `NotoSansTC-VF.ttf`、`msjhbd.ttc`）不包含彩色 Emoji（例如 `🙏` 會渲染為缺字方框），基礎符號如 `♡` 則可正常顯示。渲染引擎會透過 `find_unsupported_chars` 逐字檢查字罩，若發現缺字將於終端機或 `--json` 的 `warnings` 欄位發出提醒。

---

## 安裝與使用

### 環境建置與測試

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

### 單張 CLI 執行範例

```powershell
# 1. 1:1 裁切＋底部白字細黑邊
.\.venv\Scripts\python.exe make_sticker.py "path\to\photo.jpg" --person "Wonhee" --text "在幹嘛" --aspect 1:1

# 2. 裁切前自動去除純白／純黑截圖外框
.\.venv\Scripts\python.exe make_sticker.py "path\to\screenshot.jpg" --person "Minju" --text "收到！" --auto-trim --aspect 1:1

# 3. 離線去背＋正方形透明畫布
.\.venv\Scripts\python.exe make_sticker.py "path\to\photo.jpg" --person "Ahyeon" --text "吃瓜中" --mode cutout --square-canvas

# 4. 零遮擋原圖之外掛文字條模式
.\.venv\Scripts\python.exe make_sticker.py "path\to\photo.jpg" --person "Rora" --text "已讀亂回" --mode meme-bar --bar-pos bottom

# 5. 指定歸一化裁切框 (x1,y1,x2,y2) 與自訂文字座標
.\.venv\Scripts\python.exe make_sticker.py "path\to\photo.jpg" --person "Minju" --text "拍照存證" --crop 0.27,0.014,0.83,1.0 --aspect 1:1 --text-xy 0.5,0.88 --style yellow
```

### 批次產圖 (`make_batch.py`)

建立 JSON 工作清單（`jobs.json`）。每筆任務可填入 `group` 與 `person` 自動歸檔至 `<default_output_dir>/<group>/<person>/<person>_<text>.png`，或直接指定 `out_dir`。若未指定 `crop`，`make_batch.py` 會自動偵測並裁除純白／純黑外框，再依 `y_bias`、`x_bias` 與 `zoom` 計算 `1:1` 裁切框。

```json
[
  {
    "input": "path/to/ILLIT_Minju_01.jpg",
    "group": "ILLIT",
    "person": "Minju",
    "text": "吃瓜中",
    "y_bias": 0.12
  },
  {
    "input": "path/to/ILLIT_Wonhee_01.jpg",
    "group": "ILLIT",
    "person": "Wonhee",
    "text": "人家不管",
    "crop": [0.0, 0.09, 0.86, 0.735]
  }
]
```

執行批次任務並產出視覺驗收縮圖表：

```powershell
.\.venv\Scripts\python.exe make_batch.py jobs.json --verify-sheet verify.jpg --json
```
