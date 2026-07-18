from __future__ import annotations

import copy

import pytest

from phase1_demo.student_companion.llm.orchestrator import (
    StudentCompanionContentOrchestrator,
)
from phase1_demo.student_companion.llm.providers import FakeLLMProvider, TemplateProvider
from phase1_demo.tests.content_factory import plan_request, template_raw


def _with_fake(*outputs):
    provider = FakeLLMProvider(outputs)
    return StudentCompanionContentOrchestrator(provider, TemplateProvider()), provider


def test_template_plan_step_minutes_equal_engine_time() -> None:
    request = plan_request()
    result = StudentCompanionContentOrchestrator(TemplateProvider()).expand_plan(request)
    assert result.total_minutes == request.task.estimated_minutes
    assert sum(item.estimated_minutes for item in result.steps) == result.total_minutes


def test_valid_fake_provider_output_is_used() -> None:
    request = plan_request()
    orchestrator, provider = _with_fake(template_raw(request))
    result = orchestrator.expand_plan(request)
    assert result.result_metadata.content_mode == "fake_provider"
    assert result.result_metadata.validation_attempts == 1
    assert provider.call_count == 1


@pytest.mark.parametrize(
    "field,value,expected_warning",
    [
        ("source_task_id", "OTHER_TASK", "provider_output_invariant_violation"),
        ("skill_id", "SKILL_OTHER", "provider_output_invariant_violation"),
        ("total_minutes", 60, "provider_output_schema_error"),
    ],
)
def test_changed_engine_plan_decision_uses_fallback(
    field: str, value, expected_warning: str
) -> None:
    request = plan_request()
    raw = template_raw(request)
    raw[field] = value
    orchestrator, provider = _with_fake(raw)
    result = orchestrator.expand_plan(request)
    assert result.result_metadata.content_mode == "template_fallback"
    assert expected_warning in result.result_metadata.warnings
    assert provider.call_count == 2


def test_output_exceeding_max_steps_uses_fallback() -> None:
    request = plan_request(max_steps=2)
    raw = template_raw(plan_request(max_steps=4))
    orchestrator, _ = _with_fake(raw)
    result = orchestrator.expand_plan(request)
    assert len(result.steps) == 2
    assert result.result_metadata.content_mode == "template_fallback"


def test_zero_step_duration_uses_fallback() -> None:
    request = plan_request()
    raw = copy.deepcopy(template_raw(request))
    raw["steps"][0]["estimated_minutes"] = 0
    orchestrator, _ = _with_fake(raw)
    result = orchestrator.expand_plan(request)
    assert all(item.estimated_minutes > 0 for item in result.steps)
    assert "provider_output_schema_error" in result.result_metadata.warnings


def test_raw_evidence_id_in_content_uses_fallback() -> None:
    request = plan_request()
    raw = template_raw(request)
    raw["objective"] = "Học theo EVIDENCE_PRIVATE_001."
    orchestrator, _ = _with_fake(raw)
    result = orchestrator.expand_plan(request)
    assert "EVIDENCE_" not in result.objective
    assert result.result_metadata.content_mode == "template_fallback"


@pytest.mark.parametrize("term", ["SQL", "Python", "portfolio"])
def test_specialist_work_not_requested_by_engine_uses_fallback(term: str) -> None:
    request = plan_request()
    raw = template_raw(request)
    raw["objective"] = f"Xây dựng {term} nâng cao."
    orchestrator, _ = _with_fake(raw)
    result = orchestrator.expand_plan(request)
    assert term.casefold() not in result.objective.casefold()
    assert result.result_metadata.content_mode == "template_fallback"


def test_malformed_json_retries_then_falls_back() -> None:
    orchestrator, provider = _with_fake("{not-json")
    result = orchestrator.expand_plan(plan_request())
    assert provider.call_count == 2
    assert result.result_metadata.content_mode == "template_fallback"
    assert "provider_output_parse_error" in result.result_metadata.warnings


@pytest.mark.parametrize("error", [TimeoutError("timeout"), RuntimeError("secret-token")])
def test_provider_failure_retries_then_falls_back(error: Exception) -> None:
    orchestrator, provider = _with_fake(error)
    result = orchestrator.expand_plan(plan_request())
    assert provider.call_count == 2
    assert result.result_metadata.content_mode == "template_fallback"
    assert result.result_metadata.warnings == ["provider_error", "provider_fallback_used"]


def test_only_one_provider_retry_is_allowed() -> None:
    orchestrator, provider = _with_fake("bad", "still bad", template_raw(plan_request()))
    result = orchestrator.expand_plan(plan_request())
    assert provider.call_count == 2
    assert result.result_metadata.validation_attempts == 2


def test_template_plan_is_deterministic_and_does_not_mutate_request() -> None:
    request = plan_request()
    before = request.model_dump_json()
    orchestrator = StudentCompanionContentOrchestrator(TemplateProvider())
    first = orchestrator.expand_plan(request).model_dump_json()
    second = orchestrator.expand_plan(request).model_dump_json()
    assert first == second
    assert request.model_dump_json() == before
