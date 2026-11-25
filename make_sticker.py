"""快捷 CLI 入口：python make_sticker.py <圖片路徑> --person <人名> --text <文字>"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sticker_maker.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
