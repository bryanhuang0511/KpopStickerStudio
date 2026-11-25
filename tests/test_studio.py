"""KpopStickerStudio 核心引擎與本機 HTTP API 測試。"""

from __future__ import annotations

import base64
import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sticker_maker.ai_suggest import _parse_caption_list, load_agent_queue
from sticker_maker.config import StickerConfig
from sticker_maker.cutout import add_sticker_outline, evaluate_mask_quality
from sticker_maker.naming import build_output_path, sanitize_token
from sticker_maker.renderer import StickerOptions, render_sticker, save_lossless
from sticker_maker.server import make_handler


def _make_sample_image(path: Path, size: tuple[int, int] = (600, 800)) -> Path:
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[:, :, 0] = 60
    arr[:, :, 1] = 120
    arr[:, :, 2] = 200
    arr[150:650, 150:450] = [235, 195, 175]
    Image.fromarray(arr, mode="RGB").save(path, format="PNG")
    return path


def _make_data_url(size: tuple[int, int] = (400, 400)) -> str:
    img = Image.new("RGB", size, (80, 140, 210))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def test_naming_person_and_text_with_collision_protection(tmp_path: Path) -> None:
    p1 = build_output_path(tmp_path, "沅禧", "在幹嘛")
    assert p1.name == "沅禧_在幹嘛.png"
    p1.write_bytes(b"first")

    p2 = build_output_path(tmp_path, "沅禧", "在幹嘛")
    assert p2.name == "沅禧_在幹嘛_02.png"

    assert sanitize_token('Ahyeon:/?*<>|"') == "Ahyeon"


def test_original_mode_preserves_pixels_without_upscaling(tmp_path: Path) -> None:
    src = _make_sample_image(tmp_path / "src.png", size=(600, 800))
    res = render_sticker(src, StickerOptions(mode="original", text="", max_size=1024))
    assert res.output_size == (600, 800)
    assert np.array_equal(
        np.array(Image.open(src).convert("RGB")),
        np.array(res.image.convert("RGB")),
    )


def test_meme_bar_preserves_original_pixels(tmp_path: Path) -> None:
    src = _make_sample_image(tmp_path / "src.png", size=(500, 500))
    res = render_sticker(src, StickerOptions(mode="meme-bar", bar_position="bottom", text="笑死", max_size=500))
    assert res.output_size[0] == 500 and res.output_size[1] > 500
    assert np.array_equal(
        np.array(Image.open(src).convert("RGB")),
        np.array(res.image.crop((0, 0, 500, 500)).convert("RGB")),
    )


def test_cutout_outline_and_quality_guard() -> None:
    rgba = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    arr = np.array(rgba)
    arr[50:150, 60:140] = [255, 100, 100, 255]
    outlined = add_sticker_outline(Image.fromarray(arr, mode="RGBA"), outline_width=8, add_shadow=True)
    assert outlined.width > 200 and outlined.height > 200
    assert evaluate_mask_quality(np.zeros((100, 100), dtype=np.uint8)).warning is not None


def test_caption_parser_and_agent_queue(tmp_path: Path) -> None:
    assert _parse_caption_list('```json\n["在幹嘛", "偷看", "笑死"]\n```') == ["在幹嘛", "偷看", "笑死"]
    img = _make_sample_image(tmp_path / "sample.png", (300, 300))
    q_file = tmp_path / "agent_queue.json"
    q_file.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "image_path": str(img),
                        "person": "沅禧",
                        "recommended_text": "在幹嘛",
                        "suggestions": ["在幹嘛", "偷看", "嗨～"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    loaded = load_agent_queue(q_file)
    assert len(loaded) == 1
    assert loaded[0]["person"] == "沅禧"
    assert loaded[0]["suggestions"] == ["在幹嘛", "偷看", "嗨～"]


def test_http_server_render_and_save_api(tmp_path: Path) -> None:
    cfg = StickerConfig(default_output_dir=tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cfg, port_override=None))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/api/config") as r:
            cfg_data = json.loads(r.read().decode("utf-8"))
            assert cfg_data["default_output_dir"] == str(tmp_path)

        payload = json.dumps(
            {
                "image_data": _make_data_url((400, 400)),
                "person": "沅禧",
                "text": "收到！",
                "mode": "original",
                "crop": [0.0, 0.0, 1.0, 1.0],
                "format": "png",
                "output_dir": str(tmp_path),
            }
        ).encode("utf-8")

        req_render = urllib.request.Request(f"{base}/api/render", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req_render) as r:
            res_render = json.loads(r.read().decode("utf-8"))
            assert res_render["ok"] is True
            assert res_render["output_size"] == [400, 400]
            assert res_render["image_data"].startswith("data:image/png;base64,")

        req_save = urllib.request.Request(f"{base}/api/save", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req_save) as r:
            res_save = json.loads(r.read().decode("utf-8"))
            assert res_save["ok"] is True
            assert res_save["filename"] == "沅禧_收到！.png"
            assert (tmp_path / "沅禧_收到！.png").exists()

        req_agy = urllib.request.Request(
            f"{base}/api/agy/prepare",
            data=json.dumps({"image_data": _make_data_url((300, 300)), "person": "沅禧"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_agy) as r:
            res_agy = json.loads(r.read().decode("utf-8"))
            assert res_agy["ok"] is True
            assert "ask_agy.png" in res_agy["prompt"]
            assert Path(res_agy["image_path"]).exists()
    finally:
        server.shutdown()
        server.server_close()
