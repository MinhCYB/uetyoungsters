"""
Pydantic models dung chung - la "hop dong" API giua cac service.

Internalised from core/shared/schemas.py during the self-containment
refactor.  The import path for market contracts has been updated to use
the local market module.

QUAN TRONG: day la file rui ro conflict cao nhat.
Moi thay doi phai bao cho nguoi viet client goi API tuong ung.

Cac model danh dau "** DRAFT **" la suy luan toi thieu tu ten field / boi canh,
CHUA duoc Doi truong chot chi tiet - can xac nhan lai truoc khi 2 service kia
code theo, dac biet la field don vi/thang do (level, score, weight).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from .market import ExtractedSkill, JobPostingRecord


# ==========================================================================
# Enums dung chung
# ==========================================================================

class EducationLevel(str, Enum):
    """** DRAFT ** - can Nguoi 2 xac nhan day du cac muc, vi du co "vocational" hay khong."""
    HIGH_SCHOOL = "high_school"
    VOCATIONAL = "vocational"
    COLLEGE_OR_ABOVE = "college_or_above"
    UNIVERSITY = "university"
    POSTGRADUATE = "postgraduate"


class ActionType(str, Enum):
    SELF_STUDY = "self_study"
    VOCATIONAL = "vocational"
    UNIVERSITY = "university"
    PORTFOLIO = "portfolio"


class PathwayTimeframe(str, Enum):
    SHORT_TERM = "0-3 thang"
    MID_TERM = "3-12 thang"


class FeedbackType(str, Enum):
    HIDE_CAREER = "hide_career"
    NOT_INTERESTED = "not_interested"
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    COMMENT = "comment"


# Market contracts are imported from ``crawl_service.shared_contracts.market``.
# Student profile and recommendation models remain in this module because
# they belong to separate bounded contexts.


# ==========================================================================
# 2. profile-service - student_profiles (Bang 4)
#    core CHI NHAN qua API luc runtime, khong tu luu profile trong core DB.
# ==========================================================================

class EducationContext(BaseModel):
    """** DRAFT ** field_of_study la BAT BUOC neu level la university/postgraduate
    (theo yeu cau rieng cua Doi truong). school_type khong duoc ghi ten truong cu
    the de tranh PII (xem notes muc 12)."""

    level: EducationLevel
    field_of_study: Optional[str] = None
    school_type: Optional[str] = None

    @model_validator(mode="after")
    def _require_field_of_study_for_university(self) -> "EducationContext":
        if self.level in (EducationLevel.UNIVERSITY, EducationLevel.POSTGRADUATE):
            if not self.field_of_study:
                raise ValueError(
                    "field_of_study la bat buoc khi education.level la "
                    "university hoac postgraduate"
                )
        return self


class LocationConstraint(BaseModel):
    """** DRAFT **"""

    preferred_provinces: list[str] = Field(default_factory=list)
    open_to_remote: bool = False
    open_to_relocate: bool = False


class TrainingConstraint(BaseModel):
    """** DRAFT **"""

    hours_per_week: Optional[float] = None
    preferred_pathway: Optional[str] = None  # "university" | "vocational" | "self_study" | "undecided"
    budget_level: Optional[str] = None       # "low" | "medium" | "high"


class ProfileSignal(BaseModel):
    """Confidence = EvidenceCoverage x QuestionReliability x AnswerCompleteness
    (cong thuc do Doi truong cung cap)."""

    dimension: str
    score: float
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    source: str
    evidence: str
    user_confirmed: bool = False
    created_at: datetime
    expires_at: Optional[datetime] = None


class SkillProfile(BaseModel):
    """** DRAFT ** - thang do `level` chua duoc chot (0-1 hay 0-100)."""

    skill_id: str
    skill_name: str
    level: float
    confidence: float = Field(ge=0.0, le=1.0)
    source: str


class AbilityDimension(BaseModel):
    """** DRAFT **"""

    dimension: str
    score: float
    confidence: float = Field(ge=0.0, le=1.0)


class CareerValue(BaseModel):
    """** DRAFT ** vi du value = "stability" | "creativity" | "impact"."""

    value: str
    weight: float


class WorkPreference(BaseModel):
    """** DRAFT ** vi du preference = "teamwork" | "independent" | "fieldwork"."""

    preference: str
    weight: float


class ConsentSettings(BaseModel):
    """** DRAFT ** gan voi anonymous session, khong phai user account."""

    data_usage_ack: bool
    share_enabled: bool = False
    share_expires_at: Optional[datetime] = None


class StudentProfile(BaseModel):
    id: str
    taxonomy_version: str

    education: EducationContext
    location_constraints: LocationConstraint
    training_constraints: TrainingConstraint

    interests: list[ProfileSignal] = Field(default_factory=list)
    strengths: list[ProfileSignal] = Field(default_factory=list)
    skills: list[SkillProfile] = Field(default_factory=list)
    abilities: list[AbilityDimension] = Field(default_factory=list)
    career_values: list[CareerValue] = Field(default_factory=list)
    work_preferences: list[WorkPreference] = Field(default_factory=list)

    exploration_interests: list[ProfileSignal] = Field(default_factory=list)

    profile_version: int
    consent_settings: ConsentSettings
    updated_at: datetime


# ==========================================================================
# 3. core - recommendations (Bang 5)
#    Match score BAT BUOC deterministic - rule-based weighted scoring.
#    LLM chi dien giai `reason`, khong tu cham `total` (quyet dinh 6.3).
# ==========================================================================

class SkillGapItem(BaseModel):
    skill: str
    current_level: float
    required_level: float


class ScoreBreakdown(BaseModel):
    """Trong so: interest 30% / skill 30% / market_demand 20% /
    work_preference 10% / location 10%. Trong so thuc te dat trong
    core/shared/constants.py, khong hardcode o day."""

    interest_match: float
    skill_match: float
    market_demand: float
    work_preference_match: float
    location_compatibility: float
    total: float = Field(ge=0.0, le=100.0)


class PathwayMilestone(BaseModel):
    """Pathway gioi han 0-12 thang, khong cam ket lo trinh 3-5 nam."""

    title: str
    duration: str  # vd: "3 tuan"
    goal: str
    reason: str
    evidence: dict[str, Any]  # vd {"source_snapshot": ..., "frequency": ...}
    timeframe: PathwayTimeframe
    action_type: ActionType


class CareerRecommendation(BaseModel):
    id: str
    session_id: str
    student_profile_id: str
    profile_version: int
    demand_snapshot_version: str
    scoring_version: str
    career_id: str
    score_breakdown: ScoreBreakdown
    skill_gaps: list[SkillGapItem] = Field(default_factory=list)
    pathway: list[PathwayMilestone] = Field(default_factory=list)
    is_alternative_of: Optional[str] = None
    bias_check_passed: bool
    disclaimer: str
    created_at: datetime


# ==========================================================================
# 4. core - recommendation_feedback (Bang 6)
#    Feedback CHI dung de an nghe / danh gia huu ich / ghi chu.
#    KHONG dung de sua profile - sua profile di qua PATCH /profile/current
#    rieng (o profile-service), tao profile_version moi.
# ==========================================================================

class RecommendationFeedback(BaseModel):
    session_id: str
    recommendation_id: str
    feedback_type: FeedbackType
    career_id: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime
