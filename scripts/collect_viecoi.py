"""Deprecated compatibility wrapper for ViecOi collection."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CRAWL_SERVICE_SRC = PROJECT_ROOT / "crawl-service" / "src"
if str(CRAWL_SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(CRAWL_SERVICE_SRC))

from crawl_service.cli import main


if __name__ == "__main__":
    raise SystemExit(main("collect-viecoi"))
