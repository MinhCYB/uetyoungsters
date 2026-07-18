"""Thin Data Layer orchestrator for manual or scheduled container runs.

All collection and parsing implementations remain in ``backend.data``.
This service intentionally exposes no HTTP API.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main(action: str | None = None) -> None:
    selected = action or os.getenv("DATA_ACTION", "status")

    if selected == "status":
        print(
            "Career Compass crawl-service is ready. Set DATA_ACTION to "
            "collect-greenhouse, collect-viecoi, collect-all, or pipeline."
        )
        return

    if selected == "collect-greenhouse":
        from scripts.collect_greenhouse import main as collect_greenhouse

        collect_greenhouse()
        return

    if selected == "collect-viecoi":
        from scripts.collect_viecoi import main as collect_viecoi

        collect_viecoi()
        return

    if selected == "collect-all":
        from scripts.collect_greenhouse import main as collect_greenhouse
        from scripts.collect_viecoi import main as collect_viecoi

        collect_greenhouse()
        collect_viecoi()
        return

    if selected == "pipeline":
        from scripts.run_data_pipeline import main as run_pipeline

        run_pipeline()
        return

    raise ValueError(f"DATA_ACTION không được hỗ trợ: {selected}")


def cli() -> None:
    action = (
        sys.argv[1]
        if len(sys.argv) >= 2
        else None
    )

    if len(sys.argv) > 2:
        raise SystemExit(
            "Usage: python main.py "
            "[status|collect-greenhouse|collect-viecoi|"
            "collect-all|pipeline]"
        )

    main(action)


if __name__ == "__main__":
    cli()
