"""Parsing, safety, and request-specific content invariants."""

from __future__ import annotations

import json
import math
import re
from typing import Iterable

from pydantic import ValidationError

from .contracts import (
    DetailedLearningPlan,
    FeedbackGenerationRequest,
    PersonalizedFeedback,
    PlanExpansionRequest,
    ReassessmentGenerationRequest,
    ReassessmentPackage,
)


class LLMProviderError(RuntimeError):
    """Provider call failed without exposing raw provider details."""


class LLMOutputParseError(ValueError):
    """Provider output was not a JSON object."""


class LLMOutputValidationError(ValueError):
    """Provider output failed its internal Pydantic contract."""


class LLMInvariantViolation(ValueError):
    """Valid JSON attempted to change an engine decision or safety invariant."""


_TECHNICAL_ID = re.compile(r"\b(?:EVIDENCE|SKILL|CAREER_GROUP)_[A-Za-z0-9_-]+\b", re.I)
_UNSAFE_PHRASES = (
    "không phù hợp với nghề",
    "em quá kém",
    "em kém",
    "vô dụng",
    "chắc chắn sẽ thành công",
    "chắc chắn trở thành",
    "chắc chắn phù hợp với nghề",
    "nên chọn nghề",
    "phải chọn nghề",
    "chẩn đoán",
    "tự làm hại",
    "mật khẩu",
    "số căn cước",
    "chain of thought",
)
_ENGINE_FIELDS = (
    "confidence",
    "gap priority",
    "outcome status",
    "max_score",
    "điểm số",
    "chấm điểm",
    "điểm tối đa",
)
_SCORE_PROMISE = re.compile(r"\b\d+(?:[.,]\d+)?\s*điểm\b", re.I)
_SPECIALIST_TERMS = ("sql", "python", "portfolio")


def parse_provider_output(raw: str | dict) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str):
        raise LLMOutputParseError("provider output must be a JSON object or string")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMOutputParseError("provider output is malformed JSON") from exc
    if not isinstance(payload, dict):
        raise LLMOutputParseError("provider output JSON must be an object")
    return payload


def _all_text(values: Iterable[object]) -> str:
    return "\n".join(str(item) for item in values if item is not None)


def validate_student_facing_text(values: Iterable[object]) -> None:
    text = _all_text(values)
    lowered = text.casefold()
    if _TECHNICAL_ID.search(text):
        raise LLMInvariantViolation("student-facing text contains a technical identifier")
    for phrase in _UNSAFE_PHRASES:
        if phrase in lowered:
            raise LLMInvariantViolation("student-facing text violates content safety rules")
    for field in _ENGINE_FIELDS:
        if field in lowered:
            raise LLMInvariantViolation("content attempts to discuss an immutable engine field")
    if _SCORE_PROMISE.search(text):
        raise LLMInvariantViolation("content attempts to set or promise a score")


def validate_plan(plan: DetailedLearningPlan, request: PlanExpansionRequest) -> None:
    if plan.source_task_id != request.task.task_id:
        raise LLMInvariantViolation("source_task_id differs from the engine task")
    if plan.skill_id != request.task.skill_id:
        raise LLMInvariantViolation("skill_id differs from the engine task")
    if plan.career_group_id != request.task.career_group_id:
        raise LLMInvariantViolation("career_group_id differs from the engine task")
    if plan.total_minutes != request.task.estimated_minutes:
        raise LLMInvariantViolation("total_minutes differs from the engine task")
    if len(plan.steps) > request.max_steps:
        raise LLMInvariantViolation("plan exceeds max_steps")
    text_values = [
        plan.title,
        plan.objective,
        *plan.completion_criteria,
        plan.reflection_question,
        *(value for step in plan.steps for value in (step.title, step.instruction, step.completion_check)),
    ]
    validate_student_facing_text(text_values)
    lowered = _all_text(text_values).casefold()
    prohibited = [item.casefold() for item in request.prohibited_topics]
    if any(item and item in lowered for item in prohibited):
        raise LLMInvariantViolation("plan contains a prohibited topic")
    engine_text = f"{request.task.title} {request.task.reason}".casefold()
    if not any(term in engine_text for term in _SPECIALIST_TERMS):
        if any(term in lowered for term in _SPECIALIST_TERMS):
            raise LLMInvariantViolation("plan adds specialist work not requested by the engine")


_DIFFICULTY_RANK = {"foundation": 0, "standard": 1, "stretch": 2}


def validate_reassessment(
    package: ReassessmentPackage,
    request: ReassessmentGenerationRequest,
) -> None:
    if package.assessment_id != request.assessment_id:
        raise LLMInvariantViolation("assessment_id differs from the request")
    if package.target_skill_id != request.target_skill_id:
        raise LLMInvariantViolation("target_skill_id differs from the request")
    if len(package.questions) != request.question_count:
        raise LLMInvariantViolation("question count differs from the request")
    if not math.isclose(package.total_score, request.max_score, rel_tol=1e-9, abs_tol=1e-9):
        raise LLMInvariantViolation("total_score differs from the engine specification")
    if (
        request.estimated_minutes is not None
        and package.estimated_minutes != request.estimated_minutes
    ):
        raise LLMInvariantViolation("estimated_minutes differs from the engine specification")
    prior = set(request.prior_question_fingerprints)
    for question in package.questions:
        if question.skill_id != request.target_skill_id:
            raise LLMInvariantViolation("question skill differs from target_skill_id")
        if question.question_type not in request.allowed_question_types:
            raise LLMInvariantViolation("question type is not allowed")
        if _DIFFICULTY_RANK[question.difficulty] > _DIFFICULTY_RANK[request.difficulty]:
            raise LLMInvariantViolation("question difficulty exceeds the request")
        if question.fingerprint in prior:
            raise LLMInvariantViolation("question repeats a prior fingerprint")
        validate_student_facing_text(
            [question.prompt, *question.options, question.correct_answer, question.explanation]
        )


def validate_feedback(
    feedback: PersonalizedFeedback,
    request: FeedbackGenerationRequest,
) -> None:
    if feedback.question_id != request.question_id:
        raise LLMInvariantViolation("question_id differs from the request")
    if feedback.skill_id != request.skill_id:
        raise LLMInvariantViolation("skill_id differs from the request")
    text_values = [
        feedback.summary,
        feedback.hint,
        feedback.error_explanation,
        *feedback.worked_solution_steps,
        feedback.encouragement,
        feedback.followup_question,
    ]
    validate_student_facing_text(text_values)
    lowered = _all_text(text_values).casefold()
    if request.is_correct and any(term in lowered for term in ("em sai", "chưa đúng", "không đúng")):
        raise LLMInvariantViolation("feedback contradicts is_correct")
    if request.feedback_depth == "hint" and feedback.worked_solution_steps:
        raise LLMInvariantViolation("hint feedback must not include a worked solution")
    if request.feedback_depth == "worked_solution" and not feedback.worked_solution_steps:
        raise LLMInvariantViolation("worked_solution feedback requires explicit steps")
    if request.max_followup_questions == 0 and feedback.followup_question is not None:
        raise LLMInvariantViolation("follow-up question is not allowed")


def validate_model(model_type, payload: dict):
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise LLMOutputValidationError("provider output failed content schema validation") from exc
