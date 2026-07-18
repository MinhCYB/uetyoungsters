from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from phase1_demo.student_companion.application import DemoService
from phase1_demo.student_companion.domain import (
    AbilityEstimate,
    ActivityResult,
    AssessmentAttempt,
    Evidence,
    GapType,
    StudentProfile,
    build_ability_profile,
    build_gaps,
    evaluate_assessment_outcomes,
    generate_weekly_plan,
    merge_evidence,
    normalize_academic_records,
    normalize_assessment,
)
from phase1_demo.student_companion.infrastructure import (
    build_market_snapshot,
    load_followup_fixtures,
    load_initial_fixtures,
)


FIXTURE_ROOT = Path("phase1_demo/fixtures")


def _analyzed_service() -> DemoService:
    service = DemoService()
    service.analyze_initial_state()
    return service


def _planned_service() -> DemoService:
    service = _analyzed_service()
    service.generate_weekly_plan()
    return service


def test_fixtures_parse_with_domain_models() -> None:
    initial = load_initial_fixtures()
    followup = load_followup_fixtures()
    assert isinstance(initial.student, StudentProfile)
    assert isinstance(initial.pretest_attempt, AssessmentAttempt)
    assert isinstance(followup.activity_result, ActivityResult)
    assert initial.student.student_id == followup.posttest_attempt.student_id


def test_student_fixtures_contain_input_only() -> None:
    forbidden = {
        "ability_profile",
        "gaps",
        "weekly_plan",
        "outcomes",
        "recommendation",
        "snapshot",
    }
    for path in sorted((FIXTURE_ROOT / "student_t0").glob("*.json")) + sorted(
        (FIXTURE_ROOT / "student_t1").glob("*.json")
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        serialized = json.dumps(payload)
        assert all(key not in serialized for key in forbidden)


def test_academic_record_45_over_10_normalizes_to_045() -> None:
    initial = load_initial_fixtures()
    evidence = normalize_academic_records(initial.academic_records)
    trig = next(item for item in evidence if item.skill_id == "SKILL_TRIG_TRANSFORMATION")
    assert trig.normalized_value == pytest.approx(0.45)


def test_pretest_4_over_10_normalizes_to_04() -> None:
    initial = load_initial_fixtures()
    evidence = normalize_assessment(initial.pretest_attempt)
    trig = next(item for item in evidence if item.skill_id == "SKILL_TRIG_TRANSFORMATION")
    assert trig.normalized_value == pytest.approx(0.4)


def test_evidence_ids_and_order_are_deterministic() -> None:
    initial = load_initial_fixtures()
    first = normalize_assessment(initial.pretest_attempt)
    second = normalize_assessment(initial.pretest_attempt)
    assert [item.model_dump_json() for item in first] == [item.model_dump_json() for item in second]


def test_merge_evidence_deduplicates_identical_items() -> None:
    initial = load_initial_fixtures()
    evidence = normalize_assessment(initial.pretest_attempt)
    merged = merge_evidence(evidence, evidence)
    assert len(merged) == len(evidence)
    assert len({item.evidence_id for item in merged}) == len(merged)


def test_ability_uses_weighted_score_formula() -> None:
    common = {
        "student_id": "student-1",
        "skill_id": "skill-1",
        "confidence": 1.0,
        "observed_at": "2026-07-01T00:00:00+00:00",
        "evidence_version": "test",
    }
    evidence = [
        Evidence(
            **common,
            evidence_id="e-1",
            source_type="assessment",
            raw_value=4,
            normalized_value=0.4,
            source_reference="a-1",
        ),
        Evidence(
            **common,
            evidence_id="e-2",
            source_type="academic_record",
            raw_value=6,
            normalized_value=0.6,
            source_reference="r-1",
        ),
    ]
    estimate = build_ability_profile(evidence)[0]
    assert estimate.estimated_level == pytest.approx((0.4 + 0.6 * 0.9) / 1.9, abs=1e-6)
    assert estimate.confidence == pytest.approx(0.95)


def test_low_trigonometry_creates_academic_gap() -> None:
    service = _analyzed_service()
    assert any(
        gap.gap_type is GapType.ACADEMIC
        and gap.skill_id == "SKILL_TRIG_TRANSFORMATION"
        for gap in service.gaps_t0
    )


def test_trigonometry_85_over_10_removes_academic_gap() -> None:
    initial = load_initial_fixtures()
    data = initial.pretest_attempt.model_dump()
    data["skill_scores"] = [
        {"skill_id": "SKILL_TRIG_TRANSFORMATION", "score": 8.5, "max_score": 10.0}
    ]
    attempt = AssessmentAttempt.model_validate(data)
    evidence = normalize_assessment(attempt)
    ability = build_ability_profile(evidence)
    gaps = build_gaps(initial.student, ability, evidence)
    assert not any(gap.skill_id == "SKILL_TRIG_TRANSFORMATION" for gap in gaps)


def test_missing_activity_creates_exploration_gaps() -> None:
    service = _analyzed_service()
    groups = {
        gap.career_group_ids[0]
        for gap in service.gaps_t0
        if gap.gap_type is GapType.EXPLORATION
    }
    assert groups == {"CAREER_GROUP_DATA_AI", "CAREER_GROUP_ECONOMICS"}


def test_completed_data_activity_closes_data_exploration_gap() -> None:
    service = _planned_service()
    service.advance_two_weeks()
    groups = {
        gap.career_group_ids[0]
        for gap in service.gaps_t1
        if gap.gap_type is GapType.EXPLORATION
    }
    assert "CAREER_GROUP_DATA_AI" not in groups
    assert "CAREER_GROUP_ECONOMICS" in groups


def test_two_career_interests_create_decision_gap() -> None:
    service = _analyzed_service()
    decision = next(gap for gap in service.gaps_t0 if gap.gap_type is GapType.DECISION)
    assert decision.career_group_ids == [
        "CAREER_GROUP_DATA_AI",
        "CAREER_GROUP_ECONOMICS",
    ]


def test_t0_plan_uses_exactly_45_minutes() -> None:
    service = _planned_service()
    assert service.plan_t0.total_planned_minutes == 45
    assert [task.estimated_minutes for task in service.plan_t0.tasks] == [20, 25]


def test_budget_30_is_not_exceeded() -> None:
    service = _analyzed_service()
    student = service.initial.student.model_copy(update={"weekly_available_minutes": 30})
    plan = generate_weekly_plan(
        student,
        service.gaps_t0,
        service.initial.pretest_attempt.completed_at,
        "PLAN_30",
    )
    assert plan.total_planned_minutes <= 30


def test_exam_week_has_no_career_activity() -> None:
    service = _analyzed_service()
    student = service.initial.student.model_copy(update={"exam_week": True})
    plan = generate_weekly_plan(
        student,
        service.gaps_t0,
        service.initial.pretest_attempt.completed_at,
        "PLAN_EXAM",
    )
    assert all(task.task_type.value != "career_micro_experience" for task in plan.tasks)


def test_good_trigonometry_does_not_assign_trigonometry_practice() -> None:
    service = _analyzed_service()
    gaps = [gap for gap in service.gaps_t0 if gap.skill_id != "SKILL_TRIG_TRANSFORMATION"]
    plan = generate_weekly_plan(
        service.initial.student,
        gaps,
        service.initial.pretest_attempt.completed_at,
        "PLAN_NO_TRIG",
    )
    assert all(task.skill_id != "SKILL_TRIG_TRANSFORMATION" for task in plan.tasks)


def test_completed_activity_is_not_repeated() -> None:
    service = _analyzed_service()
    plan = generate_weekly_plan(
        service.initial.student,
        service.gaps_t0,
        service.initial.pretest_attempt.completed_at,
        "PLAN_AFTER_DATA",
        completed_activity_ids=["ACTIVITY_DATA_INSIGHTS"],
    )
    assert all(task.career_group_id != "CAREER_GROUP_DATA_AI" for task in plan.tasks)


def test_improved_posttest_is_meaningful_improvement() -> None:
    service = _planned_service()
    service.advance_two_weeks()
    trig = next(
        item for item in service.outcomes_t1 if item.metric_type == "SKILL_TRIG_TRANSFORMATION"
    )
    assert trig.delta == pytest.approx(0.3)
    assert trig.status.value == "meaningful_improvement"


def test_no_posttest_improvement_is_not_meaningful() -> None:
    initial = load_initial_fixtures()
    post_data = initial.pretest_attempt.model_dump()
    post_data.update(attempt_id="POST_NO_CHANGE", assessment_type="posttest")
    after = AssessmentAttempt.model_validate(post_data)
    outcomes = evaluate_assessment_outcomes(
        initial.pretest_attempt,
        after,
        normalize_assessment(initial.pretest_attempt),
        normalize_assessment(after),
    )
    assert all(item.status.value != "meaningful_improvement" for item in outcomes)


def test_t1_does_not_mutate_t0_snapshot() -> None:
    service = _planned_service()
    before = service.snapshot_t0.model_dump_json()
    service.advance_two_weeks()
    assert service.snapshot_t0.model_dump_json() == before


def test_snapshot_lineage_points_to_t0() -> None:
    service = _planned_service()
    service.advance_two_weeks()
    assert service.snapshot_t1.previous_snapshot_id == service.snapshot_t0.snapshot_id
    assert service.snapshot_t1.market_snapshot_version == service.snapshot_t0.market_snapshot_version


def test_market_fallback_is_marked() -> None:
    market = build_market_snapshot(processed_root=FIXTURE_ROOT / "missing_processed")
    assert market
    assert {item.data_mode for item in market} == {"fallback_demo"}


def test_same_inputs_create_identical_derived_output() -> None:
    first = _planned_service()
    first.advance_two_weeks()
    second = _planned_service()
    second.advance_two_weeks()
    assert first.get_comparison() == second.get_comparison()


def test_input_change_changes_derived_output() -> None:
    service = _analyzed_service()
    original = next(
        item for item in service.ability_t0 if item.skill_id == "SKILL_TRIG_TRANSFORMATION"
    )
    evidence = deepcopy(service.evidence_t0)
    changed = [
        item.model_copy(update={"normalized_value": 0.9})
        if item.skill_id == "SKILL_TRIG_TRANSFORMATION" and item.source_type.value == "assessment"
        else item
        for item in evidence
    ]
    updated = next(
        item for item in build_ability_profile(changed) if item.skill_id == original.skill_id
    )
    assert updated.estimated_level != original.estimated_level


def test_t1_next_step_is_economics_without_final_career_decision() -> None:
    service = _planned_service()
    service.advance_two_weeks()
    assert service.next_step.career_group_id == "CAREER_GROUP_ECONOMICS"
    assert any(gap.gap_type is GapType.DECISION for gap in service.gaps_t1)
