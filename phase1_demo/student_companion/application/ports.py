"""Dependency-inversion ports for future production integrations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from phase1_demo.student_companion.contracts import (
    FollowupEvaluationRequest,
    InitialAnalysisRequest,
)
from phase1_demo.student_companion.domain import MarketCareerGroup, StudentSnapshot


@runtime_checkable
class MarketContextProvider(Protocol):
    def get_market_context(
        self,
        career_group_ids: list[str],
    ) -> list[MarketCareerGroup]: ...


@runtime_checkable
class StudentInputProvider(Protocol):
    def load_initial_request(self) -> InitialAnalysisRequest: ...

    def load_followup_request(
        self,
        previous_snapshot: StudentSnapshot,
    ) -> FollowupEvaluationRequest: ...

