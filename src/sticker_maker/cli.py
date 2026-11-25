"""命令列介面（供 AI Skill 自動呼叫與批次處理腳本共用）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .naming import build_output_path
from .renderer import StickerOptions, render_sticker, save_lossless


def _parse_floats(raw: str | None, expected: int) -> tuple[float, ...] | None:
    if not raw:
        return None
    parts = [float(x.strip()) for x in raw.split(",")]
    if len(parts) != expected:
        raise argparse.ArgumentTypeError(f"需要 {expected} 個逗號分隔浮點數，收到：{raw}")
    return tuple(parts)


def _parse_rgb(raw: str) -> tuple[int, int, int]:
    cleaned = raw.strip().lstrip("#")
    if len(cleaned) != 6:
        raise argparse.ArgumentTypeError(f"描邊色需為 6 碼十六進位（例如 #FFFFFF），收到：{raw}")
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def build_parser() -> argparse.ArgumentParser:
    cfg = load_config()
    p = argparse.ArgumentParser(
        prog="make_sticker",
        description="KpopStickerStudio 無損貼圖與梗圖核心命令列工具",
    )
    p.add_argument("input", type=Path, help="來源圖片路徑")
    p.add_argument("--person", default="", help="成員或人物名稱（檔名：人_字.png）")
    p.add_argument("--text", default="", help="貼圖文字（可用 \\n 換行）")
    p.add_argument("--mode", choices=["original", "cutout", "meme-bar"], default=cfg.default_mode, help="版型模式")
    p.add_argument("--out-dir", type=Path, default=cfg.default_output_dir, help="輸出資料夾")
    p.add_argument("--format", dest="fmt", choices=["png", "webp", "jpg"], default=cfg.default_format, help="輸出格式")
    p.add_argument("--max-size", type=int, default=None, help="最長邊像素上限（0 表示不縮小保留原解析度）")
    p.add_argument("--crop", default=None, help="歸一化裁切框 x1,y1,x2,y2（0.0~1.0）")
    p.add_argument("--aspect", choices=["free", "1:1", "4:3", "3:4", "16:9"], default="free", help="目標比例")
    p.add_argument("--crop-anchor", choices=["top", "center", "bottom"], default="top", help="自動比例裁切對齊基準")
    p.add_argument("--radius", type=int, default=0, help="圓角半徑像素")
    p.add_argument("--cutout-model", default=cfg.default_cutout_model, help="去背模型")
    p.add_argument("--outline-width", type=int, default=cfg.default_outline_width, help="去背白邊寬度（0=關閉）")
    p.add_argument("--outline-color", default="#FFFFFF", help="去背描邊色")
    p.add_argument("--no-shadow", action="store_true", help="關閉去背微陰影")
    p.add_argument("--square-canvas", action="store_true", help="去背模式置中於正方形畫布")
    p.add_argument("--bg-fill", default=None, help="去背模式補實底色（例：#FFFFFF）")
    p.add_argument("--bar-pos", choices=["top", "bottom"], default="bottom", help="meme-bar 文字條位置")
    p.add_argument("--bar-bg", default="#FFFFFF", help="meme-bar 背景色")
    p.add_argument("--font", default=cfg.default_font_preset, help="字體（bold / heavy / sans / serif / kai / kr）")
    p.add_argument("--font-file", default=None, help="自訂字體檔路徑")
    p.add_argument("--style", default=cfg.default_text_style, help="文字配色（classic / heavy / yellow / pink / blue / dark / bar）")
    p.add_argument("--text-fill", default=None, help="自訂字色")
    p.add_argument("--text-stroke", default=None, help="自訂描邊色")
    p.add_argument(
        "--pos",
        choices=["bottom", "top", "center", "top-left", "top-right", "bottom-left", "bottom-right"],
        default=cfg.default_text_position,
        help="文字位置",
    )
    p.add_argument("--text-xy", default=None, help="精準文字中心歸一化座標 x,y")
    p.add_argument("--text-scale", type=float, default=cfg.default_text_scale, help="字高相對短邊比例")
    p.add_argument("--stroke-ratio", type=float, default=None, help="描邊相對字高比例")
    p.add_argument("--angle", type=float, default=0.0, help="文字微旋轉角度")
    p.add_argument("--overwrite", action="store_true", help="若目標同名則覆蓋")
    p.add_argument("--json", action="store_true", help="以 JSON 輸出執行結果")
    return p


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"找不到來源圖片：{args.input}", file=sys.stderr)
        return 1

    max_size = args.max_size
    if max_size is None:
        max_size = cfg.default_cutout_max_size if args.mode == "cutout" else cfg.default_max_size

    crop = _parse_floats(args.crop, 4)
    text_xy = _parse_floats(args.text_xy, 2)
    text_decoded = args.text.replace("\\n", "\n")

    options = StickerOptions(
        mode=args.mode,
        text=text_decoded,
        crop=crop,  # type: ignore[arg-type]
        aspect=args.aspect,
        crop_anchor=args.crop_anchor,
        max_size=max_size,
        radius=args.radius,
        cutout_model=args.cutout_model,
        outline_width=args.outline_width,
        outline_color=_parse_rgb(args.outline_color),
        shadow=not args.no_shadow,
        square_canvas=args.square_canvas,
        bar_position=args.bar_pos,
        bar_bg=args.bar_bg,
        font_preset=args.font,
        custom_font=args.font_file,
        text_style=args.style,
        text_fill=args.text_fill,
        text_stroke=args.text_stroke,
        text_pos=args.pos,
        text_xy=text_xy,  # type: ignore[arg-type]
        text_scale=args.text_scale,
        stroke_ratio=args.stroke_ratio,
        text_angle=args.angle,
        bg_fill=args.bg_fill,
    )

    result = render_sticker(args.input, options)
    output_path = build_output_path(
        output_dir=args.out_dir,
        person=args.person,
        text=text_decoded,
        ext=args.fmt,
        separator=cfg.naming_separator,
        overwrite=args.overwrite,
    )
    save_lossless(result.image, output_path, fmt=args.fmt)

    payload = {
        "output_path": str(output_path),
        "mode": args.mode,
        "format": args.fmt,
        "original_size": list(result.original_size),
        "output_size": list(result.output_size),
        "file_size_kb": round(output_path.stat().st_size / 1024, 1),
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

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"已完成：{output_path}")
        print(f"尺寸：{result.original_size[0]}x{result.original_size[1]} -> {result.output_size[0]}x{result.output_size[1]} ({payload['file_size_kb']} KB)")
        if result.cutout_quality and result.cutout_quality.warning:
            print(f"[去背提醒] {result.cutout_quality.warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
