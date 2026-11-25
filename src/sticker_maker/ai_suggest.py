"""AI 看圖推薦回訊息詞條（支援 Gemini API 選配直連 + Agent 草稿佇列讀寫）。"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .config import PROJECT_ROOT, load_config

AGENT_QUEUE_PATH = PROJECT_ROOT / "agent_queue.json"


def _read_key_from_env_file(env_path: Path, key_name: str = "GEMINI_API_KEY") -> str | None:
    if not env_path.exists():
        return None
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            if k.strip() == key_name:
                val = v.strip().strip('"').strip("'")
                if val:
                    return val
    except Exception:
        return None
    return None


def find_gemini_api_key() -> str | None:
    """安全尋找本機 GEMINI_API_KEY（環境變數 -> 專案 .env -> 上層 key/.env），絕不輸出金鑰值。"""
    env_val = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_val:
        return env_val

    candidates = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT.parent / "key" / ".env",
    ]
    for path in candidates:
        found = _read_key_from_env_file(path, "GEMINI_API_KEY")
        if found:
            return found
    return None


def suggest_captions_via_gemini(
    raw_image: Image.Image,
    person: str = "",
    count: int = 6,
    model: str | None = None,
) -> dict[str, Any]:
    """呼叫 Gemini 視覺模型看圖推薦簡短回訊息詞條（絕不修圖，只回傳文字建議）。"""
    api_key = find_gemini_api_key()
    if not api_key:
        return {
            "ok": False,
            "source": "none",
            "captions": [],
            "message": "尚未設定 GEMINI_API_KEY。你可以設定環境變數，或直接把圖丟給對話中的 Agent 匯入候選詞條。",
        }

    cfg = load_config()
    model_name = model or cfg.gemini_model

    # 縮圖傳給視覺模型節省流量與延遲（不影響本機無損原圖）
    thumb = ImageOps.exif_transpose(raw_image).convert("RGB")
    thumb.thumbnail((512, 512), Image.Resampling.LANCZOS)
    buf = BytesIO()
    thumb.save(buf, format="JPEG", quality=85)
    b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

    who_hint = f"圖中人物為 {person}。" if person.strip() else ""
    prompt = (
        f"你是一位熟悉臺灣網路用語與 K-pop 飯圈文化的貼圖文案師。{who_hint}\n"
        f"請根據這張照片的「表情、眼神、姿勢與情境」，發想 {count} 個最適合在 LINE / IG 回訊息使用的貼圖短詞。\n"
        "規範：\n"
        "1. 每個詞條 2～6 個字（臺灣正體中文為主，最多夾雜 1 個常用韓文短語如 진짜? / 뭐해?）。\n"
        "2. 口語自然、有反差感或實用回訊息場景（例如：在幹嘛、笑死、收到！、偷看、你在說啥、我先走了）。\n"
        "3. 嚴格只回傳 JSON 陣列，例如：[\"在幹嘛\", \"偷看\", \"嗨～\"]，不要加任何說明或 Markdown 標記。"
    )

    body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.75,
                "maxOutputTokens": 256,
            },
        }
    ).encode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "source": "gemini",
            "captions": [],
            "message": f"Gemini API 回傳 HTTP {exc.code}，請檢查金鑰額度或改由對話 Agent 配詞。",
        }
    except Exception as exc:
        return {
            "ok": False,
            "source": "gemini",
            "captions": [],
            "message": f"無法連線至 Gemini API（{exc}），離線時可使用內建分類詞條或對話 Agent 配詞。",
        }

    text_out = ""
    try:
        parts = resp_data["candidates"][0]["content"]["parts"]
        text_out = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError):
        text_out = ""

    captions = _parse_caption_list(text_out, limit=count)
    if not captions:
        return {
            "ok": False,
            "source": "gemini",
            "captions": [],
            "message": "模型回傳格式無法解析，請再試一次或直接使用下方快捷詞條。",
        }

    return {
        "ok": True,
        "source": f"gemini:{model_name}",
        "captions": captions,
        "message": f"已依圖片表情推薦 {len(captions)} 組詞條",
    }


def _parse_caption_list(raw_text: str, limit: int = 8) -> list[str]:
    if not raw_text:
        return []
    cleaned = raw_text.strip()
    match = re.search(r"\[[\s\S]*\]", cleaned)
    if match:
        try:
            arr = json.loads(match.group(0))
            if isinstance(arr, list):
                out = [str(x).strip() for x in arr if str(x).strip()]
                return out[:limit]
        except json.JSONDecodeError:
            pass

    lines = [re.sub(r"^[\-\*\d\.\)\s]+", "", ln).strip(' "\'') for ln in cleaned.splitlines()]
    return [ln for ln in lines if 1 <= len(ln) <= 16][:limit]


def load_agent_queue(queue_path: Path | None = None) -> list[dict[str, Any]]:
    """讀取對話 Agent 匯入的待處理圖片與候選詞條佇列。"""
    path = queue_path or AGENT_QUEUE_PATH
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    items = data.get("items", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    valid: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        img_path = Path(str(item.get("image_path", "")))
        if not img_path.exists() or not img_path.is_file():
            continue
        valid.append(
            {
                "index": idx,
                "name": img_path.name,
                "image_path": str(img_path),
                "person": str(item.get("person", "")),
                "recommended_text": str(item.get("recommended_text", "")),
                "suggestions": [str(s) for s in item.get("suggestions", []) if str(s).strip()],
                "crop": item.get("crop"),
                "mode": str(item.get("mode", "original")),
                "note": str(item.get("note", "")),
            }
        )
    return valid
