from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.aggregation import build_demand_summary
from backend.data.pipeline import process_greenhouse_jobs, save_outputs
from backend.data.quality import create_quality_report


INTERIM_PATH = PROJECT_ROOT / "data" / "interim" / "greenhouse_jobs_latest.parquet"
TAXONOMY_PATH = PROJECT_ROOT / "backend" / "shared" / "taxonomy.json"
PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"
REPORT_PATH = PROJECT_ROOT / "reports" / "data_quality.json"


def main() -> None:
    if not INTERIM_PATH.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {INTERIM_PATH}. "
            "Hãy chạy scripts/collect_greenhouse.py trước."
        )

    snapshot_version = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d-greenhouse"
    )
    extracted = process_greenhouse_jobs(
        interim_path=INTERIM_PATH,
        taxonomy_path=TAXONOMY_PATH,
        snapshot_version=snapshot_version,
        description_debug_path=(
            PROCESSED_ROOT / "greenhouse_jobs_description_clean.parquet"
        ),
    )

    jobs_path = PROCESSED_ROOT / "jobs_clean.parquet"
    skills_path = PROCESSED_ROOT / "job_skills.parquet"
    save_outputs(extracted, jobs_path=jobs_path, skills_path=skills_path)

    summary = build_demand_summary(
        jobs_path=jobs_path,
        skills_path=skills_path,
        output_path=PROCESSED_ROOT / "career_demand_summary.parquet",
    )
    report = create_quality_report(
        jobs_path=jobs_path,
        output_path=REPORT_PATH,
    )

    print(summary.to_string(index=False))
    print("\nDATA QUALITY")
    print(report)


if __name__ == "__main__":
    main()
