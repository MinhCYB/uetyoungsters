"""Versioned minimal prompts for controlled structured generation."""

from __future__ import annotations

import json
import re

from .contracts import (
    FeedbackGenerationRequest,
    PlanExpansionRequest,
    ReassessmentGenerationRequest,
)


PLAN_EXPANSION_PROMPT_VERSION = "plan-expansion-1.0.0"
REASSESSMENT_PROMPT_VERSION = "reassessment-1.0.0"
FEEDBACK_PROMPT_VERSION = "feedback-1.0.0"

_RAW_ID_PATTERN = re.compile(r"\b(?:EVIDENCE|TEACHER|TENANT)_[A-Za-z0-9_-]+\b", re.I)


def _redact(value: str) -> str:
    return _RAW_ID_PATTERN.sub("[redacted]", value)


def _system_prompt(use_case: str, language: str, grade_level: int) -> str:
    return (
        f"Controlled Student Companion content generation for {use_case}. "
        "Engine decisions are immutable: do not change skill, career group, difficulty "
        "constraint, time, score, confidence, gap, priority, outcome, or career decision. "
        "Return only one JSON object matching the requested schema, without markdown fences. "
        "Do not provide chain of thought. Do not infer a career conclusion. "
        "Do not request personal information or expose technical identifiers. "
        f"Content must suit grade {grade_level}. Language: {language}. "
        "Use Vietnamese when language is vi."
    )


def _json_prompt(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_plan_prompts(request: PlanExpansionRequest) -> tuple[str, str]:
    payload = {
        "use_case": "plan_expansion",
        "prompt_version": PLAN_EXPANSION_PROMPT_VERSION,
        "request_id": request.metadata.request_id,
        "language": request.metadata.language,
        "grade_level": request.metadata.grade_level,
        "task": {
            "task_id": request.task.task_id,
            "task_type": request.task.task_type.value,
            "title": _redact(request.task.title),
            "skill_id": request.task.skill_id,
            "career_group_id": request.task.career_group_id,
            "estimated_minutes": request.task.estimated_minutes,
        },
        "difficulty": request.difficulty,
        "max_steps": request.max_steps,
        "student_preferences": [_redact(item) for item in request.student_preferences],
        "prohibited_topics": [_redact(item) for item in request.prohibited_topics],
    }
    return (
        _system_prompt("plan expansion", request.metadata.language, request.metadata.grade_level),
        _json_prompt(payload),
    )


def build_reassessment_prompts(
    request: ReassessmentGenerationRequest,
) -> tuple[str, str]:
    payload = {
        "use_case": "reassessment",
        "prompt_version": REASSESSMENT_PROMPT_VERSION,
        "request_id": request.metadata.request_id,
        "language": request.metadata.language,
        "grade_level": request.metadata.grade_level,
        "assessment_id": request.assessment_id,
        "target_skill_id": request.target_skill_id,
        "question_count": request.question_count,
        "difficulty": request.difficulty,
        "max_score": request.max_score,
        "estimated_minutes": request.estimated_minutes,
        "allowed_question_types": request.allowed_question_types,
        "prior_question_fingerprints": request.prior_question_fingerprints,
        "learning_objective": _redact(request.learning_objective),
    }
    return (
        _system_prompt("reassessment", request.metadata.language, request.metadata.grade_level),
        _json_prompt(payload),
    )


def build_feedback_prompts(request: FeedbackGenerationRequest) -> tuple[str, str]:
    payload = {
        "use_case": "feedback",
        "prompt_version": FEEDBACK_PROMPT_VERSION,
        "request_id": request.metadata.request_id,
        "language": request.metadata.language,
        "grade_level": request.metadata.grade_level,
        "question_id": request.question_id,
        "skill_id": request.skill_id,
        "question_prompt": _redact(request.question_prompt),
        "student_answer": _redact(request.student_answer),
        "expected_answer": _redact(request.expected_answer),
        "is_correct": request.is_correct,
        "detected_error_type": _redact(request.detected_error_type or "") or None,
        "feedback_depth": request.feedback_depth,
        "max_followup_questions": request.max_followup_questions,
    }
    return (
        _system_prompt("personalized feedback", request.metadata.language, request.metadata.grade_level),
        _json_prompt(payload),
    )
