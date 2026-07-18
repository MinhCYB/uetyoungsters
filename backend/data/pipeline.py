from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import pandas as pd

from .models import RawJobPosting, ExtractedJobPosting
from .cleaning import (
    build_content_hash,
    build_cross_source_dedup_key,
    build_job_id,
    build_dedup_group_id,
)
from .normalization import (
    clean_text,
    normalize_location,
    normalize_work_mode,
    parse_salary,
    normalize_seniority,
    normalize_education,
    parse_posted_date,
)
from .description_cleaning import clean_job_descriptions
from .extraction import (
    extract_experience_years,
    extract_skills,
    load_taxonomy,
    normalize_career,
)


EXTRACTION_MODEL = "rule_taxonomy"
EXTRACTION_VERSION = "0.1.0"


def process_raw_jobs(
    raw_jobs: list[RawJobPosting],
    taxonomy: dict,
    snapshot_version: str,
) -> list[ExtractedJobPosting]:
    hashes = [
        build_content_hash(
            job.title_raw,
            job.company_name_raw,
            job.location_raw,
            job.description_raw,
        )
        for job in raw_jobs
    ]
    duplicate_counts = Counter(hashes)
    extracted_rows: list[ExtractedJobPosting] = []

    for raw, content_hash in zip(raw_jobs, hashes):
        role_description = raw.description_role_specific or raw.description_raw
        career_id, career_name, title_confidence = normalize_career(
            raw.title_raw, taxonomy
        )
        salary_min, salary_max, salary_mid, salary_disclosed = parse_salary(
            raw.salary_raw
        )
        default_skill_level = raw.raw_payload.get(
            "skill_requirement_level",
            "required",
        )
        raw_skill_tags = raw.raw_payload.get("skills_raw")

        if isinstance(raw_skill_tags, list):
            # Listing tags are independent mentions. Extracting each tag in
            # isolation prevents title/card negation text such as "không cần
            # kinh nghiệm" from changing another tag's requirement level.
            skills_by_id = {}
            for raw_tag in raw_skill_tags:
                for skill in extract_skills(
                    str(raw_tag),
                    taxonomy,
                    default_requirement_level=default_skill_level,
                ):
                    skills_by_id[skill.skill_id] = skill
            skills = sorted(
                skills_by_id.values(),
                key=lambda item: item.skill_id,
            )
        else:
            skills = extract_skills(
                role_description,
                taxonomy,
                default_requirement_level=default_skill_level,
            )
        province = normalize_location(raw.location_raw, taxonomy)
        work_mode = normalize_work_mode(
            work_mode_raw=raw.work_mode_raw,
            location_raw=raw.location_raw,
            description_raw=role_description,
        )
        seniority = normalize_seniority(
            raw.experience_raw or role_description
        )

        confidence_parts = [
            title_confidence,
            1.0 if province else 0.4,
            1.0 if skills else 0.3,
            1.0 if role_description else 0.0,
        ]
        overall_confidence = round(
            sum(confidence_parts) / len(confidence_parts), 3
        )

        extracted_rows.append(
            ExtractedJobPosting(
                job_id=build_job_id(
                    raw.source,
                    raw.source_job_id,
                    raw.source_url,
                    content_hash,
                ),
                content_hash=content_hash,
                content_hash_sha256=raw.content_hash_sha256,
                source=raw.source,
                source_id=raw.source_id,
                source_job_id=raw.source_job_id,
                source_url=raw.source_url,
                title_raw=raw.title_raw,
                job_title_raw=raw.title_raw,
                career_id=career_id,
                career_name=career_name,
                title_confidence=title_confidence,
                career_mapping_confidence=title_confidence,
                company_name=clean_text(raw.company_name_raw) or None,
                description_raw=raw.description_raw,
                description_clean=clean_text(role_description),
                description_role_specific=raw.description_role_specific,
                province=province,
                work_mode=work_mode,
                salary_raw=raw.salary_raw,
                salary_min_vnd=salary_min,
                salary_max_vnd=salary_max,
                salary_mid_vnd=salary_mid,
                salary_disclosed=salary_disclosed,
                seniority=seniority,
                seniority_level=seniority,
                experience_min_years=extract_experience_years(
                    raw.experience_raw or role_description
                ),
                education_level=normalize_education(raw.education_raw),
                posted_at=parse_posted_date(
                    raw.posted_at_raw, raw.collected_at
                ),
                collected_at=raw.collected_at,
                source_updated_at=raw.source_updated_at,
                first_seen_at=raw.collected_at,
                last_seen_at=raw.collected_at,
                skills=skills,
                extraction_model=EXTRACTION_MODEL,
                extraction_version=EXTRACTION_VERSION,
                taxonomy_version=taxonomy["taxonomy_version"],
                snapshot_version=snapshot_version,
                overall_confidence=overall_confidence,
                source_confidence=1.0 if raw.source == "greenhouse" else 0.8,
                normalization_version="rules-0.2.0",
                dedup_group_id=build_dedup_group_id(content_hash),
                duplicate_count=duplicate_counts[content_hash],
            )
        )

    return extracted_rows


def process_jobs(
    raw_json_path: str | Path,
    taxonomy_path: str | Path,
    snapshot_version: str,
) -> list[ExtractedJobPosting]:
    taxonomy = load_taxonomy(taxonomy_path)
    raw_rows = json.loads(Path(raw_json_path).read_text(encoding="utf-8"))
    raw_jobs = [RawJobPosting.model_validate(row) for row in raw_rows]
    return process_raw_jobs(raw_jobs, taxonomy, snapshot_version)


def process_greenhouse_jobs(
    interim_path: str | Path,
    taxonomy_path: str | Path,
    snapshot_version: str,
    description_debug_path: str | Path | None = None,
) -> list[ExtractedJobPosting]:
    """Build the canonical job schema from real Greenhouse interim data."""
    dataframe = pd.read_parquet(interim_path)
    dataframe = clean_job_descriptions(
        dataframe,
        group_column="source_id",
        frequency_threshold=0.80,
    )

    if description_debug_path is not None:
        debug_path = Path(description_debug_path)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_parquet(debug_path, index=False)

    def optional(row: pd.Series, column: str):
        value = row.get(column)
        return None if pd.isna(value) else value

    raw_jobs = [
        RawJobPosting(
            source=optional(row, "source") or "greenhouse",
            source_id=optional(row, "source_id"),
            source_job_id=str(row["source_job_id"]),
            source_url=optional(row, "source_url"),
            title_raw=str(row["job_title_raw"]),
            company_name_raw=optional(row, "company_name_raw"),
            description_raw=optional(row, "description_raw") or "",
            description_role_specific=optional(
                row, "description_role_specific"
            ),
            location_raw=optional(row, "location_raw"),
            work_mode_raw=None,
            experience_raw=optional(row, "experience_raw"),
            posted_at_raw=None,
            source_updated_at=optional(row, "updated_at_raw"),
            collected_at=optional(row, "fetched_at"),
            content_hash_sha256=optional(row, "content_hash_sha256"),
            raw_payload={},
        )
        for _, row in dataframe.iterrows()
    ]

    taxonomy = load_taxonomy(taxonomy_path)
    return process_raw_jobs(raw_jobs, taxonomy, snapshot_version)




def process_viecoi_jobs(
    interim_path: str | Path,
    taxonomy_path: str | Path,
    snapshot_version: str,
) -> list[ExtractedJobPosting]:
    """
    Chuyển dữ liệu ViecOi listing về schema RawJobPosting chung.

    ViecOi pilot chỉ thu thập job card, không mở trang chi tiết.
    Vì vậy card_text_raw và skills_raw được dùng làm nội dung
    đặc thù để chuẩn hóa nghề và trích xuất kỹ năng.
    """
    dataframe = pd.read_parquet(interim_path)

    required_columns = {
        "source_job_id",
        "job_title_raw",
        "fetched_at",
    }

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise KeyError(
            "ViecOi interim thiếu các cột bắt buộc: "
            f"{sorted(missing_columns)}"
        )

    def optional(
        row: pd.Series,
        column: str,
    ):
        value = row.get(column)

        if value is None:
            return None

        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass

        return value

    def parse_skill_tags(value) -> list[str]:
        if value is None:
            return []

        if isinstance(value, list):
            parsed = value
        else:
            try:
                parsed = json.loads(str(value))
            except (json.JSONDecodeError, TypeError):
                parsed = []

        if not isinstance(parsed, list):
            return []

        result: list[str] = []

        for item in parsed:
            skill = clean_text(item)

            if skill and skill not in result:
                result.append(skill)

        return result

    def build_role_description(row: pd.Series) -> str:
        parts: list[str] = []
        card_text = optional(row, "card_text_raw")

        if card_text:
            parts.append(str(card_text))

        skill_tags = parse_skill_tags(optional(row, "skills_raw"))

        if skill_tags:
            # One listing tag per line prevents a negation/noise tag from
            # changing the requirement level of neighbouring skill tags.
            parts.append("Kỹ năng:\n" + "\n".join(skill_tags))

        if not parts:
            parts.append(str(row["job_title_raw"]))

        return "\n".join(parts)

    raw_jobs: list[RawJobPosting] = []

    for _, row in dataframe.iterrows():
        role_description = build_role_description(row)
        collected_at = optional(row, "collected_at") or optional(
            row, "fetched_at"
        )

        raw_jobs.append(
            RawJobPosting(
                source=optional(row, "source") or "viecoi",
                source_id=optional(row, "source_id") or "viecoi_listing",
                source_job_id=str(row["source_job_id"]),
                source_url=optional(row, "source_url"),
                title_raw=str(row["job_title_raw"]),
                company_name_raw=optional(row, "company_name_raw"),
                description_raw=role_description,
                description_role_specific=role_description,
                location_raw=optional(row, "location_raw"),
                work_mode_raw=optional(row, "work_mode_raw"),
                salary_raw=optional(row, "salary_raw"),
                experience_raw=optional(row, "experience_raw"),
                education_raw=optional(row, "education_raw"),
                posted_at_raw=None,
                source_updated_at=None,
                collected_at=collected_at,
                content_hash_sha256=optional(row, "content_hash_sha256"),
                raw_payload={
                    "skill_requirement_level": "mentioned",
                    "skills_raw": parse_skill_tags(
                        optional(row, "skills_raw")
                    ),
                    "application_deadline_raw": optional(
                        row, "application_deadline_raw"
                    ),
                    "listing_url": optional(row, "listing_url"),
                    "listing_page": optional(row, "listing_page"),
                    "collection_scope": optional(row, "collection_scope"),
                },
            )
        )

    taxonomy = load_taxonomy(taxonomy_path)
    return process_raw_jobs(raw_jobs, taxonomy, snapshot_version)


def save_outputs(
    extracted_rows: list[ExtractedJobPosting],
    jobs_path: str | Path,
    skills_path: str | Path,
) -> None:
    extracted_rows = deduplicate_extracted_rows(extracted_rows)
    jobs_records = []
    skills_records = []

    for job in extracted_rows:
        record = job.model_dump(mode="json")
        skills = record.pop("skills")
        jobs_records.append(record)

        for skill in skills:
            skills_records.append({
                "job_id": job.job_id,
                "dedup_group_id": job.dedup_group_id,
                "career_id": job.career_id,
                "career_name": job.career_name,
                "province": job.province,
                "work_mode": job.work_mode,
                "posted_at": str(job.posted_at) if job.posted_at else None,
                **skill,
            })

    Path(jobs_path).parent.mkdir(parents=True, exist_ok=True)
    Path(skills_path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(jobs_records).to_parquet(jobs_path, index=False)

    skill_columns = [
        "job_id",
        "dedup_group_id",
        "career_id",
        "career_name",
        "province",
        "work_mode",
        "posted_at",
        "skill_id",
        "skill_name",
        "raw_mention",
        "requirement_level",
        "confidence",
        "extraction_method",
    ]
    pd.DataFrame(skills_records, columns=skill_columns).to_parquet(
        skills_path, index=False
    )


def deduplicate_extracted_rows(
    extracted_rows: list[ExtractedJobPosting],
) -> list[ExtractedJobPosting]:
    """
    Remove duplicate identities within one source and conservatively group
    potential cross-source duplicates without merging provenance.
    """
    by_identity: dict[tuple[str, str], ExtractedJobPosting] = {}

    for row in extracted_rows:
        key = (
            str(row.source_id or row.source),
            str(row.source_job_id or row.job_id),
        )
        by_identity[key] = row

    unique_rows = list(by_identity.values())
    candidate_groups: dict[str, list[int]] = {}

    for index, row in enumerate(unique_rows):
        candidate_key = build_cross_source_dedup_key(
            row.job_title_raw,
            row.company_name,
            row.province,
        )
        if candidate_key:
            candidate_groups.setdefault(candidate_key, []).append(index)

    for candidate_key, indices in candidate_groups.items():
        source_ids = {
            str(unique_rows[index].source_id)
            for index in indices
        }
        if len(source_ids) < 2:
            continue

        group_id = build_dedup_group_id(
            build_content_hash(candidate_key, None, None, "")
        )
        group_size = len(indices)

        for index in indices:
            unique_rows[index] = unique_rows[index].model_copy(
                update={
                    "dedup_group_id": group_id,
                    "duplicate_count": group_size,
                }
            )

    return unique_rows
