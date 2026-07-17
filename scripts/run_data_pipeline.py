from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.data.aggregation import build_demand_summary
from backend.data.lifecycle import update_job_lifecycle
from backend.data.pipeline import (
    process_greenhouse_jobs,
    save_outputs,
)
from backend.data.quality import create_quality_report


INTERIM_PATH = (
    PROJECT_ROOT
    / "data"
    / "interim"
    / "greenhouse_jobs_latest.parquet"
)

TAXONOMY_PATH = (
    PROJECT_ROOT
    / "backend"
    / "shared"
    / "taxonomy.json"
)

PROCESSED_ROOT = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "data_quality.json"
)

LIFECYCLE_PATH = (
    PROCESSED_ROOT
    / "job_lifecycle.parquet"
)


def main() -> None:
    if not INTERIM_PATH.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {INTERIM_PATH}. "
            "Hãy chạy scripts/collect_greenhouse.py trước."
        )

    snapshot_version = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d-greenhouse")

    # 1. Làm sạch, chuẩn hóa và trích xuất đặc trưng.
    extracted = process_greenhouse_jobs(
        interim_path=INTERIM_PATH,
        taxonomy_path=TAXONOMY_PATH,
        snapshot_version=snapshot_version,
        description_debug_path=(
            PROCESSED_ROOT
            / "greenhouse_jobs_description_clean.parquet"
        ),
    )

    jobs_path = (
        PROCESSED_ROOT
        / "jobs_clean.parquet"
    )

    skills_path = (
        PROCESSED_ROOT
        / "job_skills.parquet"
    )

    # 2. Ghi schema jobs và bảng skills ban đầu.
    save_outputs(
        extracted,
        jobs_path=jobs_path,
        skills_path=skills_path,
    )

    # 3. Cập nhật vòng đời tin tuyển dụng.
    current_jobs = pd.read_parquet(
        jobs_path
    )

    current_jobs, lifecycle_state = (
        update_job_lifecycle(
            current_jobs=current_jobs,
            state_path=LIFECYCLE_PATH,
            inactive_after_missing_runs=3,
        )
    )

    # jobs_clean chỉ chứa snapshot hiện tại,
    # đã được bổ sung các trường lifecycle.
    current_jobs.to_parquet(
        jobs_path,
        index=False,
    )

    # 4. Tổng hợp chỉ từ các tin trong snapshot hiện tại.
    summary = build_demand_summary(
        jobs_path=jobs_path,
        skills_path=skills_path,
        output_path=(
            PROCESSED_ROOT
            / "career_demand_summary.parquet"
        ),
    )

    # 5. Sinh báo cáo chất lượng.
    report = create_quality_report(
        jobs_path=jobs_path,
        output_path=REPORT_PATH,
    )

    print("\nLIFECYCLE")
    print(
        lifecycle_state[
            "lifecycle_status"
        ].value_counts(
            dropna=False
        )
    )

    print(
        f"\nCurrent jobs: {len(current_jobs)}"
    )
    print(
        "Lifecycle records: "
        f"{len(lifecycle_state)}"
    )

    print("\nCAREER DEMAND")
    print(
        summary.to_string(index=False)
    )

    print("\nDATA QUALITY")
    print(report)


if __name__ == "__main__":
    main()
