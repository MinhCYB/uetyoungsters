from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

from ..paths import INTERIM_DIR, PROJECT_ROOT, RAW_DIR, SOURCES_CONFIG_PATH

RAW_ROOT = RAW_DIR / "greenhouse"
INTERIM_ROOT = INTERIM_DIR
SOURCES_PATH = SOURCES_CONFIG_PATH

API_TEMPLATE = (
    "https://boards-api.greenhouse.io/v1/boards/"
    "{board_token}/jobs"
)


def load_sources(path: str | Path = SOURCES_PATH) -> list[dict[str, Any]]:
    """Load enabled Greenhouse boards from the shared source registry."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    sources = [
        source
        for source in payload.get("sources", [])
        if source.get("platform") == "greenhouse" and source.get("enabled")
    ]

    required = {"source_id", "board_token", "company_name"}
    for source in sources:
        missing = required - set(source)
        if missing:
            raise KeyError(
                f"Nguồn {source.get('source_id', '<unknown>')} thiếu cấu hình: "
                f"{sorted(missing)}"
            )

    return sources


def clean_html(value: Any) -> str | None:
    if value is None:
        return None

    text = BeautifulSoup(
        str(value),
        "html.parser",
    ).get_text(" ", strip=True)

    text = re.sub(r"\s+", " ", text).strip()

    return text or None


def extract_location(job: dict[str, Any]) -> str | None:
    location = job.get("location")

    if isinstance(location, dict):
        return location.get("name")

    return str(location) if location else None


def extract_departments(job: dict[str, Any]) -> str | None:
    departments = job.get("departments") or []

    names = [
        department.get("name")
        for department in departments
        if isinstance(department, dict)
        and department.get("name")
    ]

    return " | ".join(names) or None


def collect_source(
    source: dict[str, Any],
    session: requests.Session,
) -> list[dict[str, Any]]:
    board_token = source["board_token"]

    url = API_TEMPLATE.format(
        board_token=board_token,
    )

    response = session.get(
        url,
        params={"content": "true"},
        timeout=float(source.get("timeout_seconds", 30)),
    )

    response.raise_for_status()
    payload = response.json()

    fetched_at = datetime.now(
        timezone.utc
    ).isoformat()

    crawl_date = fetched_at[:10]

    raw_dir = (
        RAW_ROOT
        / board_token
        / crawl_date
    )
    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    records: list[dict[str, Any]] = []

    for job in payload.get("jobs", []):
        job_id = str(job.get("id"))

        raw_json = json.dumps(
            job,
            ensure_ascii=False,
            sort_keys=True,
        )

        content_hash = hashlib.sha256(
            raw_json.encode("utf-8")
        ).hexdigest()

        raw_path = raw_dir / f"{job_id}.json"

        raw_path.write_text(
            raw_json,
            encoding="utf-8",
        )

        metadata = job.get("metadata") or []

        records.append(
            {
                "source": "greenhouse",
                "source_id": source["source_id"],
                "source_job_id": job_id,
                "source_url": job.get("absolute_url"),
                "job_title_raw": job.get("title"),
                "company_name_raw": source[
                    "company_name"
                ],
                "location_raw": extract_location(job),
                "department_raw": extract_departments(job),
                # Giữ HTML để description_cleaning có thể tách p/li/heading.
                "description_raw": job.get("content"),
                "description_text_raw": clean_html(job.get("content")),
                "updated_at_raw": job.get("updated_at"),
                "language_raw": job.get("language"),
                "metadata_raw": json.dumps(
                    metadata,
                    ensure_ascii=False,
                ),
                "fetched_at": fetched_at,
                "content_hash_sha256": content_hash,
                "raw_content_path": str(
                    raw_path.relative_to(PROJECT_ROOT)
                ),
                "collector_version": "0.1.0",
                "parser_version": "greenhouse-api-0.1.0",
            }
        )

    return records


def collect_greenhouse(
    sources_path: str | Path = SOURCES_PATH,
) -> pd.DataFrame:
    session = requests.Session()

    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": (
                "UETCareerResearch/0.1 "
                "(academic project)"
            ),
        }
    )

    all_records: list[dict[str, Any]] = []

    sources = load_sources(sources_path)

    if not sources:
        raise RuntimeError("Không có nguồn Greenhouse nào đang được bật.")

    for source in sources:
        print(
            f"[SOURCE] {source['source_id']}"
        )

        try:
            records = collect_source(
                source,
                session,
            )
        except requests.RequestException as exc:
            print(f"[ERROR] {exc}")
            continue
        except ValueError as exc:
            print(f"[ERROR] JSON không hợp lệ: {exc}")
            continue

        print(
            f"  Thu được {len(records)} jobs."
        )

        all_records.extend(records)

    dataframe = pd.DataFrame(all_records)

    if dataframe.empty:
        print(
            "Không thu được dữ liệu; "
            "không ghi đè file cũ."
        )
        return dataframe

    dataframe = dataframe.drop_duplicates(
        subset=[
            "source",
            "source_id",
            "source_job_id",
        ],
        keep="first",
    )

    INTERIM_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        INTERIM_ROOT
        / "greenhouse_jobs_latest.parquet"
    )

    dataframe.to_parquet(
        output_path,
        index=False,
    )

    csv_path = (
        INTERIM_ROOT
        / "greenhouse_jobs_latest.csv"
    )

    dataframe.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\nĐã lưu {len(dataframe)} jobs:")
    print(output_path)
    print(csv_path)

    return dataframe


def run_collection() -> pd.DataFrame:
    """Run the configured Greenhouse collection command."""
    return collect_greenhouse(SOURCES_CONFIG_PATH)


if __name__ == "__main__":
    df = collect_greenhouse()

    if not df.empty:
        print(
            df[
                [
                    "job_title_raw",
                    "company_name_raw",
                    "location_raw",
                    "department_raw",
                ]
            ]
            .head(20)
            .to_string(index=False)
        )
