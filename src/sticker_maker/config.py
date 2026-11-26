"""組態讀取與預設規格定義。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass(frozen=True)
class StickerConfig:
    default_output_dir: Path = Path.home() / "Pictures" / "貼圖"
    default_mode: str = "original"
    default_format: str = "png"
    default_max_size: int = 1024
    default_cutout_max_size: int = 512
    default_cutout_model: str = "birefnet-portrait"
    fallback_cutout_model: str = "isnet-general-use"
    default_outline_width: int = 8
    default_shadow: bool = True
    default_font_preset: str = "bold"
    default_text_style: str = "classic"
    default_text_position: str = "bottom"
    default_text_scale: float = 0.11
    default_stroke_ratio: float = 0.068
    naming_separator: str = "_"


def load_config(config_path: Path | None = None) -> StickerConfig:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return StickerConfig()

    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    defaults = StickerConfig()
    return StickerConfig(
        default_output_dir=Path(data.get("default_output_dir", str(defaults.default_output_dir))).expanduser(),
        default_mode=str(data.get("default_mode", defaults.default_mode)),
        default_format=str(data.get("default_format", defaults.default_format)),
        default_max_size=int(data.get("default_max_size", defaults.default_max_size)),
        default_cutout_max_size=int(data.get("default_cutout_max_size", defaults.default_cutout_max_size)),
        default_cutout_model=str(data.get("default_cutout_model", defaults.default_cutout_model)),
        fallback_cutout_model=str(data.get("fallback_cutout_model", defaults.fallback_cutout_model)),
        default_outline_width=int(data.get("default_outline_width", defaults.default_outline_width)),
        default_shadow=bool(data.get("default_shadow", defaults.default_shadow)),
        default_font_preset=str(data.get("default_font_preset", defaults.default_font_preset)),
        default_text_style=str(data.get("default_text_style", defaults.default_text_style)),
        default_text_position=str(data.get("default_text_position", defaults.default_text_position)),
        default_text_scale=float(data.get("default_text_scale", defaults.default_text_scale)),
        default_stroke_ratio=float(data.get("default_stroke_ratio", defaults.default_stroke_ratio)),
        naming_separator=str(data.get("naming_separator", defaults.naming_separator)),
    )
