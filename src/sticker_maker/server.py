"""極輕量本機 HTTP API 與前端靜態伺服器（純 Python 標準庫，免額外 Web 框架）。"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import socket
import subprocess
import threading
import time
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from PIL import Image

from .ai_suggest import find_gemini_api_key, load_agent_queue, suggest_captions_via_gemini
from .config import PROJECT_ROOT, StickerConfig, load_config
from .naming import build_output_path
from .renderer import StickerOptions, encode_lossless_bytes, render_sticker_from_image, save_lossless

WEB_DIR = PROJECT_ROOT / "web"
RUNTIME_DIR = PROJECT_ROOT / ".studio_runtime"
AGY_ASK_IMAGE = RUNTIME_DIR / "ask_agy.png"
AGY_ASK_META = RUNTIME_DIR / "ask_agy_meta.json"
AGY_REPLY_FILE = RUNTIME_DIR / "agy_reply.json"
_SAVED_TOKENS: dict[str, Path] = {}


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except Exception:
        return "127.0.0.1"


def _decode_data_url_image(data_url: str) -> Image.Image:
    if "," in data_url and data_url.startswith("data:"):
        _, b64_part = data_url.split(",", 1)
    else:
        b64_part = data_url
    raw = base64.b64decode(b64_part)
    img = Image.open(BytesIO(raw))
    img.load()
    return img


def _parse_rgb_hex(raw: str | None, default: tuple[int, int, int] = (255, 255, 255)) -> tuple[int, int, int]:
    if not raw:
        return default
    cleaned = raw.strip().lstrip("#")
    if len(cleaned) != 6:
        return default
    try:
        return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))
    except ValueError:
        return default


def _build_options_from_payload(payload: dict[str, Any], cfg: StickerConfig) -> StickerOptions:
    mode = str(payload.get("mode", cfg.default_mode))
    crop_raw = payload.get("crop")
    crop: tuple[float, float, float, float] | None = None
    if isinstance(crop_raw, list) and len(crop_raw) == 4:
        crop = (float(crop_raw[0]), float(crop_raw[1]), float(crop_raw[2]), float(crop_raw[3]))

    text_xy_raw = payload.get("text_xy")
    text_xy: tuple[float, float] | None = None
    if isinstance(text_xy_raw, list) and len(text_xy_raw) == 2:
        text_xy = (float(text_xy_raw[0]), float(text_xy_raw[1]))

    max_size_val = payload.get("max_size")
    if max_size_val is None or max_size_val == "":
        max_size = cfg.default_cutout_max_size if mode == "cutout" else cfg.default_max_size
    else:
        max_size = int(max_size_val)

    stroke_raw = payload.get("stroke_ratio")
    stroke_ratio = None if stroke_raw in (None, "") else float(stroke_raw)

    return StickerOptions(
        mode=mode,
        text=str(payload.get("text", "")),
        crop=crop,
        aspect=str(payload.get("aspect", "free")),
        crop_anchor=str(payload.get("crop_anchor", "top")),
        max_size=max_size,
        radius=int(payload.get("radius", 0)),
        cutout_model=str(payload.get("cutout_model", cfg.default_cutout_model)),
        outline_width=int(payload.get("outline_width", cfg.default_outline_width)),
        outline_color=_parse_rgb_hex(payload.get("outline_color"), (255, 255, 255)),
        shadow=bool(payload.get("shadow", cfg.default_shadow)),
        square_canvas=bool(payload.get("square_canvas", False)),
        bar_position=str(payload.get("bar_pos", "bottom")),
        bar_bg=str(payload.get("bar_bg", "#FFFFFF")),
        font_preset=str(payload.get("font", cfg.default_font_preset)),
        text_style=str(payload.get("style", cfg.default_text_style)),
        text_fill=payload.get("text_fill") or None,
        text_stroke=payload.get("text_stroke") or None,
        text_pos=str(payload.get("pos", cfg.default_text_position)),
        text_xy=text_xy,
        text_scale=float(payload.get("text_scale", cfg.default_text_scale)),
        stroke_ratio=stroke_ratio,
        text_angle=float(payload.get("angle", 0.0)),
        bg_fill=payload.get("bg_fill") or None,
    )


def make_handler(
    config: StickerConfig | None = None,
    port_override: int | None = None,
    heartbeat_state: dict[str, Any] | None = None,
):
    cfg = config or load_config()
    active_port = port_override or cfg.server_port

    def _touch_activity() -> None:
        if heartbeat_state is not None:
            heartbeat_state["last_seen"] = time.monotonic()
            heartbeat_state["bye_at"] = None

    class StudioHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            # 保持終端機介面乾淨
            return

        def _send_json(self, data: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _send_bytes(self, data: bytes, content_type: str, download_name: str | None = None) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if download_name:
                from urllib.parse import quote

                encoded = quote(download_name)
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{encoded}")
            self.end_headers()
            self.wfile.write(data)

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            if length > 60 * 1024 * 1024:
                raise ValueError("單張圖片請求超過 60MB 上限。")
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:
            _touch_activity()
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/config":
                lan_ip = get_lan_ip()
                self._send_json(
                    {
                        "default_output_dir": str(cfg.default_output_dir),
                        "default_mode": cfg.default_mode,
                        "default_format": cfg.default_format,
                        "default_max_size": cfg.default_max_size,
                        "default_cutout_max_size": cfg.default_cutout_max_size,
                        "default_cutout_model": cfg.default_cutout_model,
                        "fallback_cutout_model": cfg.fallback_cutout_model,
                        "default_outline_width": cfg.default_outline_width,
                        "default_font_preset": cfg.default_font_preset,
                        "default_text_style": cfg.default_text_style,
                        "default_text_scale": cfg.default_text_scale,
                        "default_stroke_ratio": cfg.default_stroke_ratio,
                        "quick_members": list(cfg.quick_members),
                        "quick_captions": cfg.quick_captions,
                        "gemini_available": bool(find_gemini_api_key()),
                        "lan_url": f"http://{lan_ip}:{active_port}",
                    }
                )
                return

            if path == "/api/agent-queue":
                items = load_agent_queue()
                self._send_json({"items": items, "count": len(items)})
                return

            if path == "/api/agy/reply":
                if not AGY_REPLY_FILE.exists():
                    self._send_json({"ok": True, "has_reply": False, "timestamp": 0, "captions": []})
                    return
                try:
                    data = json.loads(AGY_REPLY_FILE.read_text(encoding="utf-8"))
                    mtime = int(AGY_REPLY_FILE.stat().st_mtime * 1000)
                    ts = int(data.get("timestamp", mtime))
                    captions = [str(c).strip() for c in data.get("captions", []) if str(c).strip()]
                    self._send_json(
                        {
                            "ok": True,
                            "has_reply": bool(captions),
                            "timestamp": max(ts, mtime),
                            "person": str(data.get("person", "")),
                            "captions": captions,
                            "crop": data.get("crop"),
                            "note": str(data.get("note", "")),
                        }
                    )
                except Exception as exc:
                    self._send_json({"ok": False, "has_reply": False, "error": str(exc)})
                return

            if path == "/api/agent-image":
                qs = parse_qs(parsed.query)
                try:
                    idx = int(qs.get("index", ["-1"])[0])
                except ValueError:
                    self._send_json({"error": "無效索引"}, HTTPStatus.BAD_REQUEST)
                    return
                items = load_agent_queue()
                matched = next((it for it in items if it["index"] == idx), None)
                if not matched:
                    self._send_json({"error": "找不到對應佇列圖片"}, HTTPStatus.NOT_FOUND)
                    return
                img_path = Path(matched["image_path"])
                mime = mimetypes.guess_type(str(img_path))[0] or "application/octet-stream"
                self._send_bytes(img_path.read_bytes(), mime)
                return

            if path.startswith("/api/saved/"):
                token = path.removeprefix("/api/saved/").strip("/")
                file_path = _SAVED_TOKENS.get(token)
                if not file_path or not file_path.exists():
                    self._send_json({"error": "下載連結已過期或檔案不存在"}, HTTPStatus.NOT_FOUND)
                    return
                mime = mimetypes.guess_type(str(file_path))[0] or "image/png"
                self._send_bytes(file_path.read_bytes(), mime, download_name=file_path.name)
                return

            # 靜態前端檔案
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            target = (WEB_DIR / rel).resolve()
            if not str(target).startswith(str(WEB_DIR.resolve())) or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
                return
            mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if mime.startswith("text/") or mime == "application/javascript":
                mime = f"{mime}; charset=utf-8"
            self._send_bytes(target.read_bytes(), mime)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/ping":
                _touch_activity()
                self._send_json({"ok": True})
                return

            if path == "/api/bye":
                if heartbeat_state is not None:
                    heartbeat_state["bye_at"] = time.monotonic()
                self._send_json({"ok": True})
                return

            _touch_activity()

            try:
                payload = self._read_json_body()
            except Exception as exc:
                self._send_json({"error": f"請求解析失敗：{exc}"}, HTTPStatus.BAD_REQUEST)
                return

            if path == "/api/render":
                try:
                    image_data = payload.get("image_data")
                    if not image_data:
                        raise ValueError("缺少來源圖片資料。")
                    raw_img = _decode_data_url_image(image_data)
                    options = _build_options_from_payload(payload, cfg)
                    fmt = str(payload.get("format", cfg.default_format))
                    result = render_sticker_from_image(raw_img, options)
                    encoded = encode_lossless_bytes(result.image, fmt=fmt)
                    mime = "image/png" if fmt == "png" else ("image/webp" if fmt == "webp" else "image/jpeg")
                    data_url = f"data:{mime};base64,{base64.b64encode(encoded).decode('ascii')}"
                    self._send_json(
                        {
                            "ok": True,
                            "image_data": data_url,
                            "original_size": list(result.original_size),
                            "output_size": list(result.output_size),
                            "file_size_kb": round(len(encoded) / 1024, 1),
                            "cutout_quality": (
                                {
                                    "foreground_ratio": result.cutout_quality.foreground_ratio,
                                    "fragment_count": result.cutout_quality.fragment_count,
                                    "warning": result.cutout_quality.warning,
                                }
                                if result.cutout_quality
                                else None
                            ),
                        }
                    )
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            if path == "/api/save":
                try:
                    image_data = payload.get("image_data")
                    if not image_data:
                        raise ValueError("缺少來源圖片資料。")
                    raw_img = _decode_data_url_image(image_data)
                    options = _build_options_from_payload(payload, cfg)
                    fmt = str(payload.get("format", cfg.default_format))
                    out_dir_raw = str(payload.get("output_dir", "")).strip()
                    out_dir = Path(out_dir_raw) if out_dir_raw else cfg.default_output_dir
                    person = str(payload.get("person", ""))
                    overwrite = bool(payload.get("overwrite", False))

                    result = render_sticker_from_image(raw_img, options)
                    out_path = build_output_path(
                        output_dir=out_dir,
                        person=person,
                        text=options.text,
                        ext=fmt,
                        separator=cfg.naming_separator,
                        overwrite=overwrite,
                    )
                    save_lossless(result.image, out_path, fmt=fmt)
                    token = uuid.uuid4().hex[:12]
                    _SAVED_TOKENS[token] = out_path
                    lan_ip = get_lan_ip()
                    self._send_json(
                        {
                            "ok": True,
                            "output_path": str(out_path),
                            "filename": out_path.name,
                            "output_size": list(result.output_size),
                            "file_size_kb": round(out_path.stat().st_size / 1024, 1),
                            "download_url": f"http://{lan_ip}:{active_port}/api/saved/{token}",
                            "cutout_quality": (
                                {
                                    "foreground_ratio": result.cutout_quality.foreground_ratio,
                                    "fragment_count": result.cutout_quality.fragment_count,
                                    "warning": result.cutout_quality.warning,
                                }
                                if result.cutout_quality
                                else None
                            ),
                        }
                    )
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            if path == "/api/suggest":
                try:
                    image_data = payload.get("image_data")
                    if not image_data:
                        raise ValueError("請先貼上或選擇一張圖片。")
                    raw_img = _decode_data_url_image(image_data)
                    person = str(payload.get("person", ""))
                    res = suggest_captions_via_gemini(raw_img, person=person)
                    self._send_json(res)
                except Exception as exc:
                    self._send_json({"ok": False, "captions": [], "message": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            if path == "/api/agy/prepare":
                try:
                    image_data = payload.get("image_data")
                    if not image_data:
                        raise ValueError("請先在軟體中貼上或選擇一張圖片。")
                    raw_img = _decode_data_url_image(image_data)
                    person = str(payload.get("person", "")).strip()
                    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
                    raw_img.convert("RGBA").save(AGY_ASK_IMAGE, format="PNG", compress_level=4)
                    now_ms = int(time.time() * 1000)
                    AGY_ASK_META.write_text(
                        json.dumps(
                            {
                                "timestamp": now_ms,
                                "image_path": str(AGY_ASK_IMAGE),
                                "person": person,
                                "reply_path": str(AGY_REPLY_FILE),
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    who = f"（成員：{person}）" if person else ""
                    prompt_text = f"請幫我看這張貼圖素材配詞並寫回 KpopStickerStudio：{AGY_ASK_IMAGE}{who}"
                    self._send_json(
                        {
                            "ok": True,
                            "timestamp": now_ms,
                            "image_path": str(AGY_ASK_IMAGE),
                            "prompt": prompt_text,
                        }
                    )
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            if path == "/api/shutdown":
                self._send_json({"ok": True, "message": "伺服器關閉中"})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return

            if path == "/api/open-folder":
                out_dir_raw = str(payload.get("output_dir", "")).strip()
                target_dir = Path(out_dir_raw) if out_dir_raw else cfg.default_output_dir
                target_dir.mkdir(parents=True, exist_ok=True)
                if os.name == "nt":
                    subprocess.Popen(["explorer", str(target_dir)])
                self._send_json({"ok": True, "path": str(target_dir)})
                return

            self._send_json({"error": "未知 API 端點"}, HTTPStatus.NOT_FOUND)

    return StudioHandler


def run_server(
    host: str | None = None,
    port: int | None = None,
    open_browser: bool = True,
    auto_exit: bool = False,
) -> None:
    cfg = load_config()
    bind_host = host or cfg.server_host
    bind_port = port or cfg.server_port
    heartbeat_state: dict[str, Any] = {
        "last_seen": time.monotonic(),
        "bye_at": None,
        "started_at": time.monotonic(),
    }
    server = ThreadingHTTPServer((bind_host, bind_port), make_handler(cfg, bind_port, heartbeat_state))
    local_url = f"http://127.0.0.1:{bind_port}"
    lan_url = f"http://{get_lan_ip()}:{bind_port}"
    print("==============================================")
    print("  KpopStickerStudio 無損貼圖工坊已啟動")
    print(f"  本機網址：{local_url}")
    print(f"  手機區網：{lan_url}")
    print(f"  預設存檔：{cfg.default_output_dir}")
    print("  關閉視窗即可自動結束（0 背景殘留）")
    print("==============================================")

    if auto_exit:
        def _watchdog() -> None:
            while True:
                time.sleep(0.8)
                now = time.monotonic()
                bye_at = heartbeat_state.get("bye_at")
                last_seen = heartbeat_state["last_seen"]
                # 收到關閉視窗通知且 2.5 秒內無新請求（非 F5 重整），立即關閉
                if bye_at is not None and (now - bye_at) >= 2.5 and last_seen <= bye_at:
                    server.shutdown()
                    return
                # 保護：若視窗異常崩潰未送出 bye，連續 30 分鐘無任何互動才自動關閉（避免背景視窗節流誤關）
                if (now - heartbeat_state["started_at"]) > 60.0 and (now - last_seen) > 1800.0:
                    server.shutdown()
                    return

        threading.Thread(target=_watchdog, daemon=True).start()

    if open_browser:
        webbrowser.open(local_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止伺服器。")
    finally:
        server.server_close()
