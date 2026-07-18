"""In-memory orchestration for the Student Companion Phase 1 demo."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from phase1_demo.student_companion.config import PIPELINE_VERSION
from phase1_demo.student_companion.domain import StudentSnapshot
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
)
from phase1_demo.student_companion.infrastructure.fixtures import (
    DEFAULT_FIXTURE_ROOT,
    FollowupFixtures,
    InitialFixtures,
    load_followup_fixtures,
    load_initial_fixtures,
)
from phase1_demo.student_companion.infrastructure.market import (
    DEFAULT_FALLBACK_PATH,
    DEFAULT_PROCESSED_ROOT,
    build_market_snapshot,
)


class DemoStage(str, Enum):
    INITIAL = "initial"
    ANALYZED = "analyzed"
    PLANNED = "planned"
    ADVANCED = "advanced"


class InvalidTransition(RuntimeError):
    """Raised when a demo action is called from the wrong stage."""


class DemoService:
    def __init__(
        self,
        fixture_root: Path = DEFAULT_FIXTURE_ROOT,
        processed_root: Path = DEFAULT_PROCESSED_ROOT,
        fallback_path: Path = DEFAULT_FALLBACK_PATH,
    ) -> None:
        self.fixture_root = fixture_root
        self.processed_root = processed_root
        self.fallback_path = fallback_path
        self.reset()

    def reset(self) -> dict:
        self.initial: InitialFixtures = load_initial_fixtures(self.fixture_root)
        self.followup: FollowupFixtures = load_followup_fixtures(self.fixture_root)
        if self.initial.student.student_id != self.followup.posttest_attempt.student_id:
            raise ValueError("T0 and T1 fixtures must reference the same student")
        self.market = build_market_snapshot(self.processed_root, self.fallback_path)
        self.stage = DemoStage.INITIAL
        self.evidence_t0 = []
        self.new_evidence_t1 = []
        self.ability_t0 = []
        self.ability_t1 = []
        self.gaps_t0 = []
        self.gaps_t1 = []
        self.plan_t0 = None
        self.outcomes_t1 = []
        self.snapshot_t0 = None
        self.snapshot_t1 = None
        self.next_step = None
        return self.get_state()

    def load_initial_state(self) -> dict:
        return self.get_state()

    def analyze_initial_state(self) -> dict:
        self._require_stage(DemoStage.INITIAL)
        self.evidence_t0 = merge_evidence(
            normalize_academic_records(self.initial.academic_records),
            normalize_teacher_observations(self.initial.teacher_observations),
            normalize_assessment(self.initial.pretest_attempt),
            normalize_self_report(self.initial.self_report),
        )
        self.ability_t0 = build_ability_profile(self.evidence_t0)
        self.gaps_t0 = build_gaps(
            self.initial.student,
            self.ability_t0,
            self.evidence_t0,
        )
        self.snapshot_t0 = StudentSnapshot(
            snapshot_id="SNAPSHOT_T0_001",
            previous_snapshot_id=None,
            student_id=self.initial.student.student_id,
            created_at=self.initial.pretest_attempt.completed_at,
            ability_profile=self.ability_t0,
            gaps=self.gaps_t0,
            active_plan=None,
            outcomes=[],
            market_snapshot_version=self._market_snapshot_version(),
            pipeline_version=PIPELINE_VERSION,
        )
        self.stage = DemoStage.ANALYZED
        return self.get_state()

    def generate_weekly_plan(self) -> dict:
        self._require_stage(DemoStage.ANALYZED)
        self.plan_t0 = generate_weekly_plan(
            student=self.initial.student,
            gaps=self.gaps_t0,
            generated_at=self.initial.pretest_attempt.completed_at,
            plan_id="PLAN_T0_001",
        )
        self.snapshot_t0 = self.snapshot_t0.model_copy(
            update={"active_plan": self.plan_t0},
            deep=True,
        )
        self.stage = DemoStage.PLANNED
        return self.get_state()

    def advance_two_weeks(self) -> dict:
        self._require_stage(DemoStage.PLANNED)
        posttest_evidence = normalize_assessment(self.followup.posttest_attempt)
        activity_evidence = normalize_activity_result(self.followup.activity_result)
        self.new_evidence_t1 = merge_evidence(posttest_evidence, activity_evidence)
        combined_evidence = merge_evidence(self.evidence_t0, self.new_evidence_t1)
        self.ability_t1 = build_ability_profile(combined_evidence, previous=self.ability_t0)
        self.gaps_t1 = build_gaps(
            self.initial.student,
            self.ability_t1,
            combined_evidence,
            activity_results=[self.followup.activity_result],
        )
        self.outcomes_t1 = evaluate_assessment_outcomes(
            self.initial.pretest_attempt,
            self.followup.posttest_attempt,
            normalize_assessment(self.initial.pretest_attempt),
            posttest_evidence,
        )
        self.outcomes_t1.append(
            evaluate_interest_outcome(self.followup.activity_result, activity_evidence)
        )
        self.next_step = select_next_step(
            self.initial.student,
            self.gaps_t1,
            completed_activity_ids=[self.followup.activity_result.activity_id],
        )
        self.snapshot_t1 = StudentSnapshot(
            snapshot_id="SNAPSHOT_T1_001",
            previous_snapshot_id=self.snapshot_t0.snapshot_id,
            student_id=self.initial.student.student_id,
            created_at=self.followup.posttest_attempt.completed_at,
            ability_profile=self.ability_t1,
            gaps=self.gaps_t1,
            active_plan=None,
            outcomes=self.outcomes_t1,
            market_snapshot_version=self._market_snapshot_version(),
            pipeline_version=PIPELINE_VERSION,
        )
        self.stage = DemoStage.ADVANCED
        return self.get_state()

    def get_comparison(self) -> dict:
        self._require_stage(DemoStage.ADVANCED)
        before_scores = {
            item.skill_id: item for item in self.initial.pretest_attempt.skill_scores
        }
        after_scores = {
            item.skill_id: item for item in self.followup.posttest_attempt.skill_scores
        }
        assessment_result = None
        trig_skill_id = "SKILL_TRIG_TRANSFORMATION"
        if trig_skill_id in before_scores and trig_skill_id in after_scores:
            assessment_result = {
                "skill_id": trig_skill_id,
                "before_score": before_scores[trig_skill_id].score,
                "before_max_score": before_scores[trig_skill_id].max_score,
                "after_score": after_scores[trig_skill_id].score,
                "after_max_score": after_scores[trig_skill_id].max_score,
            }
        return {
            "student": self.initial.student.model_dump(mode="json"),
            "before": self.snapshot_t0.model_dump(mode="json"),
            "after": self.snapshot_t1.model_dump(mode="json"),
            "new_evidence": [item.model_dump(mode="json") for item in self.new_evidence_t1],
            "next_step": self.next_step.model_dump(mode="json") if self.next_step else None,
            "assessment_result": assessment_result,
            "activity_result": self.followup.activity_result.model_dump(mode="json"),
        }

    def get_state(self) -> dict:
        payload = {
            "stage": self.stage.value,
            "student": self.initial.student.model_dump(mode="json"),
            "market": [item.model_dump(mode="json") for item in self.market],
        }
        if self.stage is not DemoStage.INITIAL:
            payload.update(
                evidence=[item.model_dump(mode="json") for item in self.evidence_t0],
                ability_profile=[item.model_dump(mode="json") for item in self.ability_t0],
                gaps=[item.model_dump(mode="json") for item in self.gaps_t0],
            )
        if self.stage in {DemoStage.PLANNED, DemoStage.ADVANCED}:
            payload["weekly_plan"] = self.plan_t0.model_dump(mode="json")
        if self.stage is DemoStage.ADVANCED:
            payload["comparison"] = self.get_comparison()
        return payload

    def _market_snapshot_version(self) -> str:
        return "+".join(sorted({item.snapshot_version for item in self.market}))

    def _require_stage(self, expected: DemoStage) -> None:
        if self.stage is not expected:
            raise InvalidTransition(
                f"Action requires stage '{expected.value}', current stage is '{self.stage.value}'."
            )
