"""Demo-only adapter from synthetic fixtures to the public request contract."""

from __future__ import annotations

from pathlib import Path

from phase1_demo.student_companion.contracts import (
    CONTRACT_VERSION,
    ContractMetadata,
    FollowupEvaluationRequest,
    InitialAnalysisRequest,
    PlanGenerationRequest,
)
from phase1_demo.student_companion.domain import StudentProfile, StudentSnapshot
from phase1_demo.student_companion.infrastructure.fixtures import (
    DEFAULT_FIXTURE_ROOT,
    load_followup_fixtures,
    load_initial_fixtures,
)


class DemoContractAdapter:
    """Stable input provider used by tests and exported contract examples."""

    def __init__(self, fixture_root: Path = DEFAULT_FIXTURE_ROOT) -> None:
        self.fixture_root = fixture_root

    def load_initial_request(self) -> InitialAnalysisRequest:
        fixtures = load_initial_fixtures(self.fixture_root)
        return InitialAnalysisRequest(
            metadata=ContractMetadata(
                contract_version=CONTRACT_VERSION,
                request_id="DEMO_INITIAL_ANALYSIS_001",
                source_system="phase1_demo.synthetic_fixtures",
                taxonomy_version="0.4.0",
                requested_at=fixtures.pretest_attempt.completed_at,
            ),
            student=fixtures.student,
            academic_records=list(fixtures.academic_records),
            teacher_observations=list(fixtures.teacher_observations),
            assessment_attempts=[fixtures.pretest_attempt],
            self_report=fixtures.self_report,
            prior_activity_results=[],
        )

    def load_plan_request(
        self,
        student: StudentProfile,
        snapshot: StudentSnapshot,
    ) -> PlanGenerationRequest:
        return PlanGenerationRequest(
            metadata=ContractMetadata(
                contract_version=CONTRACT_VERSION,
                request_id="DEMO_PLAN_GENERATION_001",
                source_system="phase1_demo.synthetic_fixtures",
                taxonomy_version="0.4.0",
                requested_at=snapshot.created_at,
            ),
            student=student,
            snapshot=snapshot,
            completed_activity_ids=[],
        )

    def load_followup_request(
        self,
        previous_snapshot: StudentSnapshot,
    ) -> FollowupEvaluationRequest:
        initial = load_initial_fixtures(self.fixture_root)
        followup = load_followup_fixtures(self.fixture_root)
        return FollowupEvaluationRequest(
            metadata=ContractMetadata(
                contract_version=CONTRACT_VERSION,
                request_id="DEMO_FOLLOWUP_EVALUATION_001",
                source_system="phase1_demo.synthetic_fixtures",
                taxonomy_version="0.4.0",
                requested_at=followup.posttest_attempt.completed_at,
            ),
            student=initial.student,
            previous_snapshot=previous_snapshot,
            assessment_attempts=[
                initial.pretest_attempt,
                followup.posttest_attempt,
            ],
            activity_results=[followup.activity_result],
        )
