"""Validated, deterministic data contracts for Student Companion Phase 1.

The models in this module represent input and derived data only. They perform
consistency validation but do not calculate abilities, gaps, plans or outcomes.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .enums import (
    AbilityTrend,
    AssessmentType,
    CareerClarity,
    EvidenceSourceType,
    GapPriority,
    GapType,
    ObservationType,
    OutcomeStatus,
    Severity,
    TaskType,
)


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]
PositiveFloat = Annotated[float, Field(gt=0.0)]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


def _has_duplicates(values: list[str]) -> bool:
    return len(values) != len(set(values))


class DomainModel(BaseModel):
    """Shared serialization policy for all domain contracts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StudentProfile(DomainModel):
    student_id: NonEmptyStr
    display_name: NonEmptyStr
    grade_level: Annotated[int, Field(ge=10, le=12)]
    weekly_available_minutes: PositiveInt
    career_interest_ids: list[NonEmptyStr]
    career_clarity: CareerClarity
    exam_week: bool
    schema_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_unique_career_interests(self) -> StudentProfile:
        if _has_duplicates(self.career_interest_ids):
            raise ValueError("career_interest_ids must not contain duplicates")
        return self


class AcademicRecord(DomainModel):
    record_id: NonEmptyStr
    student_id: NonEmptyStr
    subject_id: NonEmptyStr
    topic_id: NonEmptyStr
    score: Annotated[float, Field(ge=0.0)]
    max_score: PositiveFloat
    observed_at: datetime | date
    source: NonEmptyStr
    schema_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_score_range(self) -> AcademicRecord:
        if self.score > self.max_score:
            raise ValueError("score must be less than or equal to max_score")
        return self


class TeacherObservation(DomainModel):
    observation_id: NonEmptyStr
    student_id: NonEmptyStr
    skill_id: NonEmptyStr
    observation_type: ObservationType
    severity: Severity
    confidence: UnitInterval
    note: NonEmptyStr
    observed_at: datetime | date
    schema_version: NonEmptyStr


class SkillScore(DomainModel):
    skill_id: NonEmptyStr
    score: Annotated[float, Field(ge=0.0)]
    max_score: PositiveFloat

    @model_validator(mode="after")
    def validate_score_range(self) -> SkillScore:
        if self.score > self.max_score:
            raise ValueError("score must be less than or equal to max_score")
        return self


class AssessmentAttempt(DomainModel):
    attempt_id: NonEmptyStr
    student_id: NonEmptyStr
    assessment_id: NonEmptyStr
    assessment_type: AssessmentType
    skill_scores: Annotated[list[SkillScore], Field(min_length=1)]
    completed_at: datetime
    assessment_version: NonEmptyStr
    schema_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_unique_skill_scores(self) -> AssessmentAttempt:
        skill_ids = [item.skill_id for item in self.skill_scores]
        if _has_duplicates(skill_ids):
            raise ValueError("skill_scores must not contain duplicate skill_id values")
        return self


class CareerInterestRating(DomainModel):
    career_group_id: NonEmptyStr
    interest_score: Annotated[float, Field(ge=0.0)]
    max_score: PositiveFloat

    @model_validator(mode="after")
    def validate_interest_range(self) -> CareerInterestRating:
        if self.interest_score > self.max_score:
            raise ValueError("interest_score must be less than or equal to max_score")
        return self


class SelfReport(DomainModel):
    report_id: NonEmptyStr
    student_id: NonEmptyStr
    career_interests: list[CareerInterestRating]
    preferred_task_types: list[NonEmptyStr]
    stated_strength_skill_ids: list[NonEmptyStr]
    stated_weakness_skill_ids: list[NonEmptyStr]
    note: str | None
    observed_at: datetime
    schema_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_unique_lists(self) -> SelfReport:
        career_ids = [item.career_group_id for item in self.career_interests]
        if _has_duplicates(career_ids):
            raise ValueError("career_interests must not contain duplicate career_group_id values")
        if _has_duplicates(self.stated_strength_skill_ids):
            raise ValueError("stated_strength_skill_ids must not contain duplicates")
        if _has_duplicates(self.stated_weakness_skill_ids):
            raise ValueError("stated_weakness_skill_ids must not contain duplicates")
        return self


class ActivityResult(DomainModel):
    activity_result_id: NonEmptyStr
    activity_id: NonEmptyStr
    student_id: NonEmptyStr
    career_group_id: NonEmptyStr
    completed: bool
    rubric_score: Annotated[float, Field(ge=0.0)] | None
    max_score: PositiveFloat | None
    interest_before: Annotated[float, Field(ge=0.0)]
    interest_after: Annotated[float, Field(ge=0.0)]
    interest_max_score: PositiveFloat
    preferred_part: str | None
    completed_at: datetime
    activity_version: NonEmptyStr
    schema_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_scores(self) -> ActivityResult:
        if self.interest_before > self.interest_max_score:
            raise ValueError("interest_before must not exceed interest_max_score")
        if self.interest_after > self.interest_max_score:
            raise ValueError("interest_after must not exceed interest_max_score")
        if self.completed and (self.rubric_score is None or self.max_score is None):
            raise ValueError("completed activities require rubric_score and max_score")
        if self.rubric_score is not None and self.max_score is None:
            raise ValueError("rubric_score requires max_score")
        if (
            self.rubric_score is not None
            and self.max_score is not None
            and self.rubric_score > self.max_score
        ):
            raise ValueError("rubric_score must be less than or equal to max_score")
        return self


class Evidence(DomainModel):
    evidence_id: NonEmptyStr
    student_id: NonEmptyStr
    skill_id: NonEmptyStr
    source_type: EvidenceSourceType
    raw_value: float
    normalized_value: UnitInterval
    confidence: UnitInterval
    observed_at: datetime
    source_reference: NonEmptyStr
    evidence_version: NonEmptyStr


class AbilityEstimate(DomainModel):
    skill_id: NonEmptyStr
    estimated_level: UnitInterval
    confidence: UnitInterval
    trend: AbilityTrend
    evidence_ids: list[NonEmptyStr]
    estimate_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_unique_evidence_ids(self) -> AbilityEstimate:
        if _has_duplicates(self.evidence_ids):
            raise ValueError("evidence_ids must not contain duplicates")
        return self


class Gap(DomainModel):
    gap_id: NonEmptyStr
    gap_type: GapType
    skill_id: NonEmptyStr | None
    career_group_ids: list[NonEmptyStr]
    current_level: UnitInterval | None
    expected_level: UnitInterval | None
    gap_size: UnitInterval | None
    priority: GapPriority
    reason: NonEmptyStr
    evidence_ids: list[NonEmptyStr]
    gap_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_gap_shape(self) -> Gap:
        if self.gap_type is GapType.ACADEMIC:
            if self.skill_id is None:
                raise ValueError("academic gap requires skill_id")
            if self.current_level is None or self.expected_level is None or self.gap_size is None:
                raise ValueError(
                    "academic gap requires current_level, expected_level and gap_size"
                )
        elif self.gap_type is GapType.EXPLORATION:
            if len(self.career_group_ids) != 1:
                raise ValueError("exploration gap requires exactly one career_group_id")
        elif self.gap_type is GapType.DECISION and len(self.career_group_ids) < 2:
            raise ValueError("decision gap requires at least two career_group_ids")

        if _has_duplicates(self.evidence_ids):
            raise ValueError("evidence_ids must not contain duplicates")
        return self


class MarketCareerGroup(DomainModel):
    career_group_id: NonEmptyStr
    display_name: NonEmptyStr
    market_signal: NonEmptyStr
    sample_size: NonNegativeInt
    foundation_skill_ids: list[NonEmptyStr]
    snapshot_version: NonEmptyStr
    taxonomy_version: NonEmptyStr | None
    data_mode: Literal["pipeline_export", "fallback_demo"]
    source_output_files: list[NonEmptyStr]

    @model_validator(mode="after")
    def validate_unique_foundation_skills(self) -> MarketCareerGroup:
        if _has_duplicates(self.foundation_skill_ids):
            raise ValueError("foundation_skill_ids must not contain duplicates")
        return self


class PlanTask(DomainModel):
    task_id: NonEmptyStr
    task_type: TaskType
    title: NonEmptyStr
    skill_id: NonEmptyStr | None
    career_group_id: NonEmptyStr | None
    estimated_minutes: PositiveInt
    reason: NonEmptyStr
    evidence_ids: list[NonEmptyStr]
    activity_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_task_reference(self) -> PlanTask:
        if self.task_type is TaskType.ACADEMIC_PRACTICE and self.skill_id is None:
            raise ValueError("academic_practice requires skill_id")
        if (
            self.task_type is TaskType.CAREER_MICRO_EXPERIENCE
            and self.career_group_id is None
        ):
            raise ValueError("career_micro_experience requires career_group_id")
        if _has_duplicates(self.evidence_ids):
            raise ValueError("evidence_ids must not contain duplicates")
        return self


class WeeklyPlan(DomainModel):
    plan_id: NonEmptyStr
    student_id: NonEmptyStr
    weekly_budget_minutes: PositiveInt
    total_planned_minutes: NonNegativeInt
    tasks: list[PlanTask]
    generated_at: datetime
    rule_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_plan_consistency(self) -> WeeklyPlan:
        if self.total_planned_minutes > self.weekly_budget_minutes:
            raise ValueError("total_planned_minutes must not exceed weekly_budget_minutes")
        task_ids = [task.task_id for task in self.tasks]
        if _has_duplicates(task_ids):
            raise ValueError("tasks must not contain duplicate task_id values")
        expected_total = sum(task.estimated_minutes for task in self.tasks)
        if self.total_planned_minutes != expected_total:
            raise ValueError("total_planned_minutes must equal the sum of task minutes")
        return self


class OutcomeEvaluation(DomainModel):
    evaluation_id: NonEmptyStr
    student_id: NonEmptyStr
    metric_type: NonEmptyStr
    before_value: float
    after_value: float
    delta: float
    status: OutcomeStatus
    evidence_ids: list[NonEmptyStr]
    rule_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_delta(self) -> OutcomeEvaluation:
        expected_delta = self.after_value - self.before_value
        if not math.isclose(self.delta, expected_delta, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("delta must equal after_value - before_value")
        if _has_duplicates(self.evidence_ids):
            raise ValueError("evidence_ids must not contain duplicates")
        return self


class StudentSnapshot(DomainModel):
    snapshot_id: NonEmptyStr
    previous_snapshot_id: NonEmptyStr | None
    student_id: NonEmptyStr
    created_at: datetime
    ability_profile: list[AbilityEstimate]
    gaps: list[Gap]
    active_plan: WeeklyPlan | None
    outcomes: list[OutcomeEvaluation]
    market_snapshot_version: NonEmptyStr
    pipeline_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_snapshot_consistency(self) -> StudentSnapshot:
        if self.snapshot_id == self.previous_snapshot_id:
            raise ValueError("snapshot_id must differ from previous_snapshot_id")
        skill_ids = [estimate.skill_id for estimate in self.ability_profile]
        if _has_duplicates(skill_ids):
            raise ValueError("ability_profile must not contain duplicate skill_id values")
        gap_ids = [gap.gap_id for gap in self.gaps]
        if _has_duplicates(gap_ids):
            raise ValueError("gaps must not contain duplicate gap_id values")
        return self
