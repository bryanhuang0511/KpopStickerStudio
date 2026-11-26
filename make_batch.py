"""批次無損貼圖 CLI 入口：python make_batch.py <jobs.json> [--verify-sheet out.jpg]"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sticker_maker.batch import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
