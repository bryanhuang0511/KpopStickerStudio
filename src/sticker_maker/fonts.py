"""本機中／英／韓文字體解析與樣式配色管理。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

_HANGUL_RE = re.compile(r"[\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF]")

_USER_FONTS = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
_WIN_FONTS = Path(r"C:\Windows\Fonts")


@dataclass(frozen=True)
class TextStyle:
    fill: str
    stroke: str
    stroke_ratio: float = 0.068


TEXT_STYLES: dict[str, TextStyle] = {
    "classic": TextStyle(fill="#FFFFFF", stroke="#000000", stroke_ratio=0.068),
    "heavy": TextStyle(fill="#FFFFFF", stroke="#000000", stroke_ratio=0.11),
    "yellow": TextStyle(fill="#FFE838", stroke="#000000", stroke_ratio=0.08),
    "pink": TextStyle(fill="#FFFFFF", stroke="#FF4F93", stroke_ratio=0.09),
    "blue": TextStyle(fill="#FFFFFF", stroke="#1D63FF", stroke_ratio=0.09),
    "dark": TextStyle(fill="#111111", stroke="#FFFFFF", stroke_ratio=0.06),
    "bar": TextStyle(fill="#111111", stroke="#111111", stroke_ratio=0.0),
}


FONT_CANDIDATES: dict[str, list[tuple[Path, int | None]]] = {
    "bold": [
        (_WIN_FONTS / "NotoSansTC-VF.ttf", 650),
        (_WIN_FONTS / "msjhbd.ttc", None),
        (_WIN_FONTS / "msyhbd.ttc", None),
    ],
    "heavy": [
        (_WIN_FONTS / "NotoSansTC-VF.ttf", 900),
        (_WIN_FONTS / "msjhbd.ttc", None),
    ],
    "sans": [
        (_WIN_FONTS / "msjhbd.ttc", None),
        (_WIN_FONTS / "NotoSansTC-VF.ttf", 700),
    ],
    "serif": [
        (_USER_FONTS / "SourceHanSerifTW-Heavy.otf", None),
        (_USER_FONTS / "SourceHanSerifTC-Heavy.otf", None),
        (_USER_FONTS / "SourceHanSerifTW-Bold.otf", None),
        (_WIN_FONTS / "NotoSerifTC-VF.ttf", 900),
    ],
    "kai": [
        (_WIN_FONTS / "kaiu.ttf", None),
        (_WIN_FONTS / "STKAITI.TTF", None),
    ],
    "kr": [
        (_WIN_FONTS / "malgunbd.ttf", None),
        (_WIN_FONTS / "malgun.ttf", None),
    ],
}


def has_hangul(text: str) -> bool:
    return bool(_HANGUL_RE.search(text))


def resolve_font(
    size: int,
    preset: str = "bold",
    custom_font_path: str | None = None,
    text: str = "",
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """載入最合適的本機字體，若文字含韓文且指定預設不支援則優先切韓文粗體。"""
    if custom_font_path:
        p = Path(custom_font_path)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)

    effective_preset = preset
    if preset in ("bold", "heavy", "sans", "kai") and has_hangul(text):
        effective_preset = "kr"

    candidates = list(FONT_CANDIDATES.get(effective_preset, FONT_CANDIDATES["bold"]))
    candidates.extend(FONT_CANDIDATES["bold"])

    for font_path, var_weight in candidates:
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), size=size)
            if var_weight is not None and hasattr(font, "set_variation_by_axes"):
                try:
                    font.set_variation_by_axes([var_weight])
                except Exception:
                    pass
            return font

    return ImageFont.load_default()
