"""Deterministic synthetic scenario factory for engine tests and CLI smoke."""

from __future__ import annotations

from datetime import timedelta

from phase1_demo.student_companion.config import ACTIVITY_CATALOG
from phase1_demo.student_companion.contracts import FollowupEvaluationRequest
from phase1_demo.student_companion.domain import (
    ActivityResult,
    AssessmentAttempt,
    AssessmentType,
    MarketCareerGroup,
)
from phase1_demo.student_companion.infrastructure.demo_contract_adapter import (
    DemoContractAdapter,
)
from phase1_demo.student_companion.infrastructure.fixtures import load_followup_fixtures


class ScenarioMarketProvider:
    def __init__(
        self,
        *,
        known_groups: set[str] | None = None,
        sample_size: int = 10,
    ) -> None:
        catalog_groups = {
            item["career_group_id"]
            for item in ACTIVITY_CATALOG.values()
            if item["career_group_id"] is not None
        }
        self.known_groups = catalog_groups if known_groups is None else known_groups
        self.sample_size = sample_size

    def get_market_context(self, career_group_ids: list[str]) -> list[MarketCareerGroup]:
        return [
            MarketCareerGroup(
                career_group_id=group_id,
                display_name=group_id.removeprefix("CAREER_GROUP_").replace("_", " ").title(),
                market_signal="Deterministic scenario signal; not a career recommendation.",
                sample_size=self.sample_size,
                foundation_skill_ids=["SKILL_LOGICAL_THINKING"],
                snapshot_version="scenario-market-v1",
                taxonomy_version="0.4.0",
                data_mode="fallback_demo",
                source_output_files=["scenario_factory"],
            )
            for group_id in career_group_ids
            if group_id in self.known_groups
        ]


class ScenarioFactory:
    def __init__(self) -> None:
        self.adapter = DemoContractAdapter()

    def initial_request(
        self,
        *,
        exam_week: bool | None = None,
        budget: int | None = None,
        career_interests: list[str] | None = None,
        include_self_report: bool = True,
        include_teacher: bool = True,
    ):
        request = self.adapter.load_initial_request()
        student_updates = {}
        if exam_week is not None:
            student_updates["exam_week"] = exam_week
        if budget is not None:
            student_updates["weekly_available_minutes"] = budget
        if career_interests is not None:
            student_updates["career_interest_ids"] = career_interests
        return request.model_copy(
            update={
                "student": request.student.model_copy(update=student_updates),
                "self_report": request.self_report if include_self_report else None,
                "teacher_observations": (
                    request.teacher_observations if include_teacher else []
                ),
            },
            deep=True,
        )

    def with_trig_scores(
        self,
        request,
        *,
        assessment_score: float,
        academic_score: float,
    ):
        attempts = []
        for attempt in request.assessment_attempts:
            scores = [
                item.model_copy(update={"score": assessment_score})
                if item.skill_id == "SKILL_TRIG_TRANSFORMATION"
                else item
                for item in attempt.skill_scores
            ]
            attempts.append(attempt.model_copy(update={"skill_scores": scores}, deep=True))
        records = [
            item.model_copy(update={"score": academic_score})
            if item.topic_id == "SKILL_TRIG_TRANSFORMATION"
            else item
            for item in request.academic_records
        ]
        return request.model_copy(
            update={"assessment_attempts": attempts, "academic_records": records},
            deep=True,
        )

    def activity_result(
        self,
        career_group_id: str,
        *,
        completed: bool = True,
        rubric_score: float | None = 4.0,
    ) -> ActivityResult:
        template = load_followup_fixtures().activity_result
        activity_id = next(
            activity_id
            for activity_id, item in ACTIVITY_CATALOG.items()
            if item["career_group_id"] == career_group_id
        )
        return template.model_copy(
            update={
                "activity_result_id": f"RESULT_{activity_id}",
                "activity_id": activity_id,
                "career_group_id": career_group_id,
                "completed": completed,
                "rubric_score": rubric_score if completed else None,
                "max_score": 5.0 if completed else None,
            },
            deep=True,
        )

    def followup_request(
        self,
        previous_snapshot,
        student,
        *,
        before_score: float = 4.0,
        before_max: float = 10.0,
        after_score: float = 7.0,
        after_max: float = 10.0,
        include_baseline: bool = True,
        activity_results: list[ActivityResult] | None = None,
    ) -> FollowupEvaluationRequest:
        source = self.adapter.load_followup_request(previous_snapshot)
        baseline = self._attempt_with_score(
            source.assessment_attempts[0],
            AssessmentType.PRETEST,
            before_score,
            before_max,
            "SCENARIO_PRETEST",
        )
        posttest = self._attempt_with_score(
            source.assessment_attempts[1],
            AssessmentType.POSTTEST,
            after_score,
            after_max,
            "SCENARIO_POSTTEST",
        )
        return source.model_copy(
            update={
                "student": student,
                "assessment_attempts": (
                    [baseline, posttest] if include_baseline else [posttest]
                ),
                "activity_results": (
                    source.activity_results
                    if activity_results is None
                    else activity_results
                ),
            },
            deep=True,
        )

    @staticmethod
    def _attempt_with_score(
        attempt: AssessmentAttempt,
        assessment_type: AssessmentType,
        score: float,
        max_score: float,
        attempt_id: str,
    ) -> AssessmentAttempt:
        trig = next(
            item
            for item in attempt.skill_scores
            if item.skill_id == "SKILL_TRIG_TRANSFORMATION"
        )
        return attempt.model_copy(
            update={
                "attempt_id": attempt_id,
                "assessment_type": assessment_type,
                "skill_scores": [trig.model_copy(update={"score": score, "max_score": max_score})],
                "completed_at": (
                    attempt.completed_at
                    if assessment_type is AssessmentType.PRETEST
                    else attempt.completed_at + timedelta(days=1)
                ),
            },
            deep=True,
        )
