"""KpopStickerStudio 純無損貼圖引擎與 CLI 測試。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sticker_maker.batch import run_batch_jobs
from sticker_maker.cli import main as cli_main
from sticker_maker.config import load_config
from sticker_maker.cutout import add_sticker_outline, evaluate_mask_quality
from sticker_maker.fonts import find_unsupported_chars, resolve_font
from sticker_maker.naming import build_output_path, sanitize_token
from sticker_maker.renderer import (
    StickerOptions,
    compute_square_crop_norm,
    detect_uniform_border_crop,
    render_sticker,
)


def _make_sample_image(path: Path, size: tuple[int, int] = (600, 800)) -> Path:
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[:, :, 0] = 60
    arr[:, :, 1] = 120
    arr[:, :, 2] = 200
    arr[150:650, 150:450] = [235, 195, 175]
    Image.fromarray(arr, mode="RGB").save(path, format="PNG")
    return path


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


def test_cli_end_to_end_lossless_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = _make_sample_image(tmp_path / "in.png", size=(768, 1024))
    out_dir = tmp_path / "out"
    code = cli_main(
        [
            str(src),
            "--person",
            "沅禧",
            "--text",
            "在幹嘛",
            "--aspect",
            "1:1",
            "--out-dir",
            str(out_dir),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    out_file = Path(payload["output_path"])
    assert out_file.exists()
    assert out_file.name == "沅禧_在幹嘛.png"
    assert payload["output_size"] == [768, 768]


def test_detect_uniform_border_and_auto_trim(tmp_path: Path) -> None:
    arr = np.full((600, 800, 3), 255, dtype=np.uint8)
    arr[50:550, 150:650] = [40, 110, 190]
    bordered = Image.fromarray(arr, mode="RGB")

    box = detect_uniform_border_crop(bordered)
    assert box == (150, 50, 650, 550)

    crop = compute_square_crop_norm(800, 600, box, y_bias=0.05)
    assert crop == (0.1875, 0.0833, 0.8125, 0.9167)

    src = tmp_path / "bordered.png"
    bordered.save(src, format="PNG")
    res = render_sticker(src, StickerOptions(mode="original", text="", auto_trim=True, aspect="1:1"))
    assert res.output_size == (500, 500)


def test_find_unsupported_chars_flags_missing_emoji() -> None:
    font = resolve_font(48, preset="bold", text="切拜🙏")
    unsupported = find_unsupported_chars("切拜♡🙏", font)
    assert "切" not in unsupported
    assert "♡" not in unsupported
    assert "🙏" in unsupported


def test_run_batch_jobs_with_group_structure_and_sheet(tmp_path: Path) -> None:
    src = _make_sample_image(tmp_path / "ILLIT_Minju_01.png", size=(768, 1024))
    out_root = tmp_path / "stickers"
    sheet_path = tmp_path / "verify.jpg"

    results = run_batch_jobs(
        [
            {
                "input": str(src),
                "group": "ILLIT",
                "person": "Minju",
                "text": "收到！",
                "y_bias": 0.05,
            }
        ],
        default_out_dir=out_root,
        verify_sheet_path=sheet_path,
    )
    assert len(results) == 1
    out_file = Path(results[0]["output_path"])
    assert out_file == out_root / "ILLIT" / "Minju" / "Minju_收到！.png"
    assert out_file.exists()
    assert results[0]["output_size"] == [768, 768]
    assert sheet_path.exists()


def test_load_config_expands_user_home_dir() -> None:
    cfg = load_config()
    assert cfg.default_output_dir.is_absolute()
    assert "~" not in str(cfg.default_output_dir)
