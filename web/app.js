(() => {
  const state = {
    config: null,
    queue: [], // { id, name, dataUrl, imgEl, naturalW, naturalH, crop, aspect, text, person, done, suggestions }
    activeId: null,
    mode: "original",
    viewMode: "split",
    textXy: null, // null = 使用 selectTextPos，否則 [cx, cy]
    lastPreviewDataUrl: null,
    renderTimer: null,
    renderSeq: 0,
    drag: null,
    agyPollTimer: null,
    lastAgyReplyTs: 0,
  };

  const el = {
    queueCount: document.getElementById("queueCount"),
    queueList: document.getElementById("queueList"),
    dropZone: document.getElementById("dropZone"),
    fileInput: document.getElementById("fileInput"),
    btnClearDone: document.getElementById("btnClearDone"),
    btnLoadAgentQueue: document.getElementById("btnLoadAgentQueue"),
    btnOpenFolder: document.getElementById("btnOpenFolder"),
    viewTabs: document.getElementById("viewTabs"),
    stageContainer: document.getElementById("stageContainer"),
    aspectGroup: document.getElementById("aspectGroup"),
    btnResetCrop: document.getElementById("btnResetCrop"),
    cropCanvas: document.getElementById("cropCanvas"),
    cropWrap: document.getElementById("cropWrap"),
    emptyHint: document.getElementById("emptyHint"),
    previewImg: document.getElementById("previewImg"),
    previewMeta: document.getElementById("previewMeta"),
    previewLoading: document.getElementById("previewLoading"),
    qualityAlert: document.getElementById("qualityAlert"),
    filenamePreview: document.getElementById("filenamePreview"),
    chkAutoNext: document.getElementById("chkAutoNext"),
    btnCopyPng: document.getElementById("btnCopyPng"),
    btnSave: document.getElementById("btnSave"),
    inputPerson: document.getElementById("inputPerson"),
    quickMembers: document.getElementById("quickMembers"),
    inputText: document.getElementById("inputText"),
    btnAskAgy: document.getElementById("btnAskAgy"),
    btnPullAgy: document.getElementById("btnPullAgy"),
    btnAiSuggest: document.getElementById("btnAiSuggest"),
    aiSuggestBox: document.getElementById("aiSuggestBox"),
    aiSuggestLabel: document.getElementById("aiSuggestLabel"),
    aiSuggestChips: document.getElementById("aiSuggestChips"),
    captionTabs: document.getElementById("captionTabs"),
    quickCaptions: document.getElementById("quickCaptions"),
    modeGroup: document.getElementById("modeGroup"),
    optOriginal: document.getElementById("optOriginal"),
    optMemeBar: document.getElementById("optMemeBar"),
    optCutout: document.getElementById("optCutout"),
    rangeRadius: document.getElementById("rangeRadius"),
    valRadius: document.getElementById("valRadius"),
    selectMaxSize: document.getElementById("selectMaxSize"),
    selectBarPos: document.getElementById("selectBarPos"),
    selectBarBg: document.getElementById("selectBarBg"),
    selectCutoutModel: document.getElementById("selectCutoutModel"),
    rangeOutline: document.getElementById("rangeOutline"),
    valOutline: document.getElementById("valOutline"),
    chkShadow: document.getElementById("chkShadow"),
    chkSquareCanvas: document.getElementById("chkSquareCanvas"),
    chkLineWhiteBg: document.getElementById("chkLineWhiteBg"),
    selectFont: document.getElementById("selectFont"),
    selectStyle: document.getElementById("selectStyle"),
    rangeTextScale: document.getElementById("rangeTextScale"),
    valTextScale: document.getElementById("valTextScale"),
    rangeStroke: document.getElementById("rangeStroke"),
    valStroke: document.getElementById("valStroke"),
    selectTextPos: document.getElementById("selectTextPos"),
    rangeAngle: document.getElementById("rangeAngle"),
    valAngle: document.getElementById("valAngle"),
    btnResetTextPos: document.getElementById("btnResetTextPos"),
    inputOutputDir: document.getElementById("inputOutputDir"),
    selectFormat: document.getElementById("selectFormat"),
    chkOverwrite: document.getElementById("chkOverwrite"),
    lastSavedBox: document.getElementById("lastSavedBox"),
    lastSavedName: document.getElementById("lastSavedName"),
    lastSavedLink: document.getElementById("lastSavedLink"),
    toast: document.getElementById("toast"),
  };

  const ctx = el.cropCanvas.getContext("2d");

  function showToast(msg, duration = 2200) {
    el.toast.textContent = msg;
    el.toast.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { el.toast.hidden = true; }, duration);
  }

  function getActive() {
    return state.queue.find((item) => item.id === state.activeId) || null;
  }

  function computeDefaultCrop(w, h, aspect) {
    if (aspect === "free") return [0, 0, 1, 1];
    const ratioMap = { "1:1": 1, "4:3": 4 / 3, "3:4": 3 / 4 };
    const target = ratioMap[aspect] || 1;
    const current = w / h;
    if (Math.abs(current - target) < 1e-3) return [0, 0, 1, 1];
    if (current > target) {
      const nw = (h * target) / w;
      const x1 = (1 - nw) / 2;
      return [x1, 0, x1 + nw, 1];
    } else {
      const nh = (w / target) / h;
      // 偏向人像上半身構圖，不切頭頂
      const y1 = Math.max(0, Math.min(1 - nh, (1 - nh) * 0.12));
      return [0, y1, 1, y1 + nh];
    }
  }

  function addImageItem({ name, dataUrl, person = "", text = "", crop = null, suggestions = [], mode = null }) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const aspect = "1:1";
        const item = {
          id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
          name: name || "貼上圖片.png",
          dataUrl,
          imgEl: img,
          naturalW: img.naturalWidth,
          naturalH: img.naturalHeight,
          aspect,
          crop: crop || computeDefaultCrop(img.naturalWidth, img.naturalHeight, aspect),
          person: person || el.inputPerson.value.trim(),
          text,
          suggestions,
          mode: mode || state.mode,
          done: false,
        };
        state.queue.push(item);
        renderQueue();
        selectItem(item.id);
        resolve(item);
      };
      img.src = dataUrl;
    });
  }

  function handleFiles(fileList) {
    const files = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
    if (!files.length) return;
    files.forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => addImageItem({ name: file.name, dataUrl: reader.result });
      reader.readAsDataURL(file);
    });
  }

  function selectItem(id) {
    state.activeId = id;
    state.textXy = null;
    const item = getActive();
    renderQueue();
    if (!item) {
      el.emptyHint.hidden = false;
      el.previewImg.hidden = true;
      el.btnSave.disabled = true;
      el.btnCopyPng.disabled = true;
      ctx.clearRect(0, 0, el.cropCanvas.width, el.cropCanvas.height);
      updateFilenamePreview();
      return;
    }

    el.emptyHint.hidden = true;
    el.btnSave.disabled = false;
    el.btnCopyPng.disabled = false;
    el.inputPerson.value = item.person || el.inputPerson.value;
    el.inputText.value = item.text || "";
    setAspectButtons(item.aspect);
    setMode(item.mode || state.mode, false);
    renderSuggestions(item.suggestions, item.suggestions?.length ? "Agent / AI 推薦詞條（點一下帶入）" : "");
    drawCropCanvas();
    updateFilenamePreview();
    scheduleRender(true);
  }

  function renderQueue() {
    el.queueCount.textContent = String(state.queue.length);
    el.queueList.innerHTML = "";
    state.queue.forEach((item) => {
      const row = document.createElement("div");
      row.className = `queue-item ${item.id === state.activeId ? "active" : ""}`;
      row.innerHTML = `
        <img class="queue-thumb" src="${item.dataUrl}" alt="" />
        <div class="queue-info">
          <div class="queue-name">${escapeHtml(item.name)}</div>
          <div class="queue-sub">${item.naturalW}×${item.naturalH}${item.text ? " · " + escapeHtml(item.text) : ""}</div>
        </div>
        ${item.done ? '<span class="queue-done" title="已儲存">✓</span>' : ""}
        <button class="queue-remove" title="從佇列移除">×</button>
      `;
      row.addEventListener("click", (ev) => {
        if (ev.target.classList.contains("queue-remove")) {
          state.queue = state.queue.filter((x) => x.id !== item.id);
          if (state.activeId === item.id) {
            selectItem(state.queue[0]?.id || null);
          } else {
            renderQueue();
          }
          return;
        }
        selectItem(item.id);
      });
      el.queueList.appendChild(row);
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function renderSuggestions(list, label) {
    if (!list || !list.length) {
      el.aiSuggestBox.hidden = true;
      return;
    }
    el.aiSuggestBox.hidden = false;
    el.aiSuggestLabel.textContent = label || "推薦詞條";
    el.aiSuggestChips.innerHTML = "";
    list.forEach((txt) => {
      const b = document.createElement("button");
      b.className = "chip";
      b.textContent = txt;
      b.onclick = () => {
        el.inputText.value = txt;
        syncActiveFields();
        scheduleRender();
      };
      el.aiSuggestChips.appendChild(b);
    });
  }

  function syncActiveFields() {
    const item = getActive();
    if (item) {
      item.person = el.inputPerson.value.trim();
      item.text = el.inputText.value;
      item.mode = state.mode;
      renderQueue();
    }
    updateFilenamePreview();
  }

  function updateFilenamePreview() {
    const p = el.inputPerson.value.trim().replace(/[<>:"/\\|?*]+/g, "");
    const t = el.inputText.value.replace(/\n/g, " ").trim().replace(/[<>:"/\\|?*]+/g, "");
    const ext = el.selectFormat.value;
    const parts = [p, t].filter(Boolean);
    const stem = parts.length ? parts.join("_") : "貼圖";
    el.filenamePreview.textContent = `${stem}.${ext}`;
  }

  function setAspectButtons(aspect) {
    el.aspectGroup.querySelectorAll("button[data-aspect]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.aspect === aspect);
    });
  }

  function setMode(mode, triggerRender = true) {
    state.mode = mode;
    el.modeGroup.querySelectorAll("button").forEach((b) => {
      b.classList.toggle("active", b.dataset.mode === mode);
    });
    el.optOriginal.hidden = mode !== "original";
    el.optMemeBar.hidden = mode !== "meme-bar";
    el.optCutout.hidden = mode !== "cutout";
    const item = getActive();
    if (item) item.mode = mode;
    if (triggerRender) scheduleRender();
  }

  function drawCropCanvas() {
    const item = getActive();
    if (!item) return;

    const wrapRect = el.cropWrap.getBoundingClientRect();
    const maxW = Math.max(120, wrapRect.width - 24);
    const maxH = Math.max(120, wrapRect.height - 24);
    const scale = Math.min(maxW / item.naturalW, maxH / item.naturalH, 1);
    const cw = Math.max(1, Math.round(item.naturalW * scale));
    const ch = Math.max(1, Math.round(item.naturalH * scale));

    el.cropCanvas.width = cw;
    el.cropCanvas.height = ch;

    ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(item.imgEl, 0, 0, cw, ch);

    const [x1, y1, x2, y2] = item.crop;
    const rx = x1 * cw;
    const ry = y1 * ch;
    const rw = (x2 - x1) * cw;
    const rh = (y2 - y1) * ch;

    // 暗化裁切外區域
    ctx.fillStyle = "rgba(0, 0, 0, 0.58)";
    ctx.fillRect(0, 0, cw, ry);
    ctx.fillRect(0, ry + rh, cw, ch - (ry + rh));
    ctx.fillRect(0, ry, rx, rh);
    ctx.fillRect(rx + rw, ry, cw - (rx + rw), rh);

    // 裁切框邊線與九宮格輔助線
    ctx.strokeStyle = "#ff5b99";
    ctx.lineWidth = 2;
    ctx.strokeRect(rx + 1, ry + 1, Math.max(1, rw - 2), Math.max(1, rh - 2));

    ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
    ctx.lineWidth = 1;
    for (let i = 1; i <= 2; i++) {
      ctx.beginPath();
      ctx.moveTo(rx + (rw * i) / 3, ry);
      ctx.lineTo(rx + (rw * i) / 3, ry + rh);
      ctx.moveTo(rx, ry + (rh * i) / 3);
      ctx.lineTo(rx + rw, ry + (rh * i) / 3);
      ctx.stroke();
    }

    // 四角縮放把手
    const handles = [
      [rx, ry], [rx + rw, ry],
      [rx, ry + rh], [rx + rw, ry + rh],
    ];
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = "#ff5b99";
    ctx.lineWidth = 2;
    handles.forEach(([hx, hy]) => {
      ctx.beginPath();
      ctx.arc(hx, hy, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });

    // 文字拖曳中心點
    const [txNorm, tyNorm] = getTextMarkerNorm();
    const tx = rx + txNorm * rw;
    const ty = ry + tyNorm * rh;
    ctx.fillStyle = "#4f8cff";
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(tx, ty, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 10px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("字", tx, ty + 0.5);
  }

  function getTextMarkerNorm() {
    if (state.textXy) return state.textXy;
    const pos = el.selectTextPos.value;
    const map = {
      "bottom": [0.5, 0.88],
      "top": [0.5, 0.12],
      "center": [0.5, 0.5],
      "top-left": [0.22, 0.14],
      "top-right": [0.78, 0.14],
      "bottom-left": [0.22, 0.86],
      "bottom-right": [0.78, 0.86],
    };
    return map[pos] || [0.5, 0.88];
  }

  function getCanvasPoint(ev) {
    const rect = el.cropCanvas.getBoundingClientRect();
    return {
      x: ((ev.clientX - rect.left) / rect.width) * el.cropCanvas.width,
      y: ((ev.clientY - rect.top) / rect.height) * el.cropCanvas.height,
    };
  }

  el.cropCanvas.addEventListener("mousedown", (ev) => {
    const item = getActive();
    if (!item) return;
    const pt = getCanvasPoint(ev);
    const cw = el.cropCanvas.width;
    const ch = el.cropCanvas.height;
    const [x1, y1, x2, y2] = item.crop;
    const rx = x1 * cw, ry = y1 * ch, rw = (x2 - x1) * cw, rh = (y2 - y1) * ch;

    // 1. 檢查文字藍點
    const [tnx, tny] = getTextMarkerNorm();
    const tx = rx + tnx * rw, ty = ry + tny * rh;
    if (Math.hypot(pt.x - tx, pt.y - ty) <= 13) {
      state.drag = { type: "text" };
      return;
    }

    // 2. 檢查四角縮放把手
    const corners = [
      { key: "nw", x: rx, y: ry },
      { key: "ne", x: rx + rw, y: ry },
      { key: "sw", x: rx, y: ry + rh },
      { key: "se", x: rx + rw, y: ry + rh },
    ];
    for (const c of corners) {
      if (Math.hypot(pt.x - c.x, pt.y - c.y) <= 12) {
        state.drag = { type: c.key, startCrop: [...item.crop], startPt: pt };
        return;
      }
    }

    // 3. 檢查裁切框內移動
    if (pt.x >= rx && pt.x <= rx + rw && pt.y >= ry && pt.y <= ry + rh) {
      state.drag = { type: "move", startCrop: [...item.crop], startPt: pt };
    }
  });

  window.addEventListener("mousemove", (ev) => {
    if (!state.drag) return;
    const item = getActive();
    if (!item) return;
    const pt = getCanvasPoint(ev);
    const cw = el.cropCanvas.width;
    const ch = el.cropCanvas.height;

    if (state.drag.type === "text") {
      const [x1, y1, x2, y2] = item.crop;
      const rx = x1 * cw, ry = y1 * ch, rw = (x2 - x1) * cw, rh = (y2 - y1) * ch;
      const nx = Math.max(0.05, Math.min(0.95, (pt.x - rx) / Math.max(1, rw)));
      const ny = Math.max(0.05, Math.min(0.95, (pt.y - ry) / Math.max(1, rh)));
      state.textXy = [Number(nx.toFixed(3)), Number(ny.toFixed(3))];
      drawCropCanvas();
      return;
    }

    const dx = (pt.x - state.drag.startPt.x) / cw;
    const dy = (pt.y - state.drag.startPt.y) / ch;
    let [x1, y1, x2, y2] = state.drag.startCrop;
    const minSpan = 0.12;

    if (state.drag.type === "move") {
      const w = x2 - x1, h = y2 - y1;
      x1 = Math.max(0, Math.min(1 - w, x1 + dx));
      y1 = Math.max(0, Math.min(1 - h, y1 + dy));
      item.crop = [x1, y1, x1 + w, y1 + h];
    } else {
      if (state.drag.type.includes("w")) x1 = Math.max(0, Math.min(x2 - minSpan, x1 + dx));
      if (state.drag.type.includes("e")) x2 = Math.min(1, Math.max(x1 + minSpan, x2 + dx));
      if (state.drag.type.includes("n")) y1 = Math.max(0, Math.min(y2 - minSpan, y1 + dy));
      if (state.drag.type.includes("s")) y2 = Math.min(1, Math.max(y1 + minSpan, y2 + dy));

      // 若有鎖定比例，依寬度或高度自動約束
      const ratioMap = { "1:1": 1, "4:3": 4 / 3, "3:4": 3 / 4 };
      const targetRatio = ratioMap[item.aspect];
      if (targetRatio) {
        const pxW = (x2 - x1) * item.naturalW;
        const desiredHNorm = (pxW / targetRatio) / item.naturalH;
        if (state.drag.type.includes("n")) {
          y1 = Math.max(0, y2 - desiredHNorm);
          const actualPxH = (y2 - y1) * item.naturalH;
          const actualWNorm = (actualPxH * targetRatio) / item.naturalW;
          if (state.drag.type.includes("w")) x1 = x2 - actualWNorm;
          else x2 = x1 + actualWNorm;
        } else {
          y2 = Math.min(1, y1 + desiredHNorm);
          const actualPxH = (y2 - y1) * item.naturalH;
          const actualWNorm = (actualPxH * targetRatio) / item.naturalW;
          if (state.drag.type.includes("w")) x1 = x2 - actualWNorm;
          else x2 = x1 + actualWNorm;
        }
      }
      item.crop = [
        Math.max(0, Math.min(1, x1)),
        Math.max(0, Math.min(1, y1)),
        Math.max(0, Math.min(1, x2)),
        Math.max(0, Math.min(1, y2)),
      ];
    }
    drawCropCanvas();
  });

  window.addEventListener("mouseup", () => {
    if (!state.drag) return;
    state.drag = null;
    scheduleRender(true);
  });

  function buildRequestPayload() {
    const item = getActive();
    if (!item) return null;
    const mode = state.mode;
    const maxSize = mode === "cutout" ? 512 : Number(el.selectMaxSize.value);
    return {
      image_data: item.dataUrl,
      person: el.inputPerson.value.trim(),
      text: el.inputText.value,
      mode,
      crop: item.crop,
      aspect: "free", // 已由前端精準 crop 框決定
      max_size: maxSize,
      radius: Number(el.rangeRadius.value),
      cutout_model: el.selectCutoutModel.value,
      outline_width: Number(el.rangeOutline.value),
      shadow: el.chkShadow.checked,
      square_canvas: el.chkSquareCanvas.checked,
      bg_fill: mode === "cutout" && el.chkLineWhiteBg.checked ? "#FFFFFF" : null,
      bar_pos: el.selectBarPos.value,
      bar_bg: el.selectBarBg.value,
      font: el.selectFont.value,
      style: el.selectStyle.value,
      pos: el.selectTextPos.value,
      text_xy: state.textXy,
      text_scale: Number(el.rangeTextScale.value),
      stroke_ratio: Number(el.rangeStroke.value),
      angle: Number(el.rangeAngle.value),
      format: el.selectFormat.value,
      output_dir: el.inputOutputDir.value.trim(),
      overwrite: el.chkOverwrite.checked,
    };
  }

  function scheduleRender(immediate = false) {
    clearTimeout(state.renderTimer);
    state.renderTimer = setTimeout(runPreviewRender, immediate ? 40 : 280);
  }

  async function runPreviewRender() {
    const payload = buildRequestPayload();
    if (!payload) return;
    const seq = ++state.renderSeq;
    el.previewLoading.hidden = false;
    try {
      const resp = await fetch("/api/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (seq !== state.renderSeq) return;
      if (!data.ok) {
        showToast(`渲染失敗：${data.error || "未知錯誤"}`, 3200);
        return;
      }
      state.lastPreviewDataUrl = data.image_data;
      el.previewImg.src = data.image_data;
      el.previewImg.hidden = false;
      el.previewMeta.textContent = `${data.output_size[0]}×${data.output_size[1]} · ${data.file_size_kb} KB`;
      if (data.cutout_quality && data.cutout_quality.warning) {
        el.qualityAlert.textContent = `⚠️ ${data.cutout_quality.warning}`;
        el.qualityAlert.hidden = false;
      } else {
        el.qualityAlert.hidden = true;
      }
    } catch (err) {
      if (seq === state.renderSeq) showToast(`預覽連線錯誤：${err.message}`);
    } finally {
      if (seq === state.renderSeq) el.previewLoading.hidden = true;
    }
  }

  async function saveCurrentSticker() {
    const payload = buildRequestPayload();
    const item = getActive();
    if (!payload || !item) return;
    el.btnSave.disabled = true;
    try {
      const resp = await fetch("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!data.ok) {
        showToast(`儲存失敗：${data.error || "未知錯誤"}`, 3500);
        return;
      }
      item.done = true;
      renderQueue();
      el.lastSavedBox.hidden = false;
      el.lastSavedName.textContent = `${data.filename} (${data.output_size[0]}×${data.output_size[1]}, ${data.file_size_kb} KB)`;
      el.lastSavedLink.href = data.download_url;
      el.lastSavedLink.textContent = data.download_url;
      showToast(`已無損儲存：${data.filename}`);

      if (el.chkAutoNext.checked) {
        const nextItem = state.queue.find((q) => !q.done && q.id !== item.id);
        if (nextItem) selectItem(nextItem.id);
      }
    } catch (err) {
      showToast(`儲存錯誤：${err.message}`, 3500);
    } finally {
      el.btnSave.disabled = false;
    }
  }

  async function copyPreviewToClipboard() {
    if (!state.lastPreviewDataUrl) return;
    try {
      const blob = await (await fetch(state.lastPreviewDataUrl)).blob();
      await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
      showToast("已複製無損成品圖，可直接 Ctrl+V 貼到聊天室！");
    } catch (err) {
      showToast(`剪貼簿複製失敗（部分瀏覽器僅支援 PNG）：${err.message}`, 3200);
    }
  }

  async function askAgyForCaptions() {
    const item = getActive();
    if (!item) {
      showToast("請先貼上或選擇一張圖片");
      return;
    }
    el.btnAskAgy.disabled = true;
    try {
      const resp = await fetch("/api/agy/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_data: item.dataUrl, person: el.inputPerson.value.trim() }),
      });
      const data = await resp.json();
      if (!data.ok) {
        showToast(`準備 AGY 交接失敗：${data.error}`, 3500);
        return;
      }
      state.lastAgyReplyTs = data.timestamp;
      try {
        await navigator.clipboard.writeText(data.prompt);
        showToast("已複製指令！切到 AGY 按 Ctrl+V 送出，詞條會自動同步回來", 4500);
      } catch (_) {
        window.prompt("請複製以下指令貼給 AGY：", data.prompt);
      }
      startAgyPolling();
    } catch (err) {
      showToast(`連線失敗：${err.message}`);
    } finally {
      el.btnAskAgy.disabled = false;
    }
  }

  async function pullAgyReply(manual = false) {
    try {
      const resp = await fetch("/api/agy/reply");
      const data = await resp.json();
      if (!data.ok || !data.has_reply) {
        if (manual) showToast("尚未收到 AGY 新回覆詞條");
        return false;
      }
      if (!manual && data.timestamp <= state.lastAgyReplyTs) return false;
      state.lastAgyReplyTs = data.timestamp;
      const item = getActive();
      if (item) {
        item.suggestions = data.captions;
        if (data.person && !el.inputPerson.value.trim()) {
          el.inputPerson.value = data.person;
          item.person = data.person;
        }
        if (Array.isArray(data.crop) && data.crop.length === 4) {
          item.crop = data.crop.map(Number);
          drawCropCanvas();
          scheduleRender(true);
        }
      }
      const label = data.note ? `🤖 AGY 推薦詞條（${data.note}）` : "🤖 AGY 推薦詞條（點一下帶入）";
      renderSuggestions(data.captions, label);
      showToast(`✨ 已同步 ${data.captions.length} 組 AGY 推薦詞條！`, 3000);
      stopAgyPolling();
      return true;
    } catch (_) {
      return false;
    }
  }

  function startAgyPolling() {
    stopAgyPolling();
    let ticks = 0;
    state.agyPollTimer = setInterval(async () => {
      ticks += 1;
      const got = await pullAgyReply(false);
      if (got || ticks >= 60) stopAgyPolling();
    }, 1500);
  }

  function stopAgyPolling() {
    if (state.agyPollTimer) {
      clearInterval(state.agyPollTimer);
      state.agyPollTimer = null;
    }
  }

  async function requestAiSuggestions() {
    const item = getActive();
    if (!item) {
      showToast("請先貼上或選擇一張圖片");
      return;
    }
    el.btnAiSuggest.disabled = true;
    el.btnAiSuggest.textContent = "思考中...";
    try {
      const resp = await fetch("/api/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_data: item.dataUrl, person: el.inputPerson.value.trim() }),
      });
      const data = await resp.json();
      if (data.ok && data.captions?.length) {
        item.suggestions = data.captions;
        renderSuggestions(data.captions, `✨ ${data.message}`);
        showToast(data.message);
      } else {
        showToast(data.message || "目前未設定 Gemini API Key，可改由對話 Agent 匯入詞條", 4000);
      }
    } catch (err) {
      showToast(`推薦詞條失敗：${err.message}`);
    } finally {
      el.btnAiSuggest.disabled = false;
      el.btnAiSuggest.textContent = "✨ AI 看圖想詞條";
    }
  }

  async function loadAgentQueue() {
    try {
      const resp = await fetch("/api/agent-queue");
      const data = await resp.json();
      if (!data.items || !data.items.length) {
        showToast("目前沒有 Agent 匯入的待處理佇列（可在對話中傳圖請 Agent 配詞匯入）", 3500);
        return;
      }
      for (const q of data.items) {
        const imgResp = await fetch(`/api/agent-image?index=${q.index}`);
        const blob = await imgResp.blob();
        const dataUrl = await new Promise((res) => {
          const r = new FileReader();
          r.onload = () => res(r.result);
          r.readAsDataURL(blob);
        });
        await addImageItem({
          name: q.name,
          dataUrl,
          person: q.person,
          text: q.recommended_text || (q.suggestions[0] || ""),
          crop: q.crop,
          suggestions: q.suggestions,
          mode: q.mode || "original",
        });
      }
      showToast(`已載入 ${data.items.length} 張 Agent 配詞圖片！`);
    } catch (err) {
      showToast(`載入 Agent 佇列失敗：${err.message}`);
    }
  }

  function initQuickControls(cfg) {
    el.inputOutputDir.value = cfg.default_output_dir;
    el.selectMaxSize.value = String(cfg.default_max_size);
    el.selectFont.value = cfg.default_font_preset;
    el.selectStyle.value = cfg.default_text_style;
    el.rangeTextScale.value = String(cfg.default_text_scale);
    el.valTextScale.textContent = (cfg.default_text_scale * 100).toFixed(1);
    el.rangeStroke.value = String(cfg.default_stroke_ratio);
    el.valStroke.textContent = (cfg.default_stroke_ratio * 100).toFixed(1);

    el.quickMembers.innerHTML = "";
    (cfg.quick_members || []).forEach((name) => {
      const b = document.createElement("button");
      b.className = "chip";
      b.textContent = name;
      b.onclick = () => {
        el.inputPerson.value = name;
        syncActiveFields();
      };
      el.quickMembers.appendChild(b);
    });

    const categories = Object.keys(cfg.quick_captions || {});
    el.captionTabs.innerHTML = "";
    const showCategory = (cat) => {
      el.captionTabs.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.cat === cat));
      el.quickCaptions.innerHTML = "";
      (cfg.quick_captions[cat] || []).forEach((txt) => {
        const b = document.createElement("button");
        b.className = "chip";
        b.textContent = txt;
        b.onclick = () => {
          el.inputText.value = txt;
          syncActiveFields();
          scheduleRender();
        };
        el.quickCaptions.appendChild(b);
      });
    };
    categories.forEach((cat, i) => {
      const b = document.createElement("button");
      b.className = `caption-tab ${i === 0 ? "active" : ""}`;
      b.dataset.cat = cat;
      b.textContent = cat;
      b.onclick = () => showCategory(cat);
      el.captionTabs.appendChild(b);
    });
    if (categories.length) showCategory(categories[0]);
  }

  // 事件綁定
  el.fileInput.addEventListener("change", (ev) => {
    handleFiles(ev.target.files);
    el.fileInput.value = "";
  });

  ["dragenter", "dragover"].forEach((evt) => {
    window.addEventListener(evt, (ev) => {
      ev.preventDefault();
      el.dropZone.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    window.addEventListener(evt, (ev) => {
      ev.preventDefault();
      el.dropZone.classList.remove("drag-over");
    });
  });
  window.addEventListener("drop", (ev) => {
    if (ev.dataTransfer?.files?.length) handleFiles(ev.dataTransfer.files);
  });

  window.addEventListener("paste", (ev) => {
    const items = ev.clipboardData?.items;
    if (!items) return;
    for (const it of items) {
      if (it.type.startsWith("image/")) {
        const file = it.getAsFile();
        if (file) {
          handleFiles([file]);
          showToast("已從剪貼簿貼上圖片！");
        }
      }
    }
  });

  window.addEventListener("keydown", (ev) => {
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") {
      ev.preventDefault();
      saveCurrentSticker();
    }
  });

  el.viewTabs.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-view]");
    if (!btn) return;
    state.viewMode = btn.dataset.view;
    el.viewTabs.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
    el.stageContainer.className = `stage-container view-${state.viewMode}`;
    setTimeout(drawCropCanvas, 20);
  });

  el.aspectGroup.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-aspect]");
    if (!btn) return;
    const item = getActive();
    if (!item) return;
    item.aspect = btn.dataset.aspect;
    item.crop = computeDefaultCrop(item.naturalW, item.naturalH, item.aspect);
    setAspectButtons(item.aspect);
    drawCropCanvas();
    scheduleRender(true);
  });

  el.btnResetCrop.addEventListener("click", () => {
    const item = getActive();
    if (!item) return;
    item.crop = computeDefaultCrop(item.naturalW, item.naturalH, item.aspect);
    drawCropCanvas();
    scheduleRender(true);
  });

  el.modeGroup.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-mode]");
    if (btn) setMode(btn.dataset.mode, true);
  });

  el.btnClearDone.addEventListener("click", () => {
    state.queue = state.queue.filter((x) => !x.done);
    if (!getActive()) selectItem(state.queue[0]?.id || null);
    else renderQueue();
  });

  el.inputPerson.addEventListener("input", syncActiveFields);
  el.inputText.addEventListener("input", () => { syncActiveFields(); scheduleRender(); });
  el.selectFormat.addEventListener("change", () => { updateFilenamePreview(); scheduleRender(); });

  [
    el.selectMaxSize, el.selectBarPos, el.selectBarBg, el.selectCutoutModel,
    el.chkShadow, el.chkSquareCanvas, el.chkLineWhiteBg,
    el.selectFont, el.selectStyle,
  ].forEach((ctrl) => ctrl.addEventListener("change", () => scheduleRender()));

  el.selectTextPos.addEventListener("change", () => {
    state.textXy = null;
    drawCropCanvas();
    scheduleRender();
  });

  el.btnResetTextPos.addEventListener("click", () => {
    state.textXy = null;
    drawCropCanvas();
    scheduleRender(true);
  });

  el.rangeRadius.addEventListener("input", () => { el.valRadius.textContent = el.rangeRadius.value; scheduleRender(); });
  el.rangeOutline.addEventListener("input", () => { el.valOutline.textContent = el.rangeOutline.value; scheduleRender(); });
  el.rangeTextScale.addEventListener("input", () => {
    el.valTextScale.textContent = (Number(el.rangeTextScale.value) * 100).toFixed(1);
    scheduleRender();
  });
  el.rangeStroke.addEventListener("input", () => {
    el.valStroke.textContent = (Number(el.rangeStroke.value) * 100).toFixed(1);
    scheduleRender();
  });
  el.rangeAngle.addEventListener("input", () => { el.valAngle.textContent = el.rangeAngle.value; scheduleRender(); });

  el.btnSave.addEventListener("click", saveCurrentSticker);
  el.btnCopyPng.addEventListener("click", copyPreviewToClipboard);
  el.btnAskAgy.addEventListener("click", askAgyForCaptions);
  el.btnPullAgy.addEventListener("click", () => pullAgyReply(true));
  el.btnAiSuggest.addEventListener("click", requestAiSuggestions);
  el.btnLoadAgentQueue.addEventListener("click", loadAgentQueue);
  el.btnOpenFolder.addEventListener("click", () => {
    fetch("/api/open-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ output_dir: el.inputOutputDir.value.trim() }),
    });
  });

  window.addEventListener("resize", () => drawCropCanvas());

  // 啟動載入組態
  fetch("/api/config")
    .then((r) => r.json())
    .then((cfg) => {
      state.config = cfg;
      initQuickControls(cfg);
    })
    .catch((err) => showToast(`載入設定失敗：${err.message}`));

  // 心跳保活與關窗自動收尾（支援 .exe 無黑窗模式 0 背景殘留）
  const sendPing = () => fetch("/api/ping", { method: "POST" }).catch(() => {});
  setInterval(sendPing, 10000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) sendPing();
  });

  window.addEventListener("pagehide", () => {
    try {
      navigator.sendBeacon("/api/bye", "{}");
    } catch (_) {}
  });
})();
