"""啟動 KpopStickerStudio 本機網頁工作台。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sticker_maker.server import run_server  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="啟動 KpopStickerStudio 本機 UI")
    parser.add_argument("--host", default=None, help="監聽位址（預設 0.0.0.0）")
    parser.add_argument("--port", type=int, default=None, help="連接埠（預設 8765）")
    parser.add_argument("--no-browser", action="store_true", help="不自動開啟瀏覽器")
    parser.add_argument("--auto-exit", action="store_true", help="視窗關閉失去心跳後自動結束伺服器")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, open_browser=not args.no_browser, auto_exit=args.auto_exit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
