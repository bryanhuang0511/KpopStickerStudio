"""批次無損貼圖管線與視覺驗收拼圖產生器。"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .config import StickerConfig, load_config
from .naming import build_output_path
from .renderer import (
    StickerOptions,
    compute_square_crop_norm,
    detect_uniform_border_crop,
    render_sticker,
    save_lossless,
)


def _resolve_job_out_dir(job: dict[str, Any], default_out_dir: Path) -> Path:
    if job.get("out_dir"):
        return Path(job["out_dir"]).expanduser()
    group = str(job.get("group", "")).strip()
    person = str(job.get("person", "")).strip()
    if group and person:
        return default_out_dir / group / person
    if person:
        return default_out_dir / person
    return default_out_dir


def _build_job_options(job: dict[str, Any], cfg: StickerConfig) -> StickerOptions:
    src = Path(job["input"])
    mode = job.get("mode", cfg.default_mode)
    text = str(job.get("text", "")).replace("\\n", "\n")

    with Image.open(src) as raw:
        im = ImageOps.exif_transpose(raw)
        w, h = im.size
        content_box = detect_uniform_border_crop(im)

    if job.get("crop") is not None:
        crop = tuple(float(v) for v in job["crop"])
    elif mode == "cutout":
        crop = (
            round(content_box[0] / w, 4),
            round(content_box[1] / h, 4),
            round(content_box[2] / w, 4),
            round(content_box[3] / h, 4),
        )
    else:
        crop = compute_square_crop_norm(
            w,
            h,
            content_box,
            y_bias=float(job.get("y_bias", 0.05)),
            x_bias=float(job.get("x_bias", 0.5)),
            zoom=float(job.get("zoom", 1.0)),
        )

    max_size = job.get("max_size")
    if max_size is None:
        max_size = cfg.default_cutout_max_size if mode == "cutout" else cfg.default_max_size

    return StickerOptions(
        mode=mode,
        text=text,
        crop=crop,  # type: ignore[arg-type]
        aspect="free" if mode == "cutout" else job.get("aspect", "1:1"),
        max_size=int(max_size),
        font_preset=job.get("font", cfg.default_font_preset),
        text_style=job.get("style", cfg.default_text_style),
        text_pos=job.get("pos", cfg.default_text_position),
        text_scale=float(job.get("text_scale", cfg.default_text_scale)),
        square_canvas=bool(job.get("square_canvas", mode == "cutout")),
    )


def build_verification_sheet(items: list[tuple[Path, str]], out_path: Path, cols: int = 4) -> Path:
    """將批次產出的貼圖縮圖排成帶檔名與尺寸標籤的視覺驗收表。"""
    if not items:
        raise ValueError("驗收拼圖至少需要 1 張貼圖。")
    rows = math.ceil(len(items) / cols)
    cell_w, cell_h = 320, 355
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), (30, 32, 36))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 14)
    except Exception:
        font = ImageFont.load_default()

    for idx, (img_path, label) in enumerate(items):
        r, c = divmod(idx, cols)
        x0, y0 = c * cell_w, r * cell_h
        with Image.open(img_path) as sim:
            if sim.mode == "RGBA":
                bg = Image.new("RGB", sim.size, (50, 54, 62))
                bg.paste(sim, mask=sim.getchannel("A"))
                thumb = bg
            else:
                thumb = sim.convert("RGB")
            thumb.thumbnail((cell_w - 16, cell_h - 42))
            tw, th = thumb.size
            canvas.paste(thumb, (x0 + (cell_w - tw) // 2, y0 + 6 + (cell_h - 42 - th) // 2))
        draw.text((x0 + 8, y0 + cell_h - 32), label, fill=(240, 240, 240), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=90)
    return out_path


def run_batch_jobs(
    jobs: list[dict[str, Any]],
    default_out_dir: Path | None = None,
    verify_sheet_path: Path | None = None,
) -> list[dict[str, Any]]:
    """依 JSON 工作清單批次產出無損貼圖並可選輸出視覺驗收拼圖。"""
    cfg = load_config()
    base_out = default_out_dir or cfg.default_output_dir
    results: list[dict[str, Any]] = []
    sheet_items: list[tuple[Path, str]] = []

    for job in jobs:
        src = Path(job["input"])
        if not src.exists():
            raise FileNotFoundError(f"找不到來源圖片：{src}")

        out_dir = _resolve_job_out_dir(job, base_out)
        person = str(job.get("person", ""))
        fmt = str(job.get("format", cfg.default_format))
        options = _build_job_options(job, cfg)
        rendered = render_sticker(src, options)

        out_path = build_output_path(
            output_dir=out_dir,
            person=person,
            text=options.text,
            ext=fmt,
            separator=cfg.naming_separator,
            overwrite=bool(job.get("overwrite", True)),
        )
        save_lossless(rendered.image, out_path, fmt=fmt)

        entry = {
            "output_path": str(out_path),
            "output_size": list(rendered.output_size),
            "file_size_kb": round(out_path.stat().st_size / 1024, 1),
            "warnings": list(rendered.warnings),
        }
        results.append(entry)
        sheet_items.append((out_path, f"{out_path.name} ({rendered.output_size[0]}x{rendered.output_size[1]})"))

    if verify_sheet_path and sheet_items:
        build_verification_sheet(sheet_items, verify_sheet_path)

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make_batch", description="KpopStickerStudio 批次無損貼圖工具")
    parser.add_argument("manifest", type=Path, help="JSON 批次清單檔路徑")
    parser.add_argument("--out-dir", type=Path, default=None, help="覆蓋預設輸出根目錄")
    parser.add_argument("--verify-sheet", type=Path, default=None, help="輸出視覺驗收縮圖表路徑")
    parser.add_argument("--json", action="store_true", help="以 JSON 輸出完整結果")
    args = parser.parse_args(argv)

    if not args.manifest.exists():
        print(f"找不到批次清單：{args.manifest}", file=sys.stderr)
        return 1

    jobs = json.loads(args.manifest.read_text(encoding="utf-8"))
    results = run_batch_jobs(jobs, default_out_dir=args.out_dir, verify_sheet_path=args.verify_sheet)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print(f"OK: {item['output_path']} [{item['output_size'][0]}x{item['output_size'][1]}]")
            for warn in item["warnings"]:
                print(f"[字型提醒] {item['output_path']} -> {warn}")
        if args.verify_sheet:
            print(f"SHEET: {args.verify_sheet}")
    return 0
