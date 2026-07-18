"""Executable acceptance scenarios for Student Companion Engine V1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import ValidationError

from phase1_demo.scenario_factory import ScenarioFactory, ScenarioMarketProvider
from phase1_demo.student_companion.application.facade import StudentCompanionFacade
from phase1_demo.student_companion.domain import AssessmentAttempt, GapType


def _codes(response) -> set[str]:
    return {item.warning_code for item in response.warnings}


def _analyze(factory: ScenarioFactory, request, provider=None):
    facade = StudentCompanionFacade(provider or ScenarioMarketProvider())
    return facade, facade.analyze(request)


def _plan(factory: ScenarioFactory, facade, request, analysis, completed=()):
    plan_request = factory.adapter.load_plan_request(request.student, analysis.snapshot)
    plan_request = plan_request.model_copy(
        update={"completed_activity_ids": list(completed)}, deep=True
    )
    return facade.generate_plan(plan_request)


def s01_happy_path() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    plan = _plan(factory, facade, request, analysis)
    followup = factory.adapter.load_followup_request(
        analysis.snapshot.model_copy(update={"active_plan": plan.plan}, deep=True)
    )
    result = facade.evaluate_followup(followup)
    assert plan.plan.total_planned_minutes == 45
    assert any(item.status.value == "meaningful_improvement" for item in result.outcomes)
    assert result.next_step and result.next_step.career_group_id == "CAREER_GROUP_ECONOMICS"


def s02_exam_week() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request(exam_week=True)
    facade, analysis = _analyze(factory, request)
    plan = _plan(factory, facade, request, analysis).plan
    assert plan.tasks
    assert all(item.task_type.value == "academic_practice" for item in plan.tasks)
    assert plan.total_planned_minutes <= plan.weekly_budget_minutes


def s03_missing_self_report() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request(include_self_report=False)
    _, response = _analyze(factory, request)
    assert "optional_data_missing" in _codes(response)
    assert all(not item.skill_id.startswith("INTEREST_") for item in response.ability_profile)


def s04_missing_teacher_observation() -> None:
    factory = ScenarioFactory()
    full = factory.initial_request()
    missing = factory.initial_request(include_teacher=False)
    _, full_response = _analyze(factory, full)
    _, missing_response = _analyze(factory, missing)
    full_confidence = next(
        item.confidence
        for item in full_response.ability_profile
        if item.skill_id == "SKILL_TRIG_TRANSFORMATION"
    )
    missing_confidence = next(
        item.confidence
        for item in missing_response.ability_profile
        if item.skill_id == "SKILL_TRIG_TRANSFORMATION"
    )
    assert missing_confidence < full_confidence
    assert "optional_data_missing" in _codes(missing_response)


def s05_conflicting_evidence() -> None:
    factory = ScenarioFactory()
    agreeing = factory.with_trig_scores(
        factory.initial_request(include_teacher=False),
        assessment_score=9.0,
        academic_score=9.0,
    )
    conflicting = factory.with_trig_scores(
        factory.initial_request(), assessment_score=9.0, academic_score=2.0
    )
    _, agreeing_response = _analyze(factory, agreeing)
    _, conflicting_response = _analyze(factory, conflicting)
    good = next(item for item in agreeing_response.ability_profile if "TRIG" in item.skill_id)
    conflict = next(item for item in conflicting_response.ability_profile if "TRIG" in item.skill_id)
    assert "conflicting_evidence" in _codes(conflicting_response)
    assert conflict.confidence < good.confidence


def s06_no_improvement() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    followup = factory.followup_request(
        analysis.snapshot, request.student, before_score=4.0, after_score=4.0
    )
    result = facade.evaluate_followup(followup)
    outcome = next(item for item in result.outcomes if "TRIG" in item.metric_type)
    estimate = next(item for item in result.current_snapshot.ability_profile if "TRIG" in item.skill_id)
    assert outcome.status.value == "no_meaningful_change"
    assert estimate.trend.value != "improving"


def s07_partial_improvement() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    original_gap = next(item for item in analysis.gaps if item.skill_id == "SKILL_TRIG_TRANSFORMATION")
    followup = factory.followup_request(
        analysis.snapshot, request.student, before_score=4.0, after_score=5.0
    )
    result = facade.evaluate_followup(followup)
    outcome = next(item for item in result.outcomes if "TRIG" in item.metric_type)
    gap = next(item for item in result.updated_gaps if item.skill_id == "SKILL_TRIG_TRANSFORMATION")
    assert outcome.status.value == "partial_improvement"
    assert gap.gap_size < original_gap.gap_size


def s08_regression() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    followup = factory.followup_request(
        analysis.snapshot, request.student, before_score=4.0, after_score=1.0
    )
    result = facade.evaluate_followup(followup)
    outcome = next(item for item in result.outcomes if "TRIG" in item.metric_type)
    assert outcome.status.value == "regression"
    assert result.next_step and result.next_step.skill_id == "SKILL_TRIG_TRANSFORMATION"
    assert "củng cố" in result.next_step.reason


def s09_partial_completion() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    incomplete = factory.activity_result("CAREER_GROUP_DATA_AI", completed=False)
    followup = factory.followup_request(
        analysis.snapshot,
        request.student,
        before_score=4.0,
        after_score=4.0,
        activity_results=[incomplete],
    )
    result = facade.evaluate_followup(followup)
    assert not any(item.metric_type.startswith("INTEREST_") for item in result.outcomes)
    assert any(
        item.gap_type is GapType.EXPLORATION
        and item.career_group_ids == ["CAREER_GROUP_DATA_AI"]
        for item in result.updated_gaps
    )


def s10_three_career_interests() -> None:
    factory = ScenarioFactory()
    interests = [
        "CAREER_GROUP_DATA_AI",
        "CAREER_GROUP_ECONOMICS",
        "CAREER_GROUP_MARKETING_COMMUNICATION",
    ]
    request = factory.initial_request(career_interests=interests)
    data_result = factory.activity_result("CAREER_GROUP_DATA_AI")
    request = request.model_copy(update={"prior_activity_results": [data_result]}, deep=True)
    facade, analysis = _analyze(factory, request)
    plan = _plan(factory, facade, request, analysis, [data_result.activity_id]).plan
    assert any(item.gap_type is GapType.DECISION for item in analysis.gaps)
    assert any(item.career_group_id == "CAREER_GROUP_ECONOMICS" for item in plan.tasks)


def s11_small_market_sample() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    _, response = _analyze(factory, request, ScenarioMarketProvider(sample_size=2))
    assert "small_market_sample" in _codes(response)
    assert response.ability_profile


def s12_unknown_career_group() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request(career_interests=["CAREER_GROUP_UNKNOWN"])
    facade, response = _analyze(
        factory, request, ScenarioMarketProvider(known_groups=set())
    )
    plan = _plan(factory, facade, request, response).plan
    assert "unknown_career_group" in _codes(response)
    assert response.ability_profile
    assert all(item.task_type.value != "career_micro_experience" for item in plan.tasks)


def s13_completed_activity_not_repeated() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    plan = _plan(factory, facade, request, analysis, ["ACTIVITY_DATA_INSIGHTS"]).plan
    assert all(item.career_group_id != "CAREER_GROUP_DATA_AI" for item in plan.tasks)


def s14_scale_normalization() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    followup = factory.followup_request(
        analysis.snapshot,
        request.student,
        before_score=4.0,
        before_max=10.0,
        after_score=14.0,
        after_max=20.0,
    )
    result = facade.evaluate_followup(followup)
    outcome = next(item for item in result.outcomes if "TRIG" in item.metric_type)
    assert outcome.before_value == 0.4
    assert outcome.after_value == 0.7
    assert "assessment_scale_mismatch" not in _codes(result)


def s15_invalid_scale() -> None:
    factory = ScenarioFactory()
    attempt = factory.adapter.load_initial_request().assessment_attempts[0]
    data = attempt.model_dump()
    data["skill_scores"][0]["max_score"] = 0
    try:
        AssessmentAttempt.model_validate(data)
    except ValidationError:
        return
    raise AssertionError("zero max_score must be rejected")


def s16_baseline_missing() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    followup = factory.followup_request(
        analysis.snapshot, request.student, include_baseline=False, activity_results=[]
    )
    result = facade.evaluate_followup(followup)
    assert "baseline_not_found" in _codes(result)
    assert not any("TRIG" in item.metric_type for item in result.outcomes)


def s17_snapshot_immutability() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade, analysis = _analyze(factory, request)
    before = analysis.snapshot.model_dump_json()
    facade.evaluate_followup(
        factory.followup_request(analysis.snapshot, request.student)
    )
    assert analysis.snapshot.model_dump_json() == before


def s18_duplicate_request_idempotency() -> None:
    factory = ScenarioFactory()
    request = factory.initial_request()
    facade = StudentCompanionFacade(ScenarioMarketProvider(sample_size=2))
    first = facade.analyze(request)
    second = facade.analyze(request)
    assert first.model_dump_json() == second.model_dump_json()
    assert len(first.warnings) == len(
        {(item.warning_code, item.affected_field) for item in first.warnings}
    )
    evidence_ids = [
        evidence_id
        for estimate in first.ability_profile
        for evidence_id in estimate.evidence_ids
    ]
    assert len(evidence_ids) == len(set(evidence_ids))


@dataclass(frozen=True)
class EngineScenario:
    scenario_id: str
    name: str
    run: Callable[[], None]


ENGINE_SCENARIOS = (
    EngineScenario("S01", "happy path", s01_happy_path),
    EngineScenario("S02", "exam week", s02_exam_week),
    EngineScenario("S03", "missing self-report", s03_missing_self_report),
    EngineScenario("S04", "missing teacher observation", s04_missing_teacher_observation),
    EngineScenario("S05", "conflicting evidence", s05_conflicting_evidence),
    EngineScenario("S06", "no improvement", s06_no_improvement),
    EngineScenario("S07", "partial improvement", s07_partial_improvement),
    EngineScenario("S08", "regression", s08_regression),
    EngineScenario("S09", "partial completion", s09_partial_completion),
    EngineScenario("S10", "three career interests", s10_three_career_interests),
    EngineScenario("S11", "small market sample", s11_small_market_sample),
    EngineScenario("S12", "unknown career group", s12_unknown_career_group),
    EngineScenario("S13", "completed activity not repeated", s13_completed_activity_not_repeated),
    EngineScenario("S14", "scale normalization", s14_scale_normalization),
    EngineScenario("S15", "invalid scale", s15_invalid_scale),
    EngineScenario("S16", "baseline missing", s16_baseline_missing),
    EngineScenario("S17", "snapshot immutability", s17_snapshot_immutability),
    EngineScenario("S18", "duplicate request idempotency", s18_duplicate_request_idempotency),
)
