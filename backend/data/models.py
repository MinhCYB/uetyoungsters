from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class RawJobPosting(BaseModel):
    source: str
    source_id: str | None = None
    source_job_id: str | None = None
    source_url: str | None = None
    title_raw: str
    company_name_raw: str | None = None
    description_raw: str
    description_role_specific: str | None = None
    industry_raw: str | None = None
    location_raw: str | None = None
    salary_raw: str | None = None
    experience_raw: str | None = None
    education_raw: str | None = None
    posted_at_raw: str | None = None
    work_mode_raw: str | None = None
    source_updated_at: str | None = None
    collected_at: datetime
    content_hash_sha256: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class SkillMention(BaseModel):
    skill_id: str
    skill_name: str
    raw_mention: str
    requirement_level: Literal["required", "preferred", "not_required", "mentioned"]
    confidence: float = Field(ge=0, le=1)
    extraction_method: Literal["taxonomy", "fuzzy", "llm_fallback"]


class ExtractedJobPosting(BaseModel):
    job_id: str
    content_hash: str
    source: str
    source_id: str | None = None
    source_job_id: str | None = None
    source_url: str | None = None
    title_raw: str
    job_title_raw: str
    career_id: str | None = None
    career_name: str | None = None
    title_confidence: float = Field(ge=0, le=1)
    company_name: str | None = None
    description_raw: str
    description_clean: str
    description_role_specific: str | None = None
    province: str | None = None
    work_mode: Literal[
        "ONSITE",
        "HYBRID",
        "REMOTE",
        "UNSPECIFIED",
    ] = "UNSPECIFIED"
    salary_raw: str | None = None
    salary_min_vnd: int | None = None
    salary_max_vnd: int | None = None
    salary_mid_vnd: float | None = None
    salary_disclosed: bool
    seniority: str
    seniority_level: str
    experience_min_years: float | None = None
    education_level: str
    posted_at: date | None = None
    collected_at: datetime
    source_updated_at: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    content_hash_sha256: str | None = None
    skills: list[SkillMention] = Field(default_factory=list)
    extraction_model: str
    extraction_version: str
    taxonomy_version: str
    snapshot_version: str
    overall_confidence: float = Field(ge=0, le=1)
    source_confidence: float = Field(ge=0, le=1)
    career_mapping_confidence: float = Field(ge=0, le=1)
    normalization_version: str
    dedup_group_id: str
    duplicate_count: int = 1
