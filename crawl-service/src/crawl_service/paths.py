"""Central, portable repository paths for the crawl service."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _is_project_root(path: Path) -> bool:
    return (
        (path / "backend" / "shared" / "taxonomy.json").is_file()
        and (path / "config" / "sources.yaml").is_file()
    )


def _discover_project_root() -> Path:
    configured = os.getenv("CAREER_COMPASS_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
        if not _is_project_root(root):
            raise RuntimeError(
                "CAREER_COMPASS_ROOT does not contain the canonical "
                f"taxonomy and source config: {root}"
            )
        return root

    module_path = Path(__file__).resolve()
    for candidate in module_path.parents:
        if _is_project_root(candidate):
            return candidate

    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if _is_project_root(candidate):
            return candidate

    raise RuntimeError(
        "Cannot locate the Career Compass project root. "
        "Set CAREER_COMPASS_ROOT to the repository root."
    )


PROJECT_ROOT = _discover_project_root()

# Shared core contracts are intentionally kept outside this service package.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
SOURCES_CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"
TAXONOMY_PATH = PROJECT_ROOT / "backend" / "shared" / "taxonomy.json"


__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "RAW_DIR",
    "INTERIM_DIR",
    "PROCESSED_DIR",
    "REPORTS_DIR",
    "SOURCES_CONFIG_PATH",
    "TAXONOMY_PATH",
]
