from __future__ import annotations

import copy
import math

from phase1_demo.student_companion.llm.orchestrator import (
    StudentCompanionContentOrchestrator,
)
from phase1_demo.student_companion.llm.providers import FakeLLMProvider, TemplateProvider
from phase1_demo.tests.content_factory import reassessment_request, template_raw


def _run_fake(request, raw):
    provider = FakeLLMProvider([raw])
    result = StudentCompanionContentOrchestrator(provider, TemplateProvider()).generate_reassessment(request)
    return result, provider


def test_template_reassessment_has_exact_question_count() -> None:
    request = reassessment_request(question_count=5)
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_reassessment(request)
    assert len(result.questions) == 5


def test_template_reassessment_preserves_target_skill() -> None:
    request = reassessment_request()
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_reassessment(request)
    assert result.target_skill_id == request.target_skill_id
    assert all(item.skill_id == request.target_skill_id for item in result.questions)


def test_template_reassessment_score_sum_matches_engine_specification() -> None:
    request = reassessment_request(max_score=7.0)
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_reassessment(request)
    assert math.isclose(sum(item.score for item in result.questions), 7.0)
    assert result.total_score == 7.0


def test_duplicate_generated_fingerprint_uses_fallback() -> None:
    request = reassessment_request()
    raw = copy.deepcopy(template_raw(request))
    raw["questions"][1]["fingerprint"] = raw["questions"][0]["fingerprint"]
    result, _ = _run_fake(request, raw)
    assert len({item.fingerprint for item in result.questions}) == len(result.questions)
    assert result.result_metadata.content_mode == "template_fallback"


def test_prior_question_fingerprint_is_not_reused() -> None:
    base_request = reassessment_request()
    raw = template_raw(base_request)
    previous = raw["questions"][0]["fingerprint"]
    request = reassessment_request(prior_question_fingerprints=[previous])
    result, _ = _run_fake(request, raw)
    assert previous not in {item.fingerprint for item in result.questions}
    assert "provider_output_invariant_violation" in result.result_metadata.warnings


def test_multiple_choice_with_too_few_options_uses_fallback() -> None:
    request = reassessment_request()
    raw = copy.deepcopy(template_raw(request))
    raw["questions"][0]["options"] = ["A", "B"]
    raw["questions"][0]["correct_answer"] = "A"
    result, _ = _run_fake(request, raw)
    assert len(result.questions[0].options) >= 3
    assert "provider_output_schema_error" in result.result_metadata.warnings


def test_missing_correct_answer_uses_fallback() -> None:
    request = reassessment_request()
    raw = copy.deepcopy(template_raw(request))
    raw["questions"][0].pop("correct_answer")
    result, _ = _run_fake(request, raw)
    assert result.questions[0].correct_answer
    assert result.result_metadata.content_mode == "template_fallback"


def test_difficulty_above_request_uses_fallback() -> None:
    request = reassessment_request(difficulty="foundation")
    raw = copy.deepcopy(template_raw(request))
    raw["questions"][0]["difficulty"] = "stretch"
    result, _ = _run_fake(request, raw)
    assert all(item.difficulty == "foundation" for item in result.questions)
    assert "provider_output_invariant_violation" in result.result_metadata.warnings


def test_malformed_reassessment_output_uses_fallback() -> None:
    result, provider = _run_fake(reassessment_request(), "[not-an-object]")
    assert provider.call_count == 2
    assert result.result_metadata.content_mode == "template_fallback"


def test_reassessment_template_is_deterministic() -> None:
    request = reassessment_request()
    orchestrator = StudentCompanionContentOrchestrator(TemplateProvider())
    assert (
        orchestrator.generate_reassessment(request).model_dump_json()
        == orchestrator.generate_reassessment(request).model_dump_json()
    )


def test_provider_cannot_add_engine_outcome() -> None:
    request = reassessment_request()
    raw = template_raw(request)
    raw["outcome"] = "meaningful_improvement"
    result, _ = _run_fake(request, raw)
    assert not hasattr(result, "outcome")
    assert "provider_output_schema_error" in result.result_metadata.warnings


def test_provider_cannot_change_reassessment_time() -> None:
    request = reassessment_request(estimated_minutes=10)
    raw = template_raw(request)
    raw["estimated_minutes"] = 30
    result, _ = _run_fake(request, raw)
    assert result.estimated_minutes == 10
    assert "provider_output_invariant_violation" in result.result_metadata.warnings


def test_short_answer_has_no_options() -> None:
    request = reassessment_request(allowed_question_types=["short_answer"])
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_reassessment(request)
    assert all(item.question_type == "short_answer" and not item.options for item in result.questions)


def test_generic_skill_has_explicit_expert_review_warning() -> None:
    request = reassessment_request(target_skill_id="SKILL_COMMUNICATION")
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_reassessment(request)
    assert "generic_question_template_requires_expert_review" in result.result_metadata.warnings


def test_question_fingerprints_are_unique_and_stable() -> None:
    request = reassessment_request(question_count=10)
    result = StudentCompanionContentOrchestrator(TemplateProvider()).generate_reassessment(request)
    fingerprints = [item.fingerprint for item in result.questions]
    assert len(fingerprints) == len(set(fingerprints))
