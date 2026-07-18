"""Canonical consumer contracts for Data Layer processed market tables.

Internalised from core/shared/contracts/market.py during the
self-containment refactor.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class RequirementLevel(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    NOT_REQUIRED = "not_required"
    MENTIONED = "mentioned"
    NICE_TO_HAVE = "nice_to_have"


class ExtractionMethod(str, Enum):
    TAXONOMY = "taxonomy"
    FUZZY = "fuzzy"
    RULE = "rule"
    LLM_FALLBACK = "llm_fallback"


class WorkMode(str, Enum):
    ONSITE = "ONSITE"
    HYBRID = "HYBRID"
    REMOTE = "REMOTE"
    UNSPECIFIED = "UNSPECIFIED"


class MarketJobRecord(BaseModel):
    """Row-level contract for ``jobs_clean.parquet`` consumers."""

    job_id: str
    source: str
    source_id: str
    source_job_id: str
    source_url: str | None = None
    job_title_raw: str
    career_id: str | None = None
    career_name: str | None = None
    company_name: str | None = None
    province: str | None = None
    work_mode: WorkMode = WorkMode.UNSPECIFIED
    salary_min_vnd: int | None = None
    salary_max_vnd: int | None = None
    salary_mid_vnd: float | None = None
    salary_disclosed: bool = False
    seniority_level: str
    experience_min_years: float | None = None
    education_level: str
    posted_at: date | None = None
    collected_at: datetime
    snapshot_version: str
    taxonomy_version: str
    overall_confidence: float = Field(ge=0.0, le=1.0)
    is_active: bool


class MarketSkillRecord(BaseModel):
    """Row-level contract for ``job_skills.parquet`` consumers."""

    job_id: str
    career_id: str | None = None
    skill_id: str
    skill_name: str
    raw_mention: str
    requirement_level: RequirementLevel
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_method: ExtractionMethod


# Compatibility import aliases for the existing core skeleton.
# The row-level market contract is intentionally different
# from the previous draft schema.
JobPostingRecord = MarketJobRecord
ExtractedSkill = MarketSkillRecord
