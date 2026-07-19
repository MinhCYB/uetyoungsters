"""Versioned response models returned by the public Student Companion facade."""

from __future__ import annotations

from pydantic import model_validator

from phase1_demo.student_companion.contracts.common import (
    ContractMetadata,
    ContractModel,
    ContractWarning,
    EvidenceSummary,
    NonEmptyStr,
)
from phase1_demo.student_companion.domain import (
    AbilityEstimate,
    Gap,
    MarketCareerGroup,
    OutcomeEvaluation,
    PlanTask,
    StudentSnapshot,
    WeeklyPlan,
)


def _validate_summary_sources(items: list[EvidenceSummary]) -> None:
    sources = [item.source_type for item in items]
    if len(sources) != len(set(sources)):
        raise ValueError("evidence_summary must not contain duplicate source_type values")


class InitialAnalysisResponse(ContractModel):
    metadata: ContractMetadata
    student_id: NonEmptyStr
    snapshot: StudentSnapshot
    ability_profile: list[AbilityEstimate]
    gaps: list[Gap]
    market_context: list[MarketCareerGroup]
    evidence_summary: list[EvidenceSummary]
    warnings: list[ContractWarning]

    @model_validator(mode="after")
    def validate_response_consistency(self) -> InitialAnalysisResponse:
        if self.student_id != self.snapshot.student_id:
            raise ValueError("student_id must match snapshot.student_id")
        if self.ability_profile != self.snapshot.ability_profile:
            raise ValueError("ability_profile must match snapshot.ability_profile")
        if self.gaps != self.snapshot.gaps:
            raise ValueError("gaps must match snapshot.gaps")
        if any(not item.snapshot_version.strip() for item in self.market_context):
            raise ValueError("every market context item requires snapshot_version")
        _validate_summary_sources(self.evidence_summary)
        return self


class PlanGenerationResponse(ContractModel):
    metadata: ContractMetadata
    student_id: NonEmptyStr
    plan: WeeklyPlan
    warnings: list[ContractWarning]

    @model_validator(mode="after")
    def validate_response_consistency(self) -> PlanGenerationResponse:
        if self.plan.student_id != self.student_id:
            raise ValueError("plan.student_id must match student_id")
        if self.plan.total_planned_minutes > self.plan.weekly_budget_minutes:
            raise ValueError("plan must not exceed weekly budget")
        return self


class FollowupEvaluationResponse(ContractModel):
    metadata: ContractMetadata
    student_id: NonEmptyStr
    previous_snapshot_id: NonEmptyStr
    current_snapshot: StudentSnapshot
    outcomes: list[OutcomeEvaluation]
    updated_gaps: list[Gap]
    next_step: PlanTask | None
    evidence_summary: list[EvidenceSummary]
    warnings: list[ContractWarning]

    @model_validator(mode="after")
    def validate_response_consistency(self) -> FollowupEvaluationResponse:
        if self.current_snapshot.previous_snapshot_id != self.previous_snapshot_id:
            raise ValueError(
                "current_snapshot.previous_snapshot_id must match previous_snapshot_id"
            )
        if self.student_id != self.current_snapshot.student_id:
            raise ValueError("student_id must match current_snapshot.student_id")
        if self.outcomes != self.current_snapshot.outcomes:
            raise ValueError("outcomes must match current_snapshot.outcomes")
        if self.updated_gaps != self.current_snapshot.gaps:
            raise ValueError("updated_gaps must match current_snapshot.gaps")
        _validate_summary_sources(self.evidence_summary)
        return self

