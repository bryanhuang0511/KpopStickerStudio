# 🎀 KpopStickerStudio — 無損像素保留 K-pop 貼圖與梗圖引擎

> **最高紅線**：100% 保留原始像素——**絕不進行 AI 修臉、美肌、重繪或自動濾鏡**；僅執行精準裁切、等比無損縮小、可選離線去背（白邊＋微陰影）、梗圖白條與飯圈風格描邊壓字，預設以**無損 PNG** 輸出至 `C:\Users\yexia\Pictures\貼圖\`。

---

## 🚀 使用方式（搭配 AGY 專屬 Skill）

1. 在任一 AGY 對話中直接貼上照片並說明要做貼圖。
2. AGY 會自動辨識成員與構圖，跳出互動選單提供 5 組量身設計詞條與版型選項。
3. 點選確認後，AGY 自動呼叫本專案 `make_sticker.py` 產出無損 PNG 至 `C:\Users\yexia\Pictures\貼圖\<成員名>_<詞條>.png`，並完成視覺驗收。

---

## 💻 CLI 直接使用範例

```powershell
# 1. 範例標準原圖 1:1 裁切＋底部白字細黑邊（無損 PNG）
.\.venv\Scripts\python.exe make_sticker.py "D:\path\to\photo.jpg" --person "沅禧" --text "在幹嘛" --aspect 1:1

# 2. 離線去背＋8px 平滑白邊＋微陰影（512px 透明 PNG）
.\.venv\Scripts\python.exe make_sticker.py "D:\path\to\photo.jpg" --person "Ahyeon" --text "吃瓜中" --mode cutout --square-canvas

# 3. 梗圖白條模式（零遮擋偶像原圖）
.\.venv\Scripts\python.exe make_sticker.py "D:\path\to\photo.jpg" --person "Rora" --text "已讀亂回" --mode meme-bar --bar-pos bottom
```

---

## 🛠️ 安裝與測試

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```
