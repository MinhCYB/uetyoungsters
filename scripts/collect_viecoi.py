from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.data.collectors.viecoi import collect_viecoi


CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "sources.yaml"
)


def load_viecoi_source(
    config_path: str | Path = CONFIG_PATH,
) -> dict[str, Any]:
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy source registry: {path}"
        )

    payload = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    sources = payload.get("sources", [])

    for source in sources:
        if (
            source.get("platform") == "viecoi"
            and source.get("enabled") is True
        ):
            return source

    raise RuntimeError(
        "Không tìm thấy nguồn ViecOi đang bật "
        "trong config/sources.yaml."
    )


def main() -> None:
    source = load_viecoi_source()

    if source.get("detail_pages_enabled", False):
        raise ValueError(
            "Collector hiện chỉ hỗ trợ listing-only. "
            "detail_pages_enabled phải là false."
        )

    print("[SOURCE CONFIG]")
    print(f"  source_id: {source['source_id']}")
    print(f"  listing_url: {source['listing_url']}")
    print(f"  max_pages: {source.get('max_pages', 1)}")
    print(f"  max_jobs: {source.get('max_jobs', 30)}")
    print(
        "  collection_scope: "
        f"{source.get('collection_scope')}"
    )

    dataframe = collect_viecoi(
        project_root=PROJECT_ROOT,
        listing_url=source["listing_url"],
        max_pages=int(
            source.get("max_pages", 1)
        ),
        max_jobs=int(
            source.get("max_jobs", 30)
        ),
        min_delay_seconds=float(
            source.get("min_delay_seconds", 6)
        ),
        max_delay_seconds=float(
            source.get("max_delay_seconds", 10)
        ),
        timeout_seconds=int(
            source.get("timeout_seconds", 30)
        ),
        user_agent=source.get(
            "user_agent",
            (
                "UETCareerResearch/0.1 "
                "(academic project)"
            ),
        ),
    )

    if dataframe.empty:
        return

    columns = [
        "source_job_id",
        "job_title_raw",
        "company_name_raw",
        "salary_raw",
        "location_raw",
        "application_deadline_raw",
        "skills_raw",
    ]

    print(
        "\n"
        + dataframe[columns]
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
