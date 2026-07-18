from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .extraction import extract_skills
from .lifecycle import invalid_category_mask
from .models import ExtractedJobPosting
from .normalization import clean_text


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def create_quality_report(
    jobs_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    jobs = pd.read_parquet(jobs_path)
    total = len(jobs)
    duplicate_rows = int(
        jobs.duplicated(["source_id", "source_job_id"]).sum()
    )
    snapshot_versions = sorted(
        jobs["snapshot_version"].dropna().astype(str).unique().tolist()
    )
    taxonomy_versions = sorted(
        jobs["taxonomy_version"].dropna().astype(str).unique().tolist()
    )

    report = {
        "total_rows": total,
        "unique_content_hashes": int(jobs["content_hash"].nunique()),
        "duplicate_rows": duplicate_rows,
        "mapped_career_rows": int(jobs["career_id"].notna().sum()),
        "mapped_location_rows": int(jobs["province"].notna().sum()),
        "remote_job_count": int((jobs["work_mode"] == "REMOTE").sum()),
        "salary_disclosed_rows": int(jobs["salary_disclosed"].sum()),
        "average_extraction_confidence": (
            round(float(jobs["overall_confidence"].mean()), 3)
            if total
            else None
        ),
        "sources": sorted(jobs["source"].dropna().unique().tolist()),
        "snapshot_version": (
            snapshot_versions[0]
            if len(snapshot_versions) == 1
            else snapshot_versions
        ),
        "snapshot_versions": snapshot_versions,
        "taxonomy_version": (
            taxonomy_versions[0]
            if len(taxonomy_versions) == 1
            else taxonomy_versions
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _write_json(output_path, report)
    return report


def parse_skill_tags(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        parsed = value
    else:
        try:
            parsed = json.loads(str(value))
        except (json.JSONDecodeError, TypeError):
            return []

    if not isinstance(parsed, list):
        return []

    result: list[str] = []
    for item in parsed:
        tag = clean_text(item)
        if tag and tag not in result:
            result.append(tag)
    return result


def create_viecoi_taxonomy_reports(
    raw: pd.DataFrame,
    extracted_rows: Iterable[ExtractedJobPosting],
    taxonomy: dict[str, Any],
    output_dir: str | Path,
    *,
    low_confidence_threshold: float = 0.90,
) -> dict[str, int]:
    """Create persistent career, skill and location QA artifacts."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    rows_by_id = {
        str(row.source_job_id): row
        for row in extracted_rows
    }
    skill_categories = {
        skill["skill_id"]: skill.get("category", "unspecified")
        for skill in taxonomy.get("skills", [])
    }
    frequency: Counter[str] = Counter()
    audit_records: list[dict[str, Any]] = []

    for raw_record in raw.to_dict(orient="records"):
        source_job_id = str(raw_record.get("source_job_id"))
        extracted = rows_by_id.get(source_job_id)
        if extracted is None:
            continue

        raw_tags = parse_skill_tags(raw_record.get("skills_raw"))
        frequency.update(raw_tags)
        mapped_tags: list[str] = []
        unmapped_tags: list[str] = []

        for tag in raw_tags:
            tag_skills = extract_skills(
                tag,
                taxonomy,
                default_requirement_level="mentioned",
            )
            if tag_skills:
                mapped_tags.extend(
                    skill.skill_name for skill in tag_skills
                )
            else:
                unmapped_tags.append(tag)

        audit_records.append(
            {
                "snapshot_version": extracted.snapshot_version,
                "generated_at": generated_at,
                "source_job_id": source_job_id,
                "job_title_raw": raw_record.get("job_title_raw"),
                "company_name_raw": raw_record.get("company_name_raw"),
                "location_raw": raw_record.get("location_raw"),
                "salary_raw": raw_record.get("salary_raw"),
                "skills_raw": json.dumps(
                    raw_tags,
                    ensure_ascii=False,
                ),
                "career_id": extracted.career_id,
                "career_name": extracted.career_name,
                "career_mapping_confidence": (
                    extracted.career_mapping_confidence
                ),
                "province": extracted.province,
                "work_mode": extracted.work_mode,
                "mapped_skills": " | ".join(
                    sorted(set(mapped_tags))
                ),
                "unmapped_skill_tags": " | ".join(unmapped_tags),
                "source_url": extracted.source_url,
            }
        )

    audit = pd.DataFrame(audit_records)
    career_gap = audit[
        audit["career_id"].isna()
        | (
            audit["career_mapping_confidence"]
            < low_confidence_threshold
        )
    ].copy()
    skill_gap = audit[
        audit["unmapped_skill_tags"].fillna("").ne("")
    ].copy()
    location_gap = audit[audit["province"].isna()].copy()
    location_gap["location_status"] = location_gap["work_mode"].map(
        lambda value: "remote" if value == "REMOTE" else "unknown"
    )

    tag_rows: list[dict[str, Any]] = []
    for tag, count in frequency.most_common():
        mapped = extract_skills(
            tag,
            taxonomy,
            default_requirement_level="mentioned",
        )
        tag_rows.append(
            {
                "snapshot_version": (
                    audit["snapshot_version"].iloc[0]
                    if not audit.empty
                    else None
                ),
                "generated_at": generated_at,
                "skill_tag_raw": tag,
                "frequency": count,
                "mapped_skill_ids": " | ".join(
                    skill.skill_id for skill in mapped
                ),
                "mapped_skill_names": " | ".join(
                    skill.skill_name for skill in mapped
                ),
                "skill_categories": " | ".join(
                    sorted(
                        {
                            skill_categories.get(
                                skill.skill_id,
                                "unspecified",
                            )
                            for skill in mapped
                        }
                    )
                ),
                "is_mapped": bool(mapped),
            }
        )

    frequency_table = pd.DataFrame(tag_rows)
    unmapped_table = frequency_table[
        ~frequency_table["is_mapped"]
    ].copy()

    outputs = {
        "viecoi_taxonomy_gap.csv": career_gap,
        "viecoi_skill_gap.csv": skill_gap,
        "viecoi_location_gap.csv": location_gap,
        "viecoi_skill_frequency.csv": frequency_table,
        "viecoi_unmapped_skills.csv": unmapped_table,
    }
    for filename, dataframe in outputs.items():
        dataframe.to_csv(
            output_root / filename,
            index=False,
            encoding="utf-8-sig",
        )

    return {
        "career_gap_rows": len(career_gap),
        "skill_gap_rows": len(skill_gap),
        "location_gap_rows": len(location_gap),
        "unique_skill_tags": len(frequency_table),
        "unmapped_skill_tags": len(unmapped_table),
    }


def create_coverage_reports(
    jobs_path: str | Path,
    skills_path: str | Path,
    lifecycle_path: str | Path,
    taxonomy: dict[str, Any],
    output_dir: str | Path,
    *,
    collector_versions: dict[str, list[str]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    jobs = pd.read_parquet(jobs_path)
    skills = pd.read_parquet(skills_path)
    lifecycle = pd.read_parquet(lifecycle_path)
    output_root = Path(output_dir)
    generated_at = datetime.now(timezone.utc).isoformat()

    invalid_mask = invalid_category_mask(lifecycle)
    valid_lifecycle = lifecycle.loc[~invalid_mask].copy()
    total = len(jobs)
    remote_mask = jobs["work_mode"].eq("REMOTE")
    non_remote = jobs.loc[~remote_mask]
    mapped_skill_job_ids = set(
        skills.get("job_id", pd.Series(dtype="string"))
        .dropna()
        .astype(str)
    )
    jobs_with_skills = int(
        jobs["job_id"].astype(str).isin(mapped_skill_job_ids).sum()
    )
    salary_count = int(jobs["salary_disclosed"].fillna(False).sum())
    description_count = int(
        jobs["description_clean"].fillna("").str.strip().ne("").sum()
    )
    career_count = int(jobs["career_id"].notna().sum())
    location_count = int(non_remote["province"].notna().sum())
    snapshot_versions = sorted(
        jobs["snapshot_version"].dropna().astype(str).unique().tolist()
    )

    source_coverage: dict[str, Any] = {
        "snapshot_version": (
            snapshot_versions[0] if len(snapshot_versions) == 1
            else snapshot_versions
        ),
        "total_current_jobs": total,
        "total_lifecycle_records": len(lifecycle),
        "valid_lifecycle_records": len(valid_lifecycle),
        "active_jobs": int(
            (valid_lifecycle["lifecycle_status"] == "active").sum()
        ),
        "missing_unconfirmed_jobs": int(
            (
                valid_lifecycle["lifecycle_status"]
                == "missing_unconfirmed"
            ).sum()
        ),
        "inactive_jobs": int(
            (valid_lifecycle["lifecycle_status"] == "inactive").sum()
        ),
        "invalid_records_excluded": int(invalid_mask.sum()),
        "active_sources": sorted(jobs["source"].dropna().unique().tolist()),
        "source_distribution": {
            str(key): int(value)
            for key, value in jobs["source"].value_counts().items()
        },
        "unique_companies": int(jobs["company_name"].nunique()),
        "unique_careers": int(jobs["career_id"].nunique()),
        "unique_provinces": int(jobs["province"].nunique()),
        "remote_job_count": int(remote_mask.sum()),
        "unknown_location_count": int(
            non_remote["province"].isna().sum()
        ),
        "salary_available_count": salary_count,
        "salary_available_rate": _rate(salary_count, total),
        "description_available_rate": _rate(description_count, total),
        "career_mapping_rate": _rate(career_count, total),
        "location_mapping_rate_non_remote": _rate(
            location_count,
            len(non_remote),
        ),
        "jobs_with_mapped_skills": jobs_with_skills,
        "skill_mapping_rate": _rate(jobs_with_skills, total),
        "duplicate_count": int(
            jobs.duplicated(["source_id", "source_job_id"]).sum()
        ),
        "average_extraction_confidence": (
            round(float(jobs["overall_confidence"].mean()), 4)
            if total
            else None
        ),
        "average_extraction_confidence_by_source": {
            str(key): round(float(value), 4)
            for key, value in jobs.groupby("source")[
                "overall_confidence"
            ].mean().items()
        },
        "taxonomy_version": taxonomy.get("taxonomy_version"),
        "collector_versions": collector_versions or {},
        "generated_at": generated_at,
        "coverage_note": (
            "Snapshot from monitored sources; it does not represent the "
            "entire Vietnamese labour market. Greenhouse covers one company "
            "with full job descriptions. ViecOi covers three public listing "
            "pages and listing fields only."
        ),
    }

    taxonomy_sources: dict[str, Any] = {}
    for source, group in jobs.groupby("source"):
        source_remote = group["work_mode"].eq("REMOTE")
        source_non_remote = group.loc[~source_remote]
        source_skill_jobs = int(
            group["job_id"].astype(str).isin(mapped_skill_job_ids).sum()
        )
        taxonomy_sources[str(source)] = {
            "rows": len(group),
            "career_mapping_rate": _rate(
                int(group["career_id"].notna().sum()),
                len(group),
            ),
            "location_mapping_rate_non_remote": _rate(
                int(source_non_remote["province"].notna().sum()),
                len(source_non_remote),
            ),
            "remote_job_count": int(source_remote.sum()),
            "unknown_location_count": int(
                source_non_remote["province"].isna().sum()
            ),
            "jobs_with_mapped_skills": source_skill_jobs,
            "skill_mapping_rate": _rate(source_skill_jobs, len(group)),
            "average_extraction_confidence": round(
                float(group["overall_confidence"].mean()),
                4,
            ),
        }

    taxonomy_coverage = {
        "snapshot_version": source_coverage["snapshot_version"],
        "taxonomy_version": taxonomy.get("taxonomy_version"),
        "generated_at": generated_at,
        "sources": taxonomy_sources,
    }

    _write_json(output_root / "source_coverage.json", source_coverage)
    _write_json(
        output_root / "taxonomy_coverage.json",
        taxonomy_coverage,
    )
    return source_coverage, taxonomy_coverage
