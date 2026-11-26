"""100% 像素保留之無損貼圖與梗圖渲染引擎（僅裁切、縮放、可選去背、圓角、梗圖條、壓字）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .cutout import CutoutQuality, add_sticker_outline, remove_background
from .fonts import TEXT_STYLES, find_unsupported_chars, resolve_font


@dataclass(frozen=True)
class StickerOptions:
    mode: str = "original"  # original | cutout | meme-bar
    text: str = ""
    crop: tuple[float, float, float, float] | None = None  # 歸一化 (x1, y1, x2, y2)
    aspect: str = "free"  # free | 1:1 | 4:3 | 3:4 | 16:9
    crop_anchor: str = "top"  # top | center | bottom
    max_size: int = 1024  # 0 表示保留原裁切解析度，絕不放大
    radius: int = 0
    cutout_model: str = "birefnet-portrait"
    outline_width: int = 8
    outline_color: tuple[int, int, int] = (255, 255, 255)
    shadow: bool = True
    square_canvas: bool = False
    bar_position: str = "bottom"  # top | bottom
    bar_bg: str = "#FFFFFF"
    font_preset: str = "bold"
    custom_font: str | None = None
    text_style: str = "classic"
    text_fill: str | None = None
    text_stroke: str | None = None
    text_pos: str = "bottom"  # bottom | top | center | top-left | top-right | bottom-left | bottom-right
    text_xy: tuple[float, float] | None = None  # 歸一化 (cx, cy)
    text_scale: float = 0.11
    stroke_ratio: float | None = None
    text_angle: float = 0.0
    bg_fill: str | None = None
    auto_trim: bool = False


@dataclass(frozen=True)
class RenderResult:
    image: Image.Image
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    cutout_quality: CutoutQuality | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


def detect_uniform_border_crop(image: Image.Image) -> tuple[int, int, int, int]:
    """偵測純白或純黑外框（常見於限動/SNS截圖或黑邊），回傳有效內容像素框 (x1, y1, x2, y2)。"""
    arr = np.asarray(image.convert("RGB"))
    h, w, _ = arr.shape

    def is_uniform_line(line: np.ndarray) -> bool:
        mean_val = line.mean(axis=0)
        std_val = line.std(axis=0).max()
        is_white = bool((mean_val > 250).all() and std_val < 2.5)
        is_black = bool((mean_val < 8).all() and std_val < 2.5)
        return is_white or is_black

    x1, x2 = 0, w
    while x1 < w // 3 and is_uniform_line(arr[:, x1, :]):
        x1 += 1
    while x2 > (2 * w) // 3 and is_uniform_line(arr[:, x2 - 1, :]):
        x2 -= 1

    y1, y2 = 0, h
    while y1 < h // 3 and is_uniform_line(arr[y1, x1:x2, :]):
        y1 += 1
    while y2 > (2 * h) // 3 and is_uniform_line(arr[y2 - 1, x1:x2, :]):
        y2 -= 1

    if (x2 - x1) < w * 0.4 or (y2 - y1) < h * 0.4:
        return (0, 0, w, h)
    return (x1, y1, x2, y2)


def compute_square_crop_norm(
    w: int,
    h: int,
    content_box: tuple[int, int, int, int],
    y_bias: float = 0.05,
    x_bias: float = 0.5,
    zoom: float = 1.0,
) -> tuple[float, float, float, float]:
    """在有效內容框內計算歸一化 1:1 裁切座標（預設偏上保留頭部與手勢）。"""
    cx1, cy1, cx2, cy2 = content_box
    cw = cx2 - cx1
    ch = cy2 - cy1
    side = min(cw, ch) * zoom
    side = max(64.0, min(float(cw), float(ch), side))

    left = cx1 + (cw - side) * x_bias
    top = cy1 + (ch - side) * y_bias
    left = max(float(cx1), min(float(cx2) - side, left))
    top = max(float(cy1), min(float(cy2) - side, top))

    return (
        round(left / w, 4),
        round(top / h, 4),
        round((left + side) / w, 4),
        round((top + side) / h, 4),
    )


def apply_normalized_crop(
    image: Image.Image,
    crop: tuple[float, float, float, float] | None,
) -> Image.Image:
    if crop is None:
        return image
    x1, y1, x2, y2 = crop
    if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
        raise ValueError(f"裁切座標必須滿足 0 <= x1 < x2 <= 1 且 0 <= y1 < y2 <= 1，收到：{crop}")
    w, h = image.size
    box = (
        max(0, round(x1 * w)),
        max(0, round(y1 * h)),
        min(w, round(x2 * w)),
        min(h, round(y2 * h)),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("裁切後影像尺寸無效。")
    return image.crop(box)


def apply_aspect_crop(image: Image.Image, aspect: str, anchor: str = "top") -> Image.Image:
    if aspect == "free":
        return image
    ratios = {
        "1:1": 1.0,
        "4:3": 4.0 / 3.0,
        "3:4": 3.0 / 4.0,
        "16:9": 16.0 / 9.0,
    }
    if aspect not in ratios:
        raise ValueError(f"不支援的長寬比：{aspect}，可選：{', '.join(ratios)}")

    target = ratios[aspect]
    w, h = image.size
    current = w / h
    if abs(current - target) < 1e-4:
        return image

    if current > target:
        new_w = round(h * target)
        left = (w - new_w) // 2
        return image.crop((left, 0, left + new_w, h))

    new_h = round(w / target)
    if anchor == "top":
        top = round((h - new_h) * 0.15)
    elif anchor == "bottom":
        top = h - new_h
    else:
        top = (h - new_h) // 2
    top = max(0, min(h - new_h, top))
    return image.crop((0, top, w, top + new_h))


def resize_down_only(image: Image.Image, max_size: int) -> Image.Image:
    """僅當原圖大於 max_size 時以 Lanczos 無損等比縮小；絕不強行放大失真。"""
    if max_size <= 0:
        return image
    w, h = image.size
    longest = max(w, h)
    if longest <= max_size:
        return image
    scale = max_size / longest
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def apply_rounded_corners(image: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return image
    rgba = image.convert("RGBA")
    w, h = rgba.size
    r = min(radius, w // 2, h // 2)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    out = rgba.copy()
    existing_alpha = out.getchannel("A")
    combined = Image.composite(existing_alpha, Image.new("L", (w, h), 0), mask)
    out.putalpha(combined)
    return out


def trim_transparent_bounds(image: Image.Image, margin: int = 8) -> Image.Image:
    rgba = image.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        return rgba
    x1 = max(0, bbox[0] - margin)
    y1 = max(0, bbox[1] - margin)
    x2 = min(rgba.width, bbox[2] + margin)
    y2 = min(rgba.height, bbox[3] + margin)
    return rgba.crop((x1, y1, x2, y2))


def fit_to_square_canvas(image: Image.Image, size: int, padding_ratio: float = 0.04) -> Image.Image:
    rgba = image.convert("RGBA")
    pad = round(size * padding_ratio)
    inner = max(1, size - pad * 2)
    fitted = resize_down_only(rgba, inner)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - fitted.width) // 2, (size - fitted.height) // 2)
    canvas.alpha_composite(fitted, dest=offset)
    return canvas


def _measure_multiline(
    text: str,
    font,
    stroke_width: int,
    spacing: int,
) -> tuple[int, int, tuple[int, int, int, int]]:
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy.multiline_textbbox(
        (0, 0),
        text,
        font=font,
        align="center",
        spacing=spacing,
        stroke_width=stroke_width,
    )
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1]), bbox


def _draw_text_overlay(
    canvas: Image.Image,
    text: str,
    options: StickerOptions,
    target_box: tuple[int, int, int, int] | None = None,
) -> tuple[Image.Image, list[str]]:
    if not text.strip():
        return canvas, []

    rgba = canvas.convert("RGBA")
    w, h = rgba.size
    style = TEXT_STYLES.get(options.text_style, TEXT_STYLES["classic"])
    fill_color = options.text_fill or style.fill
    stroke_color = options.text_stroke or style.stroke
    s_ratio = style.stroke_ratio if options.stroke_ratio is None else options.stroke_ratio

    box = target_box or (0, 0, w, h)
    box_w = box[2] - box[0]
    box_h = box[3] - box[1]
    margin_x = max(12, round(box_w * 0.055))
    margin_y = max(12, round(box_h * 0.05))
    max_text_w = max(40, box_w - margin_x * 2)
    max_text_h = max(32, round(box_h * (0.82 if target_box else 0.42)))

    base_font_size = max(18, round(min(w, h) * options.text_scale))
    font_size = base_font_size
    while font_size >= 14:
        font = resolve_font(font_size, preset=options.font_preset, custom_font_path=options.custom_font, text=text)
        stroke_w = max(0, round(font_size * s_ratio))
        spacing = max(4, round(font_size * 0.16))
        tw, th, bbox = _measure_multiline(text, font, stroke_w, spacing)
        if tw <= max_text_w and th <= max_text_h:
            break
        font_size -= 2
    else:
        font = resolve_font(14, preset=options.font_preset, custom_font_path=options.custom_font, text=text)
        stroke_w = max(0, round(14 * s_ratio))
        spacing = 4
        tw, th, bbox = _measure_multiline(text, font, stroke_w, spacing)

    pad = stroke_w + 8
    txt_layer = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_layer)
    txt_draw.multiline_text(
        (pad - bbox[0], pad - bbox[1]),
        text,
        font=font,
        fill=fill_color,
        align="center",
        spacing=spacing,
        stroke_width=stroke_w,
        stroke_fill=stroke_color if stroke_w > 0 else None,
    )

    if abs(options.text_angle) > 0.1:
        txt_layer = txt_layer.rotate(options.text_angle, resample=Image.Resampling.BICUBIC, expand=True)

    lw, lh = txt_layer.size

    if target_box is not None:
        cx = box[0] + box_w // 2
        cy = box[1] + box_h // 2
    elif options.text_xy is not None:
        cx = round(options.text_xy[0] * w)
        cy = round(options.text_xy[1] * h)
    else:
        pos = options.text_pos
        if pos == "top":
            cx, cy = w // 2, margin_y + lh // 2
        elif pos == "center":
            cx, cy = w // 2, h // 2
        elif pos == "top-left":
            cx, cy = margin_x + lw // 2, margin_y + lh // 2
        elif pos == "top-right":
            cx, cy = w - margin_x - lw // 2, margin_y + lh // 2
        elif pos == "bottom-left":
            cx, cy = margin_x + lw // 2, h - margin_y - lh // 2
        elif pos == "bottom-right":
            cx, cy = w - margin_x - lw // 2, h - margin_y - lh // 2
        else:
            cx, cy = w // 2, h - margin_y - lh // 2

    dest_x = max(0, min(w - lw, cx - lw // 2))
    dest_y = max(0, min(h - lh, cy - lh // 2))

    rgba.alpha_composite(txt_layer, dest=(dest_x, dest_y))
    unsupported = find_unsupported_chars(text, font)
    warnings = [f"字型不支援字元（將顯示缺字方框）：{''.join(unsupported)}"] if unsupported else []
    return rgba, warnings


def render_sticker_from_image(raw_image: Image.Image, options: StickerOptions) -> RenderResult:
    """從 PIL Image 直接執行無損渲染管線（供檔案路徑與 HTTP 記憶體上傳共用）。"""
    img = ImageOps.exif_transpose(raw_image).convert("RGBA")
    original_size = img.size
    if options.crop is not None:
        img = apply_normalized_crop(img, options.crop)
    elif options.auto_trim:
        img = img.crop(detect_uniform_border_crop(img))
    img = apply_aspect_crop(img, options.aspect, anchor=options.crop_anchor)

    cutout_quality: CutoutQuality | None = None
    warnings: list[str] = []

    if options.mode == "cutout":
        cutout_img, cutout_quality = remove_background(img, model_name=options.cutout_model)
        cutout_img = trim_transparent_bounds(cutout_img, margin=6)
        if options.max_size > 0:
            inner_target = max(64, options.max_size - (options.outline_width * 2 + 28))
            cutout_img = resize_down_only(cutout_img, inner_target)
        out = add_sticker_outline(
            cutout_img,
            outline_width=options.outline_width,
            outline_color=options.outline_color,
            add_shadow=options.shadow,
        )
        out = trim_transparent_bounds(out, margin=4)
        if options.square_canvas and options.max_size > 0:
            out = fit_to_square_canvas(out, size=options.max_size)
        elif options.max_size > 0:
            out = resize_down_only(out, options.max_size)
        if options.bg_fill:
            bg = Image.new("RGBA", out.size, options.bg_fill)
            bg.alpha_composite(out)
            out = bg
        out, warnings = _draw_text_overlay(out, options.text, options)

    elif options.mode == "meme-bar":
        img = resize_down_only(img, options.max_size)
        w, h = img.size
        line_count = max(1, len(options.text.splitlines()))
        bar_h = max(round(h * 0.19), round(min(w, h) * options.text_scale * 1.45 * line_count))
        out = Image.new("RGBA", (w, h + bar_h), options.bar_bg)
        if options.bar_position == "top":
            out.paste(img, (0, bar_h))
            text_box = (0, 0, w, bar_h)
        else:
            out.paste(img, (0, 0))
            text_box = (0, h, w, h + bar_h)
        bar_opts = StickerOptions(
            **{
                **options.__dict__,
                "text_style": "bar" if options.text_style == "classic" and options.text_fill is None else options.text_style,
            }
        )
        out, warnings = _draw_text_overlay(out, options.text, bar_opts, target_box=text_box)
        if options.radius > 0:
            out = apply_rounded_corners(out, options.radius)

    elif options.mode == "original":
        out = resize_down_only(img, options.max_size)
        if options.radius > 0:
            out = apply_rounded_corners(out, options.radius)
        out, warnings = _draw_text_overlay(out, options.text, options)
    else:
        raise ValueError(f"不支援的模式：{options.mode}，可選：original | cutout | meme-bar")

    return RenderResult(
        image=out,
        original_size=original_size,
        output_size=out.size,
        cutout_quality=cutout_quality,
        warnings=tuple(warnings),
    )


def render_sticker(image_path: Path, options: StickerOptions) -> RenderResult:
    """從本機路徑讀取圖片並執行無損渲染。"""
    with Image.open(image_path) as raw:
        return render_sticker_from_image(raw, options)


def encode_lossless_bytes(image: Image.Image, fmt: str = "png") -> bytes:
    """編碼為無損 PNG／無損 WebP／高品質 JPG 位元組。"""
    clean_fmt = fmt.lower().lstrip(".")
    buf = BytesIO()
    if clean_fmt == "png":
        image.save(buf, format="PNG", compress_level=6, optimize=True)
    elif clean_fmt == "webp":
        image.save(buf, format="WEBP", lossless=True, quality=100, method=6)
    elif clean_fmt in ("jpg", "jpeg"):
        bg = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        bg.paste(rgba, mask=rgba.getchannel("A"))
        bg.save(buf, format="JPEG", quality=95, subsampling=0, optimize=True)
    else:
        raise ValueError(f"不支援的輸出格式：{fmt}")
    return buf.getvalue()


def save_lossless(image: Image.Image, output_path: Path, fmt: str = "png") -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = encode_lossless_bytes(image, fmt=fmt)
    output_path.write_bytes(data)
    return output_path
