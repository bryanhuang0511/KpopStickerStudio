"""可選離線 AI 去背、歐氏距離場平滑白邊與品質防呆檢測。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import distance_transform_edt, label


@dataclass(frozen=True)
class CutoutQuality:
    foreground_ratio: float
    fragment_count: int
    warning: str | None


_SESSION_CACHE: dict[str, object] = {}


def _get_session(model_name: str):
    if model_name not in _SESSION_CACHE:
        from rembg import new_session

        _SESSION_CACHE[model_name] = new_session(model_name)
    return _SESSION_CACHE[model_name]


def evaluate_mask_quality(alpha: np.ndarray) -> CutoutQuality:
    """檢查去背遮罩是否有明顯異常（過小、幾乎未去背、過度破碎）。"""
    binary = alpha > 128
    ratio = float(binary.mean())
    _, num_features = label(binary)

    warning: str | None = None
    if ratio < 0.04:
        warning = "去背前景過小（<4%），人物可能被誤切，建議切換備援模型或切回原圖模式。"
    elif ratio > 0.92:
        warning = "背景幾乎未被去除（前景 >92%），建議切回原圖模式或切換備援模型。"
    elif num_features > 25:
        warning = f"遮罩碎片過多（{num_features} 塊），背景可能較複雜，建議檢視邊緣或改用原圖模式。"

    return CutoutQuality(
        foreground_ratio=round(ratio, 4),
        fragment_count=int(num_features),
        warning=warning,
    )


def remove_background(
    image: Image.Image,
    model_name: str = "birefnet-portrait",
) -> tuple[Image.Image, CutoutQuality]:
    """對輸入影像執行離線去背，僅產生 Alpha 遮罩並套回原始 RGB 像素（絕不修改原圖色彩）。"""
    from rembg import remove

    rgba = image.convert("RGBA")
    session = _get_session(model_name)
    mask_img = remove(rgba, session=session, only_mask=True)
    if not isinstance(mask_img, Image.Image):
        raise RuntimeError("去背引擎未回傳有效遮罩影像。")

    alpha_img = mask_img.convert("L").resize(rgba.size, Image.Resampling.LANCZOS)
    alpha_arr = np.array(alpha_img, dtype=np.uint8)
    quality = evaluate_mask_quality(alpha_arr)

    # 嚴格只替換 Alpha 通道，保留 100% 原始 RGB 像素（零修圖）
    result = rgba.copy()
    result.putalpha(alpha_img)
    return result, quality


def add_sticker_outline(
    cutout_rgba: Image.Image,
    outline_width: int = 8,
    outline_color: tuple[int, int, int] = (255, 255, 255),
    add_shadow: bool = True,
) -> Image.Image:
    """以歐氏距離場產生平滑圓潤的貼圖白邊與柔和微陰影，絕不改動人物本體像素。"""
    src = cutout_rgba.convert("RGBA")
    pad = max(outline_width + (14 if add_shadow else 4), 4)
    canvas_w = src.width + pad * 2
    canvas_h = src.height + pad * 2

    padded = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    padded.paste(src, (pad, pad))

    if outline_width <= 0 and not add_shadow:
        return padded

    alpha = np.array(padded.getchannel("A"), dtype=np.float32) / 255.0
    fg_mask = alpha > 0.35

    dist = distance_transform_edt(~fg_mask)
    feather = 1.5
    outline_alpha = np.clip((outline_width + feather - dist) / feather, 0.0, 1.0)
    outline_alpha = np.maximum(outline_alpha, alpha)
    outline_u8 = (outline_alpha * 255.0).astype(np.uint8)

    outline_layer = Image.new("RGBA", (canvas_w, canvas_h), (*outline_color, 0))
    outline_layer.putalpha(Image.fromarray(outline_u8, mode="L"))

    base = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    if add_shadow:
        shadow_alpha = Image.fromarray((outline_alpha * 95.0).astype(np.uint8), mode="L")
        shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(radius=max(3, outline_width // 2)))
        shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        shadow_layer.putalpha(shadow_alpha)
        shadow_offset = max(3, outline_width // 2)
        base.alpha_composite(shadow_layer, dest=(0, shadow_offset))

    base.alpha_composite(outline_layer)
    base.alpha_composite(padded)
    return base
