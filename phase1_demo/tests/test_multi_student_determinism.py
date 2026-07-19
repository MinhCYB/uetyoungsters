from __future__ import annotations

from itertools import product

from phase1_demo.scenario_factory import ScenarioFactory, ScenarioMarketProvider
from phase1_demo.student_companion.application.facade import StudentCompanionFacade
from phase1_demo.student_companion.contracts import InitialAnalysisRequest


def test_thirty_student_variations_are_isolated_and_deterministic() -> None:
    factory = ScenarioFactory()
    facade = StudentCompanionFacade(ScenarioMarketProvider(sample_size=8))
    variations = list(product([20, 30, 45, 60, 90], [2.0, 4.0, 6.0], [False, True]))
    assert len(variations) == 30

    first_pass: list[str] = []
    inputs: list[str] = []
    for index, (budget, score, exam_week) in enumerate(variations):
        interest_count = 1 + index % 3
        interests = [
            "CAREER_GROUP_DATA_AI",
            "CAREER_GROUP_ECONOMICS",
            "CAREER_GROUP_MARKETING_COMMUNICATION",
        ][:interest_count]
        request = factory.initial_request(
            budget=budget,
            exam_week=exam_week,
            career_interests=interests,
            include_self_report=index % 2 == 0,
            include_teacher=index % 3 != 0,
        )
        request = factory.with_trig_scores(
            request,
            assessment_score=score,
            academic_score=score,
        )
        before = request.model_dump_json()
        response = facade.analyze(request)
        plan_request = factory.adapter.load_plan_request(request.student, response.snapshot)
        plan = facade.generate_plan(plan_request)
        assert plan.plan.total_planned_minutes <= budget
        assert request.model_dump_json() == before
        inputs.append(before)
        first_pass.append(response.model_dump_json() + plan.model_dump_json())

    second_pass: list[str] = []
    for payload in inputs:
        request = InitialAnalysisRequest.model_validate_json(payload)
        response = facade.analyze(request)
        plan_request = factory.adapter.load_plan_request(request.student, response.snapshot)
        plan = facade.generate_plan(plan_request)
        second_pass.append(response.model_dump_json() + plan.model_dump_json())

    assert second_pass == first_pass
