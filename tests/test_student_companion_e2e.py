from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend-api"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from modules.candidate.analysis_contracts import to_initial_analysis_request
from modules.companion.service import (
    CompanionError,
    CompanionService,
    map_initial_profile,
    payload_datetime,
)
from modules.companion.store import CompanionStore


INITIAL = ROOT / "tests" / "fixtures" / "student_profile_initial.json"


def _service() -> CompanionService:
    return CompanionService(CompanionStore())


def _analysis(service: CompanionService):
    return service.analyze(student_id="stu_uet_0001", profile_version=1, fixture_selector="initial")


def _plan(service: CompanionService):
    analysis = _analysis(service)
    return analysis, service.generate_plan(analysis["analysis_id"])


def test_profile_mapping_and_full_golden_path_are_deterministic() -> None:
    raw = json.loads(INITIAL.read_text(encoding="utf-8"))
    original = copy.deepcopy(raw)
    wrapped = to_initial_analysis_request(raw, request_id="iar_mapping_test", requested_at=payload_datetime(raw))
    mapped = map_initial_profile(wrapped)

    assert raw == original
    assert mapped.student.student_id == raw["student"]["student_id"]
    assert all(item.student_id == mapped.student.student_id for item in mapped.academic_records)
    assert mapped.metadata.taxonomy_version == "profile-v1"

    first = _service()
    analysis = first.analyze(student_id="stu_uet_0001", profile_version=1, fixture_selector="initial")
    plan = first.generate_plan(analysis["analysis_id"])
    followup = first.followup(baseline_analysis_id=analysis["analysis_id"], student_id="stu_uet_0001", profile_version=2, fixture_selector="week3")

    assert analysis["ability_profile"]
    assert {item["gap_type"] for item in analysis["gaps"]} >= {"academic", "exploration", "decision"}
    assert all("EVIDENCE_" not in json.dumps(item) for item in analysis["gaps"])
    assert plan["estimated_minutes"] <= 45
    assert {item["task_type"] for item in plan["activities"]} == {"academic_practice", "career_micro_experience"}
    assert followup["baseline_analysis_id"] == analysis["analysis_id"]
    assert followup["before_after"]
    comparison = next(item for item in followup["before_after"] if item["subject_id"] == "SKILL_TRIG_TRANSFORMATION")
    assert comparison["after"] > comparison["before"]
    assert followup["next_steps"]

    second = _service()
    assert second.analyze(student_id="stu_uet_0001", profile_version=1, fixture_selector="initial") == analysis
    assert second.generate_plan(analysis["analysis_id"]) == plan


def test_store_state_is_isolated_resettable_and_transitions_are_guarded() -> None:
    first = _service()
    second = _service()
    with pytest.raises(CompanionError, match="Run analysis") as missing_plan:
        first.generate_plan("ANALYSIS_missing")
    assert missing_plan.value.code == "analysis_not_found"
    with pytest.raises(CompanionError) as missing_baseline:
        first.followup(baseline_analysis_id="ANALYSIS_missing", student_id="stu_uet_0001", profile_version=2, fixture_selector="week3")
    assert missing_baseline.value.code == "baseline_not_found"

    analysis = first.analyze(student_id="stu_uet_0001", profile_version=1, fixture_selector="initial")
    assert second.store.get_analysis(analysis["analysis_id"]) is None
    first.store.reset()
    assert first.store.get_analysis(analysis["analysis_id"]) is None


def test_template_content_preserves_engine_decisions_and_grading() -> None:
    service = _service()
    analysis = service.analyze(student_id="stu_uet_0001", profile_version=1, fixture_selector="initial")
    plan = service.generate_plan(analysis["analysis_id"])
    task = plan["activities"][0]
    detail = service.expand_plan(plan["plan_id"], task["activity_id"], 4)
    assert detail["result_metadata"]["content_mode"] == "template_fallback"
    assert detail["source_task_id"] == task["activity_id"]
    assert detail["skill_id"] == task["skill_id"]
    assert detail["total_minutes"] == task["estimated_minutes"]

    reassessment = service.reassessment(plan["plan_id"], task["skill_id"], 3, 10)
    assert len(reassessment["questions"]) == 3
    assert reassessment["total_score"] == 10
    assert reassessment["result_metadata"]["content_mode"] == "template_fallback"

    from modules.companion.schemas import FeedbackRequest
    feedback = service.feedback(FeedbackRequest(question_id="question_1", skill_id=task["skill_id"], question_prompt="Câu hỏi mẫu", student_answer="Sai", expected_answer="Đúng", is_correct=False))
    assert feedback["graded_answer"]["is_correct"] is False
    assert feedback["result_metadata"]["content_mode"] == "template_fallback"


def test_initial_fixture_analyzes_with_all_business_gap_types() -> None:
    result = _analysis(_service())
    assert {item["gap_type"] for item in result["gaps"]} >= {"academic", "exploration", "decision"}


def test_plan_generation_respects_budget_and_happy_path_task_mix() -> None:
    _, result = _plan(_service())
    assert result["estimated_minutes"] == 45
    assert {item["task_type"] for item in result["activities"]} == {"academic_practice", "career_micro_experience"}


def test_followup_preserves_baseline_lineage_and_has_next_step() -> None:
    service = _service()
    analysis = _analysis(service)
    result = service.followup(baseline_analysis_id=analysis["analysis_id"], student_id="stu_uet_0001", profile_version=2, fixture_selector="week3")
    assert result["baseline_analysis_id"] == analysis["analysis_id"]
    assert result["next_steps"]


def test_analyze_ids_and_payload_are_deterministic() -> None:
    first = _analysis(_service())
    second = _analysis(_service())
    assert first == second


def test_presentation_entities_have_display_names() -> None:
    result = _analysis(_service())
    assert result["display_name"]
    assert all(item["display_name"] for item in result["ability_profile"])
    assert all(item["display_name"] for item in result["gaps"])


def test_presentation_omits_raw_evidence_identifiers() -> None:
    analysis, plan = _plan(_service())
    serialized = json.dumps([analysis, plan])
    assert "EVIDENCE_" not in serialized
    assert "source_reference" not in serialized


def test_warning_shape_is_safe_and_deduplicated() -> None:
    warnings = _analysis(_service())["warnings"]
    assert len({item["code"] for item in warnings}) == len(warnings)
    assert all({"code", "severity", "title", "message", "suggested_action"} == set(item) for item in warnings)


def test_before_after_items_share_one_scale() -> None:
    service = _service()
    analysis = _analysis(service)
    result = service.followup(baseline_analysis_id=analysis["analysis_id"], student_id="stu_uet_0001", profile_version=2, fixture_selector="week3")
    assert all(item["max_value"] == 100 for item in result["before_after"])
    assert all(item["delta"] == pytest.approx(item["after"] - item["before"], abs=0.01) for item in result["before_after"])


def test_expand_plan_uses_template_fallback() -> None:
    service = _service()
    _, plan = _plan(service)
    task = plan["activities"][0]
    result = service.expand_plan(plan["plan_id"], task["activity_id"], 4)
    assert result["result_metadata"]["content_mode"] == "template_fallback"


def test_reassessment_preserves_requested_count_and_score() -> None:
    service = _service()
    _, plan = _plan(service)
    skill = next(item["skill_id"] for item in plan["activities"] if item["skill_id"])
    result = service.reassessment(plan["plan_id"], skill, 3, 10)
    assert (len(result["questions"]), result["total_score"]) == (3, 10)


def test_feedback_preserves_caller_owned_is_correct() -> None:
    from modules.companion.schemas import FeedbackRequest
    result = _service().feedback(FeedbackRequest(question_id="question_wrong", skill_id="SKILL_TRIG_TRANSFORMATION", question_prompt="Câu hỏi", student_answer="Sai", expected_answer="Đúng", is_correct=False))
    assert result["graded_answer"] == {"is_correct": False}


def test_reset_removes_analysis_and_plan_state() -> None:
    service = _service()
    analysis, plan = _plan(service)
    assert service.store.get_analysis(analysis["analysis_id"])
    assert service.store.get_plan(plan["plan_id"])
    service.store.reset()
    assert service.store.get_analysis(analysis["analysis_id"]) is None
    assert service.store.get_plan(plan["plan_id"]) is None
