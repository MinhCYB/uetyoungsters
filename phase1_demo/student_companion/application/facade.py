"""Stateless public application facade for Student Companion core."""

from __future__ import annotations

from collections import Counter

from phase1_demo.student_companion.application.ports import MarketContextProvider
from phase1_demo.student_companion.config import PIPELINE_VERSION
from phase1_demo.student_companion.contracts import (
    ContractWarning,
    EvidenceSummary,
    FollowupEvaluationRequest,
    FollowupEvaluationResponse,
    InitialAnalysisRequest,
    InitialAnalysisResponse,
    PlanGenerationRequest,
    PlanGenerationResponse,
)
from phase1_demo.student_companion.domain import (
    AbilityTrend,
    AssessmentType,
    OutcomeStatus,
    StudentSnapshot,
)
from phase1_demo.student_companion.domain.rules import (
    build_ability_profile,
    build_gaps,
    evaluate_assessment_outcomes,
    evaluate_interest_outcome,
    generate_weekly_plan,
    merge_evidence,
    normalize_academic_records,
    normalize_activity_result,
    normalize_assessment,
    normalize_self_report,
    normalize_teacher_observations,
    select_next_step,
    stable_id,
)
from phase1_demo.student_companion.domain.warnings import (
    evidence_warnings,
    followup_warnings,
    initial_warnings,
    normalize_warnings,
)


class StudentCompanionFacade:
    """Three stateless use cases exposed to production adapters."""

    def __init__(self, market_provider: MarketContextProvider) -> None:
        self._market_provider = market_provider

    def analyze(self, request: InitialAnalysisRequest) -> InitialAnalysisResponse:
        assessment_evidence = [
            normalize_assessment(attempt) for attempt in request.assessment_attempts
        ]
        activity_evidence = [
            normalize_activity_result(result) for result in request.prior_activity_results
        ]
        evidence = merge_evidence(
            normalize_academic_records(request.academic_records),
            normalize_teacher_observations(request.teacher_observations),
            *assessment_evidence,
            *activity_evidence,
            *(
                [normalize_self_report(request.self_report)]
                if request.self_report is not None
                else []
            ),
        )
        ability_profile = build_ability_profile(evidence)
        gaps = build_gaps(
            request.student,
            ability_profile,
            evidence,
            activity_results=request.prior_activity_results,
        )
        market_context = self._market_provider.get_market_context(
            request.student.career_interest_ids
        )
        market_version = "+".join(
            sorted({item.snapshot_version for item in market_context})
        )
        if not market_version:
            market_version = "market-context-unavailable-v1"
        snapshot = StudentSnapshot(
            snapshot_id=stable_id(
                "SNAPSHOT", "initial", request.metadata.request_id, request.student.student_id
            ),
            previous_snapshot_id=None,
            student_id=request.student.student_id,
            created_at=request.metadata.requested_at,
            ability_profile=ability_profile,
            gaps=gaps,
            active_plan=None,
            outcomes=[],
            market_snapshot_version=market_version,
            pipeline_version=PIPELINE_VERSION,
        )
        warnings = initial_warnings(
            request,
            market_context,
            evidence,
            ability_profile,
        )
        return InitialAnalysisResponse(
            metadata=request.metadata,
            student_id=request.student.student_id,
            snapshot=snapshot,
            ability_profile=ability_profile,
            gaps=gaps,
            market_context=market_context,
            evidence_summary=_summarize_evidence(evidence),
            warnings=warnings,
        )

    def generate_plan(self, request: PlanGenerationRequest) -> PlanGenerationResponse:
        plan = generate_weekly_plan(
            student=request.student,
            gaps=request.snapshot.gaps,
            generated_at=request.metadata.requested_at,
            plan_id=stable_id(
                "PLAN", request.metadata.request_id, request.student.student_id
            ),
            completed_activity_ids=request.completed_activity_ids,
        )
        warnings: list[ContractWarning] = []
        if not plan.tasks:
            warnings.append(
                ContractWarning(
                    warning_code="insufficient_evidence",
                    message="No eligible task could be selected within the current budget.",
                    affected_field="plan.tasks",
                )
            )
        return PlanGenerationResponse(
            metadata=request.metadata,
            student_id=request.student.student_id,
            plan=plan,
            warnings=normalize_warnings(warnings),
        )

    def evaluate_followup(
        self,
        request: FollowupEvaluationRequest,
    ) -> FollowupEvaluationResponse:
        assessment_evidence = {
            attempt.attempt_id: normalize_assessment(attempt)
            for attempt in request.assessment_attempts
        }
        activity_evidence = {
            result.activity_result_id: normalize_activity_result(result)
            for result in request.activity_results
        }
        new_evidence = merge_evidence(
            *assessment_evidence.values(),
            *activity_evidence.values(),
        )
        outcomes = self._followup_outcomes(
            request,
            assessment_evidence,
            activity_evidence,
        )
        updated_estimates = build_ability_profile(
            new_evidence,
            previous=request.previous_snapshot.ability_profile,
        )
        assessment_trends = {
            item.metric_type: {
                OutcomeStatus.MEANINGFUL_IMPROVEMENT: AbilityTrend.IMPROVING,
                OutcomeStatus.PARTIAL_IMPROVEMENT: AbilityTrend.IMPROVING,
                OutcomeStatus.NO_MEANINGFUL_CHANGE: AbilityTrend.STABLE,
                OutcomeStatus.REGRESSION: AbilityTrend.DECLINING,
            }[item.status]
            for item in outcomes
            if not item.metric_type.startswith("INTEREST_")
        }
        updated_estimates = [
            item.model_copy(
                update={"trend": assessment_trends.get(item.skill_id, item.trend)}
            )
            for item in updated_estimates
        ]
        estimates_by_skill = {
            item.skill_id: item for item in request.previous_snapshot.ability_profile
        }
        estimates_by_skill.update({item.skill_id: item for item in updated_estimates})
        ability_profile = [estimates_by_skill[key] for key in sorted(estimates_by_skill)]
        updated_gaps = build_gaps(
            request.student,
            ability_profile,
            new_evidence,
            activity_results=request.activity_results,
        )
        completed_activity_ids = [
            item.activity_id for item in request.activity_results if item.completed
        ]
        next_step = select_next_step(
            request.student,
            updated_gaps,
            completed_activity_ids=completed_activity_ids,
        )
        snapshot = StudentSnapshot(
            snapshot_id=stable_id(
                "SNAPSHOT",
                "followup",
                request.metadata.request_id,
                request.previous_snapshot.snapshot_id,
            ),
            previous_snapshot_id=request.previous_snapshot.snapshot_id,
            student_id=request.student.student_id,
            created_at=request.metadata.requested_at,
            ability_profile=ability_profile,
            gaps=updated_gaps,
            active_plan=None,
            outcomes=outcomes,
            market_snapshot_version=request.previous_snapshot.market_snapshot_version,
            pipeline_version=PIPELINE_VERSION,
        )
        warnings = normalize_warnings(
            [
                *followup_warnings(request),
                *evidence_warnings(new_evidence, updated_estimates),
            ]
        )
        return FollowupEvaluationResponse(
            metadata=request.metadata,
            student_id=request.student.student_id,
            previous_snapshot_id=request.previous_snapshot.snapshot_id,
            current_snapshot=snapshot,
            outcomes=outcomes,
            updated_gaps=updated_gaps,
            next_step=next_step,
            evidence_summary=_summarize_evidence(new_evidence),
            warnings=warnings,
        )

    @staticmethod
    def _followup_outcomes(request, assessment_evidence, activity_evidence):
        outcomes = []
        prior_attempts = sorted(
            (
                item
                for item in request.assessment_attempts
                if item.assessment_type
                in {AssessmentType.DIAGNOSTIC, AssessmentType.PRETEST}
            ),
            key=lambda item: (item.completed_at, item.attempt_id),
        )
        posttests = sorted(
            (
                item
                for item in request.assessment_attempts
                if item.assessment_type is AssessmentType.POSTTEST
            ),
            key=lambda item: (item.completed_at, item.attempt_id),
        )
        for posttest in posttests:
            candidates = [
                item
                for item in prior_attempts
                if item.assessment_id == posttest.assessment_id
                and item.completed_at <= posttest.completed_at
            ]
            if not candidates:
                continue
            before = candidates[-1]
            outcomes.extend(
                evaluate_assessment_outcomes(
                    before,
                    posttest,
                    assessment_evidence[before.attempt_id],
                    assessment_evidence[posttest.attempt_id],
                )
            )
        for activity in sorted(
            request.activity_results,
            key=lambda item: (item.completed_at, item.activity_result_id),
        ):
            normalized = activity_evidence[activity.activity_result_id]
            if normalized:
                outcomes.append(evaluate_interest_outcome(activity, normalized))
        return sorted(outcomes, key=lambda item: item.evaluation_id)

def _summarize_evidence(evidence) -> list[EvidenceSummary]:
    counts = Counter(item.source_type for item in evidence)
    return [
        EvidenceSummary(source_type=source_type, evidence_count=counts[source_type])
        for source_type in sorted(counts, key=lambda item: item.value)
    ]
