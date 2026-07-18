"""Strict internal contracts for controlled content generation."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from phase1_demo.student_companion.domain import AbilityEstimate, Gap, PlanTask, TaskType


CONTENT_CONTRACT_VERSION = "1.0.0"
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Difficulty = Literal["foundation", "standard", "stretch"]
ContentMode = Literal["external_llm", "fake_provider", "template_fallback"]
QuestionType = Literal["multiple_choice", "short_answer"]
FeedbackDepth = Literal["hint", "explanation", "worked_solution"]


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ContentGenerationMetadata(ContentModel):
    content_contract_version: Literal["1.0.0"]
    request_id: NonEmptyStr
    prompt_version: NonEmptyStr
    student_id: NonEmptyStr
    language: NonEmptyStr
    grade_level: Annotated[int, Field(ge=10, le=12)]


class ContentGenerationResultMetadata(ContentModel):
    content_mode: ContentMode
    provider_name: NonEmptyStr
    prompt_version: NonEmptyStr
    validation_attempts: Annotated[int, Field(ge=1, le=2)]
    warnings: list[NonEmptyStr]

    @model_validator(mode="after")
    def validate_unique_warnings(self):
        if len(self.warnings) != len(set(self.warnings)):
            raise ValueError("warnings must not contain duplicates")
        return self


class PlanExpansionRequest(ContentModel):
    metadata: ContentGenerationMetadata
    task: PlanTask
    relevant_ability: AbilityEstimate | None
    relevant_gap: Gap | None
    student_preferences: list[NonEmptyStr]
    prohibited_topics: list[NonEmptyStr]
    max_steps: Annotated[int, Field(ge=2, le=6)]
    difficulty: Difficulty

    @model_validator(mode="after")
    def validate_task_scope(self):
        if self.task.task_type not in {
            TaskType.ACADEMIC_PRACTICE,
            TaskType.CAREER_MICRO_EXPERIENCE,
        }:
            raise ValueError("task must be academic practice or career micro-experience")
        if self.task.estimated_minutes < 2:
            raise ValueError("task needs at least two minutes for a multi-step plan")
        if len(self.student_preferences) != len(set(self.student_preferences)):
            raise ValueError("student_preferences must not contain duplicates")
        if len(self.prohibited_topics) != len(set(self.prohibited_topics)):
            raise ValueError("prohibited_topics must not contain duplicates")
        if self.relevant_ability and self.task.skill_id:
            if self.relevant_ability.skill_id != self.task.skill_id:
                raise ValueError("relevant_ability must match task.skill_id")
        if self.relevant_gap:
            if self.task.skill_id and self.relevant_gap.skill_id != self.task.skill_id:
                raise ValueError("relevant_gap must match task.skill_id")
            if self.task.career_group_id and self.task.career_group_id not in self.relevant_gap.career_group_ids:
                raise ValueError("relevant_gap must match task.career_group_id")
        return self


class DetailedPlanStep(ContentModel):
    step_number: Annotated[int, Field(gt=0)]
    title: NonEmptyStr
    instruction: NonEmptyStr
    estimated_minutes: Annotated[int, Field(gt=0)]
    completion_check: NonEmptyStr


class DetailedLearningPlan(ContentModel):
    content_id: NonEmptyStr
    source_task_id: NonEmptyStr
    title: NonEmptyStr
    objective: NonEmptyStr
    skill_id: NonEmptyStr | None
    career_group_id: NonEmptyStr | None
    total_minutes: Annotated[int, Field(gt=0)]
    steps: Annotated[list[DetailedPlanStep], Field(min_length=2, max_length=6)]
    completion_criteria: Annotated[list[NonEmptyStr], Field(min_length=1)]
    reflection_question: str | None
    result_metadata: ContentGenerationResultMetadata

    @model_validator(mode="after")
    def validate_plan_shape(self):
        numbers = [item.step_number for item in self.steps]
        if numbers != list(range(1, len(self.steps) + 1)):
            raise ValueError("step_number values must be consecutive from one")
        if sum(item.estimated_minutes for item in self.steps) != self.total_minutes:
            raise ValueError("step minutes must sum to total_minutes")
        return self


class ReassessmentGenerationRequest(ContentModel):
    metadata: ContentGenerationMetadata
    assessment_id: NonEmptyStr
    target_skill_id: NonEmptyStr
    question_count: Annotated[int, Field(ge=3, le=10)]
    difficulty: Difficulty
    max_score: Annotated[float, Field(gt=0)]
    estimated_minutes: Annotated[int, Field(gt=0)] | None = None
    allowed_question_types: Annotated[list[QuestionType], Field(min_length=1)]
    prior_question_fingerprints: list[NonEmptyStr]
    learning_objective: NonEmptyStr

    @model_validator(mode="after")
    def validate_unique_values(self):
        if len(self.allowed_question_types) != len(set(self.allowed_question_types)):
            raise ValueError("allowed_question_types must not contain duplicates")
        if len(self.prior_question_fingerprints) != len(set(self.prior_question_fingerprints)):
            raise ValueError("prior_question_fingerprints must not contain duplicates")
        return self


class ReassessmentQuestion(ContentModel):
    question_id: NonEmptyStr
    skill_id: NonEmptyStr
    question_type: QuestionType
    prompt: NonEmptyStr
    options: list[NonEmptyStr]
    correct_answer: NonEmptyStr
    explanation: NonEmptyStr
    score: Annotated[float, Field(gt=0)]
    difficulty: Difficulty
    fingerprint: NonEmptyStr

    @model_validator(mode="after")
    def validate_question_shape(self):
        if self.question_type == "multiple_choice":
            if len(self.options) < 3:
                raise ValueError("multiple_choice requires at least three options")
            if len(self.options) != len(set(self.options)):
                raise ValueError("options must not contain duplicates")
            if self.correct_answer not in self.options:
                raise ValueError("correct_answer must be one of the options")
        elif self.options:
            raise ValueError("short_answer options must be empty")
        return self


class ReassessmentPackage(ContentModel):
    content_id: NonEmptyStr
    assessment_id: NonEmptyStr
    target_skill_id: NonEmptyStr
    questions: Annotated[list[ReassessmentQuestion], Field(min_length=1)]
    total_score: Annotated[float, Field(gt=0)]
    estimated_minutes: Annotated[int, Field(gt=0)]
    result_metadata: ContentGenerationResultMetadata

    @model_validator(mode="after")
    def validate_package_shape(self):
        question_ids = [item.question_id for item in self.questions]
        fingerprints = [item.fingerprint for item in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("question_id values must be unique")
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("question fingerprints must be unique")
        if not math.isclose(
            sum(item.score for item in self.questions),
            self.total_score,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError("question scores must sum to total_score")
        return self


class FeedbackGenerationRequest(ContentModel):
    metadata: ContentGenerationMetadata
    question_id: NonEmptyStr
    skill_id: NonEmptyStr
    question_prompt: NonEmptyStr
    student_answer: NonEmptyStr
    expected_answer: NonEmptyStr
    is_correct: bool
    detected_error_type: str | None
    feedback_depth: FeedbackDepth
    max_followup_questions: Annotated[int, Field(ge=0, le=1)]


class PersonalizedFeedback(ContentModel):
    content_id: NonEmptyStr
    question_id: NonEmptyStr
    skill_id: NonEmptyStr
    summary: NonEmptyStr
    hint: str | None
    error_explanation: str | None
    worked_solution_steps: list[NonEmptyStr]
    encouragement: NonEmptyStr
    followup_question: str | None
    result_metadata: ContentGenerationResultMetadata
