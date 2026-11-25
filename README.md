# 🎀 KpopStickerStudio — 無損像素保留貼圖與梗圖工坊

> **最高紅線**：100% 保留原始像素——**絕不進行 AI 修臉、美肌、重繪或自動濾鏡**；僅執行精準裁切、等比無損縮小、可選離線去背（白邊＋微陰影）、梗圖白條與綜藝／飯圈風格描邊壓字，預設以**無損 PNG** 輸出。

---

## ✨ 三種協作方式（共用同一顆無損核心引擎）

1. **極簡本機 UI（雙擊 `start_studio.bat` 即開，關視窗 0 背景常駐）**
   - 支援 **`Ctrl+V` 剪貼簿直接貼圖**、一次拖曳多張照片排隊處理。
   - 滑鼠拖曳 `1:1` / `4:3` / `3:4` / 自由裁切框與文字位置，右側即時呈現真實無損成品。
   - 按 `Ctrl+S` 無損儲存至 `C:\Users\yexia\Pictures\貼圖\<人>_<字>.png`（同名自動 `_02` 防覆蓋），支援一鍵複製成品圖與手機同 Wi-Fi 下載連結。
2. **Agent 協作配詞佇列（`agent_queue.json`）**
   - 將一批圖片交給對話中的 Agent 看表情構圖、批次推薦多組貼合詞條寫入 `agent_queue.json`；打開 UI 點擊「🤖 載入 Agent 佇列」即可直接切換候選詞條、微調裁切與一鍵存檔。
   - 亦可由 Agent 直接呼叫 `make_sticker.py` 批次無損出圖。
3. **UI 內建「✨ AI 看圖想詞條」（選配 Gemini API）**
   - 若本機環境變數或 `.env`（或上層 `../key/.env`）含有 `GEMINI_API_KEY`，點擊即可當場依畫面表情推薦 6 組臺灣正體中文／韓文回訊息短詞（僅產文字，絕不修圖）。

---

## 🛠️ 安裝與啟動

```powershell
# 1. 建立虛擬環境並安裝依賴
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. 雙擊啟動本機介面（或由終端機執行）
.\start_studio.bat
# 或：.\.venv\Scripts\python.exe run_studio.py
```

### CLI 直接出圖範例
```powershell
.\.venv\Scripts\python.exe make_sticker.py "D:\path\to\photo.jpg" --person "沅禧" --text "在幹嘛" --aspect 1:1
```

---

## 🧪 執行自動化測試

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
