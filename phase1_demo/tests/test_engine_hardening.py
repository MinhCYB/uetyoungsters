from __future__ import annotations

from datetime import datetime, timezone

import pytest

from phase1_demo.scenario_factory import ScenarioFactory, ScenarioMarketProvider
from phase1_demo.student_companion.application.facade import StudentCompanionFacade
from phase1_demo.student_companion.config import (
    ACTIVITY_CATALOG,
    CAREER_ACTIVITY_BY_GROUP,
    CONFIDENCE_CONFIG_VERSION,
    CONFIDENCE_POLICY,
    GAP_PRIORITY_CONFIG_VERSION,
)
from phase1_demo.student_companion.contracts import ContractWarning
from phase1_demo.student_companion.domain import (
    AbilityEstimate,
    AbilityTrend,
    Evidence,
    GapPriority,
)
from phase1_demo.student_companion.domain.rules import (
    academic_priority_score,
    build_ability_profile,
    build_gaps,
)
from phase1_demo.student_companion.domain.warnings import (
    normalize_warnings,
    scales_are_comparable,
    stale_profile_version_warning,
)


def _evidence(
    evidence_id: str,
    value: float,
    source: str,
    *,
    skill: str = "SKILL_TEST",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        student_id="STUDENT_TEST",
        skill_id=skill,
        source_type=source,
        raw_value=value,
        normalized_value=value,
        confidence=1.0,
        observed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        source_reference=f"SOURCE_{evidence_id}",
        evidence_version="test",
    )


def test_confidence_config_is_versioned() -> None:
    assert CONFIDENCE_CONFIG_VERSION == "confidence-1.0.0"
    assert GAP_PRIORITY_CONFIG_VERSION == "gap-priority-1.0.0"


def test_single_self_report_has_low_confidence() -> None:
    estimate = build_ability_profile([_evidence("E1", 0.9, "self_report")])[0]
    assert estimate.confidence < CONFIDENCE_POLICY["low_confidence_threshold"]


def test_agreeing_assessment_and_record_raise_confidence() -> None:
    single = build_ability_profile([_evidence("E1", 0.7, "assessment")])[0]
    agreeing = build_ability_profile(
        [
            _evidence("E1", 0.7, "assessment"),
            _evidence("E2", 0.72, "academic_record"),
        ]
    )[0]
    assert agreeing.confidence > single.confidence


def test_strong_conflict_reduces_confidence() -> None:
    agreeing = build_ability_profile(
        [_evidence("E1", 0.8, "assessment"), _evidence("E2", 0.8, "academic_record")]
    )[0]
    conflicting = build_ability_profile(
        [_evidence("E1", 0.9, "assessment"), _evidence("E2", 0.1, "academic_record")]
    )[0]
    assert conflicting.confidence < agreeing.confidence


def test_source_diversity_beats_repeated_single_source() -> None:
    repeated = build_ability_profile(
        [_evidence(f"E{i}", 0.6, "assessment") for i in range(3)]
    )[0]
    diverse = build_ability_profile(
        [
            _evidence("E1", 0.6, "assessment"),
            _evidence("E2", 0.6, "academic_record"),
            _evidence("E3", 0.6, "teacher_observation"),
        ]
    )[0]
    assert diverse.confidence > repeated.confidence


@pytest.mark.parametrize("values", [[0.0], [1.0], [0.0, 1.0], [0.49, 0.51], [0.2, 0.2, 0.2]])
def test_confidence_is_bounded(values: list[float]) -> None:
    evidence = [_evidence(f"E{i}", value, "assessment") for i, value in enumerate(values)]
    confidence = build_ability_profile(evidence)[0].confidence
    assert 0.0 <= confidence <= 1.0


def test_confidence_is_deterministic() -> None:
    evidence = [_evidence("E1", 0.4, "assessment"), _evidence("E2", 0.6, "academic_record")]
    assert build_ability_profile(evidence) == build_ability_profile(reversed(evidence))


def test_demo_ability_remains_reasonable() -> None:
    factory = ScenarioFactory()
    response = StudentCompanionFacade(ScenarioMarketProvider()).analyze(
        factory.initial_request()
    )
    trig = next(item for item in response.ability_profile if "TRIG" in item.skill_id)
    data = next(item for item in response.ability_profile if "DATA" in item.skill_id)
    assert trig.estimated_level < 0.5
    assert data.estimated_level > trig.estimated_level


def test_warning_deduplication_uses_code_and_field() -> None:
    warnings = [
        ContractWarning(warning_code="x", message="first", affected_field="a"),
        ContractWarning(warning_code="x", message="second", affected_field="a"),
    ]
    assert normalize_warnings(warnings) == [warnings[0]]


def test_warning_order_is_deterministic() -> None:
    warnings = [
        ContractWarning(warning_code="z", message="z", affected_field="b"),
        ContractWarning(warning_code="a", message="a", affected_field="c"),
    ]
    assert [item.warning_code for item in normalize_warnings(warnings)] == ["a", "z"]


def test_warning_messages_do_not_expose_evidence_ids() -> None:
    factory = ScenarioFactory()
    request = factory.with_trig_scores(
        factory.initial_request(), assessment_score=9.0, academic_score=1.0
    )
    response = StudentCompanionFacade(ScenarioMarketProvider(sample_size=2)).analyze(request)
    assert all("EVIDENCE_" not in item.message for item in response.warnings)


def test_stale_profile_warning_only_when_versions_are_comparable() -> None:
    assert not stale_profile_version_warning(None, "v2")
    assert not stale_profile_version_warning("v1", None)
    assert not stale_profile_version_warning("v1", "v1")
    assert stale_profile_version_warning("v1", "v2")[0].warning_code == "stale_profile_version"


def test_valid_different_assessment_scales_are_comparable() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade = StudentCompanionFacade(ScenarioMarketProvider())
    snapshot = facade.analyze(request).snapshot
    followup = factory.followup_request(
        snapshot, request.student, before_score=4, before_max=10, after_score=14, after_max=20
    )
    assert scales_are_comparable(followup.assessment_attempts[0], followup.assessment_attempts[1])


def test_non_overlapping_assessment_skills_warn_scale_mismatch() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade = StudentCompanionFacade(ScenarioMarketProvider())
    snapshot = facade.analyze(request).snapshot
    followup = factory.followup_request(snapshot, request.student, activity_results=[])
    posttest = followup.assessment_attempts[1]
    posttest = posttest.model_copy(
        update={
            "skill_scores": [
                posttest.skill_scores[0].model_copy(update={"skill_id": "SKILL_OTHER"})
            ]
        },
        deep=True,
    )
    response = facade.evaluate_followup(
        followup.model_copy(
            update={"assessment_attempts": [followup.assessment_attempts[0], posttest]},
            deep=True,
        )
    )
    assert "assessment_scale_mismatch" in {
        item.warning_code for item in response.warnings
    }


@pytest.mark.parametrize("activity_id", sorted(ACTIVITY_CATALOG))
def test_activity_catalog_entries_are_complete(activity_id: str) -> None:
    item = ACTIVITY_CATALOG[activity_id]
    assert {
        "activity_id",
        "career_group_id",
        "title",
        "description",
        "skill_ids",
        "estimated_minutes",
        "difficulty",
        "prerequisite_skill_ids",
        "rubric_dimensions",
        "reflection_questions",
        "activity_version",
    } <= set(item)
    assert item["estimated_minutes"] <= 45
    assert item["reflection_questions"]


def test_catalog_covers_seven_career_groups() -> None:
    assert len(CAREER_ACTIVITY_BY_GROUP) >= 7


def test_low_confidence_cannot_create_high_academic_gap() -> None:
    factory = ScenarioFactory()
    student = factory.initial_request().student
    estimate = AbilityEstimate(
        skill_id="SKILL_TRIG_TRANSFORMATION",
        estimated_level=0.0,
        confidence=0.2,
        trend=AbilityTrend.UNKNOWN,
        evidence_ids=["E1"],
        estimate_version="test",
    )
    gap = next(item for item in build_gaps(student, [estimate], []) if item.skill_id)
    assert gap.priority is not GapPriority.HIGH


def test_exam_week_increases_internal_academic_priority() -> None:
    factory = ScenarioFactory()
    student = factory.initial_request().student
    estimate = AbilityEstimate(
        skill_id="SKILL_TRIG_TRANSFORMATION",
        estimated_level=0.4,
        confidence=0.9,
        trend=AbilityTrend.UNKNOWN,
        evidence_ids=["E1", "E2"],
        estimate_version="test",
    )
    normal = academic_priority_score(student, estimate, 0.25)
    exam = academic_priority_score(student.model_copy(update={"exam_week": True}), estimate, 0.25)
    assert exam > normal


def test_market_sample_does_not_change_gap_priority() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    large = StudentCompanionFacade(ScenarioMarketProvider(sample_size=100)).analyze(request)
    small = StudentCompanionFacade(ScenarioMarketProvider(sample_size=1)).analyze(request)
    assert large.gaps == small.gaps


def test_experiencing_all_interests_closes_decision_gap() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    activities = [
        factory.activity_result("CAREER_GROUP_DATA_AI"),
        factory.activity_result("CAREER_GROUP_ECONOMICS"),
    ]
    request = request.model_copy(
        update={"prior_activity_results": activities}, deep=True
    )
    response = StudentCompanionFacade(ScenarioMarketProvider()).analyze(request)
    assert all(item.gap_type.value != "decision" for item in response.gaps)
