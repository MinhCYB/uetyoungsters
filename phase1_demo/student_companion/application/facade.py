"""Stateless public application facade for Student Companion core."""

from __future__ import annotations

from collections import Counter

from phase1_demo.student_companion.application.ports import MarketContextProvider
from phase1_demo.student_companion.config import PIPELINE_VERSION
from phase1_demo.student_companion.contracts import (
    ContractError,
    ContractExecutionError,
    ContractWarning,
    EvidenceSummary,
    FollowupEvaluationRequest,
    FollowupEvaluationResponse,
    InitialAnalysisRequest,
    InitialAnalysisResponse,
    PlanGenerationRequest,
    PlanGenerationResponse,
)
from phase1_demo.student_companion.domain import AssessmentType, StudentSnapshot
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
        returned_groups = {item.career_group_id for item in market_context}
        missing_groups = [
            item
            for item in request.student.career_interest_ids
            if item not in returned_groups
        ]
        if missing_groups:
            raise ContractExecutionError(
                ContractError(
                    error_code="unknown_career_group",
                    message=f"No market context for: {', '.join(missing_groups)}",
                    field_path="student.career_interest_ids",
                    recoverable=True,
                )
            )
        market_version = "+".join(
            sorted({item.snapshot_version for item in market_context})
        )
        if not market_version:
            raise ContractExecutionError(
                ContractError(
                    error_code="market_context_unavailable",
                    message="Market context did not provide a snapshot version.",
                    field_path="market_context",
                    recoverable=True,
                )
            )
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
        warnings = self._initial_warnings(request, market_context, evidence)
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
        warnings = []
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
            warnings=warnings,
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
        updated_estimates = build_ability_profile(
            new_evidence,
            previous=request.previous_snapshot.ability_profile,
        )
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
        outcomes = self._followup_outcomes(
            request,
            assessment_evidence,
            activity_evidence,
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
        warnings = self._followup_warnings(request)
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
    def _initial_warnings(request, market_context, evidence) -> list[ContractWarning]:
        warnings: list[ContractWarning] = []
        optional_fields = (
            ("academic_records", request.academic_records),
            ("teacher_observations", request.teacher_observations),
            ("self_report", request.self_report),
        )
        for field_name, value in optional_fields:
            if not value:
                warnings.append(
                    ContractWarning(
                        warning_code="optional_data_missing",
                        message=f"Optional input '{field_name}' was not provided.",
                        affected_field=field_name,
                    )
                )
        if len(evidence) < 2:
            warnings.append(
                ContractWarning(
                    warning_code="insufficient_evidence",
                    message="Ability estimates are based on fewer than two evidence items.",
                    affected_field="ability_profile",
                )
            )
        for item in market_context:
            if item.sample_size < 5:
                warnings.append(
                    ContractWarning(
                        warning_code="small_market_sample",
                        message=f"Market sample for {item.career_group_id} is below 5.",
                        affected_field="market_context",
                    )
                )
        return _sorted_warnings(warnings)

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

    @staticmethod
    def _followup_warnings(request) -> list[ContractWarning]:
        has_posttest = any(
            item.assessment_type is AssessmentType.POSTTEST
            for item in request.assessment_attempts
        )
        has_baseline = any(
            item.assessment_type in {AssessmentType.DIAGNOSTIC, AssessmentType.PRETEST}
            for item in request.assessment_attempts
        )
        warnings = []
        if has_posttest and not has_baseline:
            warnings.append(
                ContractWarning(
                    warning_code="optional_data_missing",
                    message="Posttest was provided without a comparable diagnostic/pretest.",
                    affected_field="assessment_attempts",
                )
            )
        return warnings


def _summarize_evidence(evidence) -> list[EvidenceSummary]:
    counts = Counter(item.source_type for item in evidence)
    return [
        EvidenceSummary(source_type=source_type, evidence_count=counts[source_type])
        for source_type in sorted(counts, key=lambda item: item.value)
    ]


def _sorted_warnings(warnings: list[ContractWarning]) -> list[ContractWarning]:
    return sorted(
        warnings,
        key=lambda item: (item.warning_code, item.affected_field or "", item.message),
    )

