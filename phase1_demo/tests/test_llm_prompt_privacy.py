from __future__ import annotations

from phase1_demo.student_companion.llm.prompts import (
    FEEDBACK_PROMPT_VERSION,
    PLAN_EXPANSION_PROMPT_VERSION,
    REASSESSMENT_PROMPT_VERSION,
    build_feedback_prompts,
    build_plan_prompts,
    build_reassessment_prompts,
)
from phase1_demo.tests.content_factory import (
    feedback_request,
    plan_request,
    reassessment_request,
)


def test_plan_prompt_does_not_contain_teacher_id() -> None:
    request = plan_request(student_preferences=["TEACHER_PRIVATE_123 prefers examples"])
    _, user = build_plan_prompts(request)
    assert "TEACHER_PRIVATE_123" not in user


def test_plan_prompt_does_not_contain_tenant_id() -> None:
    request = plan_request(student_preferences=["TENANT_PRIVATE_123"])
    _, user = build_plan_prompts(request)
    assert "TENANT_PRIVATE_123" not in user


def test_plan_prompt_does_not_contain_raw_evidence_ids() -> None:
    system, user = build_plan_prompts(plan_request())
    assert "EVIDENCE_PRIVATE_001" not in system + user


def test_prompt_does_not_contain_full_profile_fields() -> None:
    _, user = build_plan_prompts(plan_request())
    assert "display_name" not in user
    assert "career_interest_ids" not in user
    assert "weekly_available_minutes" not in user


def test_prompt_does_not_contain_market_or_database_metadata() -> None:
    prompts = [
        *build_plan_prompts(plan_request()),
        *build_reassessment_prompts(reassessment_request()),
        *build_feedback_prompts(feedback_request()),
    ]
    combined = "\n".join(prompts).casefold()
    assert "market_signal" not in combined
    assert "database" not in combined
    assert "taxonomy_version" not in combined


def test_prompt_versions_are_stable() -> None:
    assert PLAN_EXPANSION_PROMPT_VERSION == "plan-expansion-1.0.0"
    assert REASSESSMENT_PROMPT_VERSION == "reassessment-1.0.0"
    assert FEEDBACK_PROMPT_VERSION == "feedback-1.0.0"


def test_prompt_is_deterministic() -> None:
    assert build_plan_prompts(plan_request()) == build_plan_prompts(plan_request())


def test_system_prompt_requires_json_and_forbids_chain_of_thought() -> None:
    system, _ = build_feedback_prompts(feedback_request())
    lowered = system.casefold()
    assert "json" in lowered
    assert "do not provide chain of thought" in lowered
