"""HTTP request contracts for the assessment module."""
from typing import Any

from pydantic import BaseModel, Field


class AssessmentSubmission(BaseModel):
    assessment_id: str
    question_set_id: str
    mode: str = "standard_25_35_min"
    seed: int
    responses: dict[str, Any] = Field(default_factory=dict)


class AssessmentDraftUpdate(BaseModel):
    question_set_id: str
    version: int = Field(ge=1)
    current_question_id: str | None = Field(default=None, max_length=120)
    responses: dict[str, Any] = Field(default_factory=dict)
