from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.data.aggregation import build_demand_summary
from backend.data.extraction import load_taxonomy
from backend.data.lifecycle import update_job_lifecycle
from backend.data.models import RawJobPosting
from backend.data.pipeline import (
    deduplicate_extracted_rows,
    process_raw_jobs,
    process_viecoi_jobs,
    save_outputs,
)
from backend.data.quality import create_coverage_reports


TAXONOMY_PATH = Path("backend/shared/taxonomy.json")


def _raw_job(
    source_id: str,
    source_job_id: str,
    *,
    source: str = "viecoi",
    title: str = "Nhân viên kinh doanh",
    company: str = "Công ty Demo",
    location: str = "Hà Nội",
) -> RawJobPosting:
    return RawJobPosting(
        source=source,
        source_id=source_id,
        source_job_id=source_job_id,
        source_url=f"https://example.test/{source_job_id}",
        title_raw=title,
        company_name_raw=company,
        description_raw="Kỹ năng giao tiếp",
        location_raw=location,
        collected_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
    )


def test_viecoi_adapter_handles_90_rows(tmp_path):
    interim_path = tmp_path / "viecoi.parquet"
    dataframe = pd.DataFrame(
        [
            {
                "source": "viecoi",
                "source_id": "viecoi_listing",
                "source_job_id": index,
                "source_url": f"https://viecoi.vn/viec-lam/{index}.html",
                "job_title_raw": "Nhân viên kinh doanh",
                "company_name_raw": f"Công ty {index}",
                "location_raw": "Hà Nội",
                "salary_raw": "10-12 triệu",
                "skills_raw": json.dumps(
                    ["Kỹ Năng Bán Hàng", "Kỹ Năng Giao Tiếp"],
                    ensure_ascii=False,
                ),
                "card_text_raw": "Nhân viên kinh doanh",
                "fetched_at": "2026-07-18T00:00:00Z",
                "content_hash_sha256": f"hash-{index}",
            }
            for index in range(90)
        ]
    )
    dataframe.to_parquet(interim_path, index=False)

    rows = process_viecoi_jobs(
        interim_path,
        TAXONOMY_PATH,
        "test-90",
    )

    assert len(rows) == 90
    assert len({row.source_job_id for row in rows}) == 90
    assert all(isinstance(row.source_job_id, str) for row in rows)
    assert all(
        skill.requirement_level == "mentioned"
        for row in rows
        for skill in row.skills
    )


def test_dedup_identity_and_cross_source_grouping():
    taxonomy = load_taxonomy(TAXONOMY_PATH)
    raw_jobs = [
        _raw_job("viecoi_listing", "1"),
        _raw_job("viecoi_listing", "1"),
        _raw_job("viecoi_listing", "2", company="Công ty Khác"),
        _raw_job("viecoi_listing", "3", location="TP.HCM"),
        _raw_job(
            "greenhouse_demo",
            "4",
            source="greenhouse",
        ),
    ]
    extracted = process_raw_jobs(raw_jobs, taxonomy, "dedup-test")
    deduplicated = deduplicate_extracted_rows(extracted)

    assert len(deduplicated) == 4
    by_id = {row.source_job_id: row for row in deduplicated}
    assert by_id["1"].dedup_group_id == by_id["4"].dedup_group_id
    assert by_id["1"].duplicate_count == 2
    assert by_id["2"].dedup_group_id != by_id["1"].dedup_group_id
    assert by_id["3"].dedup_group_id != by_id["1"].dedup_group_id


def test_lifecycle_multisource_idempotent_and_invalid(tmp_path):
    state_path = tmp_path / "lifecycle.parquet"
    invalid = pd.DataFrame(
        [
            {
                "source": "viecoi",
                "source_id": "viecoi_listing",
                "source_job_id": "2",
                "source_url": (
                    "https://viecoi.vn/viec-lam/danh-muc-demo-2.html"
                ),
                "content_hash_sha256": "invalid",
                "collected_at": "2026-07-17T00:00:00Z",
                "lifecycle_status": "inactive",
                "is_active": False,
            }
        ]
    )
    invalid.to_parquet(state_path, index=False)
    current = pd.DataFrame(
        [
            {
                "source": "greenhouse",
                "source_id": "greenhouse_demo",
                "source_job_id": "1",
                "source_url": "https://example.test/greenhouse/1",
                "content_hash_sha256": "green-v1",
                "collected_at": "2026-07-18T00:00:00Z",
            },
            {
                "source": "viecoi",
                "source_id": "viecoi_listing",
                "source_job_id": "10",
                "source_url": "https://example.test/viecoi/10",
                "content_hash_sha256": "viecoi-v1",
                "collected_at": "2026-07-18T00:00:00Z",
            },
        ]
    )

    first, state = update_job_lifecycle(current, state_path)
    second, state_again = update_job_lifecycle(current, state_path)

    assert len(first) == len(second) == 2
    assert not second.duplicated(["source_id", "source_job_id"]).any()
    assert (state_again["lifecycle_status"] == "active").sum() == 2
    assert (state_again["lifecycle_status"] == "invalid").sum() == 1
    assert set(second["source_job_id"]) == {"1", "10"}


def test_aggregation_keeps_remote_and_excludes_inactive(tmp_path):
    jobs_path = tmp_path / "jobs.parquet"
    skills_path = tmp_path / "skills.parquet"
    output_path = tmp_path / "summary.parquet"
    jobs = pd.DataFrame(
        [
            {
                "job_id": "remote",
                "source_id": "viecoi_listing",
                "source_job_id": "1",
                "career_id": "CAREER_SALES_EXECUTIVE",
                "career_name": "Sales Executive",
                "province": None,
                "work_mode": "REMOTE",
                "snapshot_version": "test",
                "company_name": "A",
                "salary_mid_vnd": 10_000_000,
                "salary_disclosed": True,
                "overall_confidence": 0.9,
                "posted_at": None,
                "collected_at": "2026-07-18T00:00:00Z",
                "is_active": True,
                "lifecycle_status": "active",
            },
            {
                "job_id": "inactive",
                "source_id": "viecoi_listing",
                "source_job_id": "2",
                "career_id": "CAREER_SALES_EXECUTIVE",
                "career_name": "Sales Executive",
                "province": "Hà Nội",
                "work_mode": "UNSPECIFIED",
                "snapshot_version": "test",
                "company_name": "B",
                "salary_mid_vnd": 12_000_000,
                "salary_disclosed": False,
                "overall_confidence": 0.9,
                "posted_at": None,
                "collected_at": "2026-07-18T00:00:00Z",
                "is_active": False,
                "lifecycle_status": "inactive",
            },
        ]
    )
    jobs.to_parquet(jobs_path, index=False)
    pd.DataFrame(
        columns=[
            "dedup_group_id",
            "career_id",
            "province",
            "work_mode",
            "skill_id",
            "skill_name",
            "requirement_level",
        ]
    ).to_parquet(skills_path, index=False)

    summary = build_demand_summary(jobs_path, skills_path, output_path)

    assert len(summary) == 1
    assert summary.iloc[0]["posting_count"] == 1
    assert summary.iloc[0]["salary_sample_size"] == 1
    assert pd.isna(summary.iloc[0]["province"])
    assert summary.iloc[0]["work_mode"] == "REMOTE"
    assert pd.isna(summary.iloc[0]["data_from"])
    assert pd.isna(summary.iloc[0]["data_to"])


def test_coverage_report_schema(tmp_path):
    taxonomy = load_taxonomy(TAXONOMY_PATH)
    rows = process_raw_jobs(
        [_raw_job("viecoi_listing", "1")],
        taxonomy,
        "coverage-test",
    )
    jobs_path = tmp_path / "jobs.parquet"
    skills_path = tmp_path / "skills.parquet"
    lifecycle_path = tmp_path / "lifecycle.parquet"
    save_outputs(rows, jobs_path, skills_path)
    jobs = pd.read_parquet(jobs_path)
    jobs, lifecycle = update_job_lifecycle(jobs, lifecycle_path)
    jobs.to_parquet(jobs_path, index=False)

    report, taxonomy_report = create_coverage_reports(
        jobs_path,
        skills_path,
        lifecycle_path,
        taxonomy,
        tmp_path / "reports",
    )

    required = {
        "snapshot_version",
        "total_current_jobs",
        "invalid_records_excluded",
        "source_distribution",
        "remote_job_count",
        "career_mapping_rate",
        "location_mapping_rate_non_remote",
        "skill_mapping_rate",
        "taxonomy_version",
        "generated_at",
    }
    assert required <= report.keys()
    assert taxonomy_report["taxonomy_version"] == "0.4.0"
    assert (tmp_path / "reports/source_coverage.json").exists()
    assert (tmp_path / "reports/taxonomy_coverage.json").exists()
