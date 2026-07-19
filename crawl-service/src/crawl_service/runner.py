from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .aggregation import build_demand_summary
from .extraction import load_taxonomy
from .lifecycle import update_job_lifecycle
from .paths import INTERIM_DIR, PROCESSED_DIR, REPORTS_DIR, TAXONOMY_PATH
from .pipeline import (
    process_greenhouse_jobs,
    process_viecoi_jobs,
    save_outputs,
)
from .quality import (
    create_coverage_reports,
    create_quality_report,
    create_viecoi_taxonomy_reports,
)
from .database import publish_processed_outputs
from .career_profiles import write_career_detail_outputs


GREENHOUSE_INTERIM_PATH = (
    INTERIM_DIR
    / "greenhouse_jobs_latest.parquet"
)

VIECOI_INTERIM_PATH = (
    INTERIM_DIR
    / "viecoi_jobs_latest.parquet"
)

PROCESSED_ROOT = PROCESSED_DIR

REPORT_PATH = (
    REPORTS_DIR
    / "data_quality.json"
)

REPORT_ROOT = REPORTS_DIR

LIFECYCLE_PATH = (
    PROCESSED_ROOT
    / "job_lifecycle.parquet"
)


def run_pipeline() -> None:
    required_inputs = [
        GREENHOUSE_INTERIM_PATH,
        VIECOI_INTERIM_PATH,
    ]

    missing_inputs = [
        path
        for path in required_inputs
        if not path.exists()
    ]

    if missing_inputs:
        missing_text = "\n".join(
            f"- {path}"
            for path in missing_inputs
        )

        raise FileNotFoundError(
            "Thiếu dữ liệu interim:\n"
            f"{missing_text}\n"
            "Hãy chạy các collector trước."
        )

    snapshot_version = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d-multisource")

    # 1. Làm sạch, chuẩn hóa và trích xuất đặc trưng.
    greenhouse_rows = process_greenhouse_jobs(
        interim_path=GREENHOUSE_INTERIM_PATH,
        taxonomy_path=TAXONOMY_PATH,
        snapshot_version=snapshot_version,
        description_debug_path=(
            PROCESSED_ROOT
            / "greenhouse_jobs_description_clean.parquet"
        ),
    )

    viecoi_rows = process_viecoi_jobs(
        interim_path=VIECOI_INTERIM_PATH,
        taxonomy_path=TAXONOMY_PATH,
        snapshot_version=snapshot_version,
    )

    extracted = greenhouse_rows + viecoi_rows
    taxonomy = load_taxonomy(TAXONOMY_PATH)

    print("\nSOURCE INPUT")
    print(f"Greenhouse: {len(greenhouse_rows)}")
    print(f"ViecOi:     {len(viecoi_rows)}")
    print(f"Combined:   {len(extracted)}")

    gap_report = create_viecoi_taxonomy_reports(
        raw=pd.read_parquet(VIECOI_INTERIM_PATH),
        extracted_rows=viecoi_rows,
        taxonomy=taxonomy,
        output_dir=REPORT_ROOT,
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

    collector_versions = {}
    for source_name, interim_path in {
        "greenhouse": GREENHOUSE_INTERIM_PATH,
        "viecoi": VIECOI_INTERIM_PATH,
    }.items():
        interim = pd.read_parquet(interim_path)
        collector_versions[source_name] = sorted(
            interim.get(
                "collector_version",
                pd.Series(dtype="string"),
            )
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    coverage_report, _ = create_coverage_reports(
        jobs_path=jobs_path,
        skills_path=skills_path,
        lifecycle_path=LIFECYCLE_PATH,
        taxonomy=taxonomy,
        output_dir=REPORT_ROOT,
        collector_versions=collector_versions,
    )

    write_career_detail_outputs(
        jobs_path=jobs_path,
        skills_path=skills_path,
        demand_path=PROCESSED_ROOT / "career_demand_summary.parquet",
        skill_matrix_path=PROCESSED_ROOT / "career_skill_matrix.parquet",
        taxonomy=taxonomy,
        output_dir=PROCESSED_ROOT,
    )

    # 6. Chá»‰ publish database sau khi toÃ n bá»™ pipeline vÃ  quality checks
    # Ä‘Ã£ hoÃ n táº¥t, Ä‘á»ƒ consumer khÃ´ng Ä‘á»c pháº£i snapshot dá»Ÿ dang.
    manifest = publish_processed_outputs(PROCESSED_ROOT)

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

    print("\nTAXONOMY GAP REPORTS")
    print(gap_report)

    print("\nSOURCE COVERAGE")
    print(coverage_report)

    print("\nDATABASE WAREHOUSE")
    print(manifest.to_string(index=False))


if __name__ == "__main__":
    run_pipeline()
