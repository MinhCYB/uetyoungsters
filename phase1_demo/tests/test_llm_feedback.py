from __future__ import annotations

import copy

import pytest

from phase1_demo.student_companion.llm.orchestrator import (
    StudentCompanionContentOrchestrator,
)
from phase1_demo.student_companion.llm.providers import FakeLLMProvider, TemplateProvider
from phase1_demo.tests.content_factory import feedback_request, template_raw


def _run_fake(request, raw):
    provider = FakeLLMProvider([raw])
    result = StudentCompanionContentOrchestrator(provider, TemplateProvider()).generate_feedback(request)
    return result, provider


def test_provider_cannot_change_is_correct() -> None:
    request = feedback_request(is_correct=True)
    raw = template_raw(request)
    raw["is_correct"] = False
    result, _ = _run_fake(request, raw)
    assert "provider_output_schema_error" in result.result_metadata.warnings
    assert "trả lời đúng" in result.summary


def test_hint_depth_has_no_full_worked_solution() -> None:
    request = feedback_request(feedback_depth="hint")
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_feedback(request)
    assert result.hint
    assert result.worked_solution_steps == []


def test_worked_solution_depth_has_explicit_steps() -> None:
    request = feedback_request(feedback_depth="worked_solution")
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_feedback(request)
    assert len(result.worked_solution_steps) >= 2


def test_provider_cannot_add_score_change() -> None:
    request = feedback_request()
    raw = template_raw(request)
    raw["score"] = 10
    result, _ = _run_fake(request, raw)
    assert not hasattr(result, "score")
    assert result.result_metadata.content_mode == "template_fallback"


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "Em quá kém.",
        "Em không phù hợp với nghề Data.",
        "Em chắc chắn sẽ thành công.",
        "Hãy cung cấp mật khẩu.",
        "Em sẽ đạt 10 điểm.",
    ],
)
def test_unsafe_or_judgmental_feedback_uses_fallback(unsafe_text: str) -> None:
    request = feedback_request()
    raw = template_raw(request)
    raw["summary"] = unsafe_text
    result, _ = _run_fake(request, raw)
    assert result.summary != unsafe_text
    assert "provider_output_invariant_violation" in result.result_metadata.warnings


@pytest.mark.parametrize(
    "field,value",
    [("question_id", "OTHER_QUESTION"), ("skill_id", "SKILL_OTHER")],
)
def test_feedback_reference_change_uses_fallback(field: str, value: str) -> None:
    request = feedback_request()
    raw = template_raw(request)
    raw[field] = value
    result, _ = _run_fake(request, raw)
    assert getattr(result, field) == getattr(request, field)
    assert result.result_metadata.content_mode == "template_fallback"


def test_provider_failure_uses_feedback_fallback() -> None:
    request = feedback_request()
    result, provider = _run_fake(request, TimeoutError("timeout"))
    assert provider.call_count == 2
    assert result.hint
    assert result.result_metadata.content_mode == "template_fallback"


def test_correct_answer_generates_reinforcement_feedback() -> None:
    request = feedback_request(is_correct=True, student_answer="-sin(x)")
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_feedback(request)
    assert "trả lời đúng" in result.summary
    assert result.error_explanation is None


def test_incorrect_answer_generates_hint_and_explanation() -> None:
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_feedback(
        feedback_request(is_correct=False)
    )
    assert result.hint
    assert result.error_explanation


def test_zero_followup_limit_produces_no_followup_question() -> None:
    request = feedback_request(max_followup_questions=0)
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_feedback(request)
    assert result.followup_question is None


def test_feedback_with_raw_evidence_id_uses_fallback() -> None:
    request = feedback_request()
    raw = copy.deepcopy(template_raw(request))
    raw["encouragement"] = "Dựa trên EVIDENCE_PRIVATE_001."
    result, _ = _run_fake(request, raw)
    assert "EVIDENCE_" not in result.encouragement
