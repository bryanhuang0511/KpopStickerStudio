"""安全檔名產生器（遵循「人_字」規則與防覆蓋保護）。"""

from __future__ import annotations

import re
from pathlib import Path

_ILLEGAL_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_token(value: str | None, max_len: int = 40) -> str:
    if not value:
        return ""
    cleaned = _ILLEGAL_CHARS_RE.sub("", value)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip(" .")
    return cleaned[:max_len].strip(" .")


def build_output_path(
    output_dir: Path,
    person: str | None,
    text: str | None,
    ext: str = "png",
    separator: str = "_",
    overwrite: bool = False,
) -> Path:
    """依「人_字.ext」產生不覆蓋既有檔案的輸出路徑。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_ext = ext.lower().lstrip(".")

    person_tok = sanitize_token(person)
    text_tok = sanitize_token(text.replace("\n", " ") if text else "")

    parts = [p for p in (person_tok, text_tok) if p]
    stem = separator.join(parts) if parts else "貼圖"

    candidate = output_dir / f"{stem}.{clean_ext}"
    if overwrite or not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = output_dir / f"{stem}{separator}{index:02d}.{clean_ext}"
        if not candidate.exists():
            return candidate
        index += 1
