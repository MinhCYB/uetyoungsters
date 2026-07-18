"""Resettable in-memory demo state for the Companion golden path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisRecord:
    analysis_id: str
    profile_version: int
    display_name: str
    core_request: Any
    core_response: Any


@dataclass(frozen=True)
class PlanRecord:
    plan_id: str
    analysis_id: str
    core_response: Any


class CompanionStore:
    """Process-local demo store; this is not production persistence."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._analyses: dict[str, AnalysisRecord] = {}
        self._plans: dict[str, PlanRecord] = {}

    def save_analysis(self, record: AnalysisRecord) -> None:
        self._analyses[record.analysis_id] = record

    def get_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        return self._analyses.get(analysis_id)

    def save_plan(self, record: PlanRecord) -> None:
        self._plans[record.plan_id] = record

    def get_plan(self, plan_id: str) -> PlanRecord | None:
        return self._plans.get(plan_id)


companion_store = CompanionStore()
