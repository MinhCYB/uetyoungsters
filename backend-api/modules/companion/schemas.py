"""HTTP request schemas for the Student Companion demo integration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyzeRequest(RequestModel):
    student_id: str = "stu_uet_0001"
    profile_version: int = Field(default=1, ge=1)
    fixture_selector: Literal["initial"] = "initial"


class PlanRequest(RequestModel):
    analysis_id: str


class FollowupRequest(RequestModel):
    baseline_analysis_id: str
    student_id: str = "stu_uet_0001"
    profile_version: int = Field(default=2, ge=1)
    fixture_selector: Literal["week3"] = "week3"


class ExpandPlanRequest(RequestModel):
    plan_id: str
    task_id: str
    max_steps: int = Field(default=4, ge=2, le=6)


class ReassessmentRequest(RequestModel):
    plan_id: str
    target_skill_id: str
    question_count: int = Field(default=3, ge=3, le=10)
    max_score: float = Field(default=10.0, gt=0)


class FeedbackRequest(RequestModel):
    student_id: str = "stu_uet_0001"
    question_id: str
    skill_id: str
    question_prompt: str
    student_answer: str
    expected_answer: str
    is_correct: bool
    detected_error_type: str | None = None


class ErrorBody(RequestModel):
    code: str
    message: str
    details: list[dict] = Field(default_factory=list)
