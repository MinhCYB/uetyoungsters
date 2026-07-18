"""Versioned student profile contracts consumed by the AI analysis pipeline."""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessmentPurpose(str, Enum):
    DIAGNOSTIC = "diagnostic"
    PRETEST = "pretest"
    POSTTEST = "posttest"


class Student(ContractModel):
    student_id: str = Field(pattern=r"^stu_[a-z0-9_]+$")
    tenant_id: str = Field(pattern=r"^ten_[a-z0-9_]+$")
    class_id: str = Field(pattern=r"^cls_[a-z0-9_]+$")
    student_code: str
    display_name: str
    profile_type: Literal["HIGH_SCHOOL", "UNIVERSITY"]
    grade_level: str | None = None
    date_of_birth: date | None = None


class AcademicRecord(ContractModel):
    record_id: str = Field(pattern=r"^acr_[a-z0-9_]+$")
    student_id: str
    subject_id: str
    subject_name: str
    period: str
    score: float = Field(ge=0, le=10)
    score_scale: Literal[10] = 10
    recorded_at: datetime
    source: Literal["school_system", "teacher_entry", "verified_import"]


class TeacherObservation(ContractModel):
    observation_id: str = Field(pattern=r"^obs_[a-z0-9_]+$")
    student_id: str
    teacher_id: str
    observed_at: datetime
    context: Literal["classroom", "project", "club", "counseling", "other"]
    skill_ids: list[str] = Field(min_length=1)
    observation: str = Field(min_length=10, max_length=2000)
    visibility: Literal["analysis_only", "student_visible"] = "analysis_only"


class SkillScore(ContractModel):
    skill_id: str = Field(min_length=1)
    score: float
    max_score: float = Field(gt=0)
    evidence_item_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def score_within_scale(self):
        if self.score < 0 or self.score > self.max_score:
            raise ValueError("score must be between 0 and max_score")
        return self


class AssessmentAttempt(ContractModel):
    attempt_id: str = Field(pattern=r"^att_[a-z0-9_]+$")
    student_id: str
    assessment_id: str
    purpose: AssessmentPurpose
    started_at: datetime
    submitted_at: datetime | None = None
    status: Literal["in_progress", "submitted", "scored"]
    total_score: float | None = None
    total_max_score: float | None = Field(default=None, gt=0)
    skill_scores: list[SkillScore]

    @model_validator(mode="after")
    def scored_attempt_has_skill_scores(self):
        if self.status == "scored" and not self.skill_scores:
            raise ValueError("a scored assessment requires at least one skill_score")
        if self.status == "scored" and (self.submitted_at is None or self.total_score is None or self.total_max_score is None):
            raise ValueError("a scored assessment requires submitted_at and total scores")
        return self


class SelfReportedSkill(ContractModel):
    skill_id: str
    level: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class SelfReport(ContractModel):
    submitted_at: datetime
    interest_ids: list[str] = Field(default_factory=list)
    career_value_ids: list[str] = Field(default_factory=list)
    preferred_career_ids: list[str] = Field(default_factory=list)
    skills: list[SelfReportedSkill] = Field(default_factory=list)
    weekly_learning_hours: int | None = Field(default=None, ge=0, le=168)
    free_text: str | None = Field(default=None, max_length=3000)


class ActivityResult(ContractModel):
    activity_result_id: str = Field(pattern=r"^act_[a-z0-9_]+$")
    student_id: str
    activity_id: str
    completed_at: datetime
    skill_id: str
    score: float
    max_score: float = Field(gt=0)
    duration_minutes: int | None = Field(default=None, ge=0)
    evidence: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def score_within_scale(self):
        if self.score < 0 or self.score > self.max_score:
            raise ValueError("score must be between 0 and max_score")
        return self


class StudentProfilePayload(ContractModel):
    schema_version: Literal["1.0.0"]
    profile_version: int = Field(ge=1)
    generated_at: datetime
    student: Student
    academic_records: list[AcademicRecord]
    teacher_observations: list[TeacherObservation]
    assessment_attempts: list[AssessmentAttempt]
    self_report: SelfReport | None
    activity_results: list[ActivityResult]

    @model_validator(mode="after")
    def child_resources_belong_to_student(self):
        expected = self.student.student_id
        groups = (self.academic_records, self.teacher_observations, self.assessment_attempts, self.activity_results)
        if any(item.student_id != expected for group in groups for item in group):
            raise ValueError("all child resources must use student.student_id")
        return self


class InitialAnalysisRequest(ContractModel):
    request_id: str = Field(pattern=r"^iar_[a-z0-9_]+$")
    requested_at: datetime
    profile: StudentProfilePayload


class FollowupEvaluationRequest(ContractModel):
    request_id: str = Field(pattern=r"^fer_[a-z0-9_]+$")
    requested_at: datetime
    baseline_analysis_id: str
    window_started_at: datetime
    window_ended_at: datetime
    profile: StudentProfilePayload

    @model_validator(mode="after")
    def valid_window(self):
        if self.window_ended_at <= self.window_started_at:
            raise ValueError("window_ended_at must be after window_started_at")
        if not any(a.purpose == AssessmentPurpose.POSTTEST for a in self.profile.assessment_attempts):
            raise ValueError("follow-up evaluation requires at least one posttest")
        return self


def to_initial_analysis_request(payload: dict, *, request_id: str, requested_at: datetime) -> InitialAnalysisRequest:
    """Validate a raw profile snapshot and wrap it for initial AI analysis."""
    return InitialAnalysisRequest(request_id=request_id, requested_at=requested_at, profile=payload)


def to_followup_evaluation_request(
    payload: dict,
    *,
    request_id: str,
    requested_at: datetime,
    baseline_analysis_id: str,
    window_started_at: datetime,
    window_ended_at: datetime,
) -> FollowupEvaluationRequest:
    """Validate a later profile snapshot and wrap it for follow-up evaluation."""
    return FollowupEvaluationRequest(
        request_id=request_id,
        requested_at=requested_at,
        baseline_analysis_id=baseline_analysis_id,
        window_started_at=window_started_at,
        window_ended_at=window_ended_at,
        profile=payload,
    )
