"""Deprecated file entrypoint; prefer ``python -m crawl_service``."""

from __future__ import annotations

from pathlib import Path
import sys


CRAWL_SERVICE_SRC = Path(__file__).resolve().parent / "src"
if str(CRAWL_SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(CRAWL_SERVICE_SRC))

from crawl_service.cli import cli


if __name__ == "__main__":
    raise SystemExit(cli())
