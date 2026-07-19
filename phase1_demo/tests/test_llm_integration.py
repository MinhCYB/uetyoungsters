from __future__ import annotations

import inspect

from phase1_demo.scripts.run_llm_content_demo import run_demo
from phase1_demo.student_companion.application.content_service import (
    ReassessmentSpecification,
    StudentCompanionContentService,
)
from phase1_demo.student_companion.llm.contracts import ContentGenerationMetadata
from phase1_demo.student_companion.llm.orchestrator import (
    StudentCompanionContentOrchestrator,
)
from phase1_demo.student_companion.llm.ports import LLMProvider
from phase1_demo.student_companion.llm.prompts import PLAN_EXPANSION_PROMPT_VERSION
from phase1_demo.student_companion.llm.providers import (
    ExistingProviderAdapter,
    FakeLLMProvider,
    TemplateProvider,
)
from phase1_demo.tests.content_factory import metadata, weekly_plan


def _metadata_by_task(plan):
    return {
        task.task_id: ContentGenerationMetadata(
            **metadata(
                PLAN_EXPANSION_PROMPT_VERSION,
                f"EXPAND_{index}",
            ).model_dump()
        )
        for index, task in enumerate(plan.tasks)
    }


def test_content_service_expands_entire_weekly_plan_without_changing_time() -> None:
    plan = weekly_plan()
    service = StudentCompanionContentService(
        StudentCompanionContentOrchestrator(TemplateProvider())
    )
    results = service.expand_weekly_plan(
        plan,
        metadata_by_task=_metadata_by_task(plan),
        difficulty_by_task={
            plan.tasks[0].task_id: "foundation",
            plan.tasks[1].task_id: "standard",
        },
    )
    assert len(results) == len(plan.tasks)
    assert sum(item.total_minutes for item in results) == 45
    assert plan.total_planned_minutes == 45


def test_content_service_requires_caller_owned_difficulty() -> None:
    plan = weekly_plan()
    service = StudentCompanionContentService(
        StudentCompanionContentOrchestrator(TemplateProvider())
    )
    try:
        service.expand_weekly_plan(
            plan,
            metadata_by_task=_metadata_by_task(plan),
            difficulty_by_task={},
        )
    except ValueError as exc:
        assert "caller-owned" in str(exc)
    else:
        raise AssertionError("missing engine difficulty must not be inferred")


def test_reassessment_specification_is_internal_and_strict() -> None:
    specification = ReassessmentSpecification(
        target_skill_id="SKILL_TRIG_TRANSFORMATION",
        question_count=5,
        difficulty="foundation",
        max_score=10,
        estimated_minutes=10,
        reassessment_after_days=14,
    )
    assert specification.reassessment_after_days == 14


def test_providers_satisfy_protocol() -> None:
    assert isinstance(TemplateProvider(), LLMProvider)
    assert isinstance(FakeLLMProvider(delegate=TemplateProvider()), LLMProvider)
    assert isinstance(ExistingProviderAdapter(), LLMProvider)


def test_existing_provider_unavailable_falls_back_without_crash() -> None:
    plan = weekly_plan()
    service = StudentCompanionContentService(
        StudentCompanionContentOrchestrator(
            ExistingProviderAdapter(), TemplateProvider()
        )
    )
    result = service.expand_weekly_plan(
        plan,
        metadata_by_task=_metadata_by_task(plan),
        difficulty_by_task={task.task_id: "foundation" for task in plan.tasks},
    )
    assert all(item.result_metadata.content_mode == "template_fallback" for item in result)
    assert all("provider_fallback_used" in item.result_metadata.warnings for item in result)


def test_llm_orchestrator_has_no_demo_or_market_dependency() -> None:
    source = inspect.getsource(
        __import__(
            "phase1_demo.student_companion.llm.orchestrator",
            fromlist=["StudentCompanionContentOrchestrator"],
        )
    ).casefold()
    assert "fixture" not in source
    assert "run_demo" not in source
    assert "parquet" not in source
    assert "market" not in source


def test_cli_demo_template_mode_runs_without_prompt_or_secret_output() -> None:
    output: list[str] = []
    run_demo("template", output.append)
    combined = "\n".join(output)
    assert "Provider mode: template_fallback" in combined
    assert "Reassessment: 5 câu" in combined
    assert "system_prompt" not in combined
    assert "secret" not in combined.casefold()
