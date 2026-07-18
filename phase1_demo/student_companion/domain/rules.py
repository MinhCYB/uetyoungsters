"""Pure deterministic business rules for the Phase 1 vertical slice."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, datetime, time, timezone
from typing import Iterable

from phase1_demo.student_companion.config import (
    ABILITY_TREND_THRESHOLD,
    ACADEMIC_HIGH_PRIORITY_GAP,
    ACADEMIC_THRESHOLDS,
    ACTIVITY_CATALOG,
    ACTIVITY_VERSION,
    CAREER_ACTIVITY_BY_GROUP,
    CAREER_EXPLORATION_RULES,
    CONFIG_VERSION,
    ESTIMATE_VERSION,
    EVIDENCE_VERSION,
    GAP_VERSION,
    OUTCOME_THRESHOLDS,
    SOURCE_WEIGHTS,
    TEACHER_OBSERVATION_VALUES,
)
from phase1_demo.student_companion.domain.enums import (
    AbilityTrend,
    GapPriority,
    GapType,
    OutcomeStatus,
)
from phase1_demo.student_companion.domain.models import (
    AbilityEstimate,
    AcademicRecord,
    ActivityResult,
    AssessmentAttempt,
    Evidence,
    Gap,
    OutcomeEvaluation,
    PlanTask,
    SelfReport,
    StudentProfile,
    TeacherObservation,
    WeeklyPlan,
)


def stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _as_datetime(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _evidence(
    *,
    student_id: str,
    skill_id: str,
    source_type: str,
    raw_value: float,
    normalized_value: float,
    confidence: float,
    observed_at: datetime | date,
    source_reference: str,
) -> Evidence:
    return Evidence(
        evidence_id=stable_id("EVIDENCE", source_type, source_reference, skill_id),
        student_id=student_id,
        skill_id=skill_id,
        source_type=source_type,
        raw_value=raw_value,
        normalized_value=normalized_value,
        confidence=confidence,
        observed_at=_as_datetime(observed_at),
        source_reference=source_reference,
        evidence_version=EVIDENCE_VERSION,
    )


def normalize_academic_records(records: Iterable[AcademicRecord]) -> list[Evidence]:
    return _stable_evidence(
        _evidence(
            student_id=item.student_id,
            skill_id=item.topic_id,
            source_type="academic_record",
            raw_value=item.score,
            normalized_value=item.score / item.max_score,
            confidence=1.0,
            observed_at=item.observed_at,
            source_reference=item.record_id,
        )
        for item in records
    )


def normalize_teacher_observations(
    observations: Iterable[TeacherObservation],
) -> list[Evidence]:
    return _stable_evidence(
        _evidence(
            student_id=item.student_id,
            skill_id=item.skill_id,
            source_type="teacher_observation",
            raw_value=TEACHER_OBSERVATION_VALUES[item.observation_type.value][
                item.severity.value
            ],
            normalized_value=TEACHER_OBSERVATION_VALUES[item.observation_type.value][
                item.severity.value
            ],
            confidence=item.confidence,
            observed_at=item.observed_at,
            source_reference=item.observation_id,
        )
        for item in observations
    )


def normalize_assessment(attempt: AssessmentAttempt) -> list[Evidence]:
    return _stable_evidence(
        _evidence(
            student_id=attempt.student_id,
            skill_id=item.skill_id,
            source_type="assessment",
            raw_value=item.score,
            normalized_value=item.score / item.max_score,
            confidence=1.0,
            observed_at=attempt.completed_at,
            source_reference=attempt.attempt_id,
        )
        for item in attempt.skill_scores
    )


def normalize_self_report(report: SelfReport) -> list[Evidence]:
    return _stable_evidence(
        _evidence(
            student_id=report.student_id,
            skill_id=f"INTEREST_{item.career_group_id}",
            source_type="self_report",
            raw_value=item.interest_score,
            normalized_value=item.interest_score / item.max_score,
            confidence=1.0,
            observed_at=report.observed_at,
            source_reference=report.report_id,
        )
        for item in report.career_interests
    )


def normalize_activity_result(result: ActivityResult) -> list[Evidence]:
    if not result.completed or result.rubric_score is None or result.max_score is None:
        return []
    catalog_item = ACTIVITY_CATALOG.get(result.activity_id)
    if catalog_item is None or "rubric_skill_id" not in catalog_item:
        raise ValueError(f"unknown activity rubric mapping: {result.activity_id}")
    return [
        _evidence(
            student_id=result.student_id,
            skill_id=catalog_item["rubric_skill_id"],
            source_type="activity_result",
            raw_value=result.rubric_score,
            normalized_value=result.rubric_score / result.max_score,
            confidence=1.0,
            observed_at=result.completed_at,
            source_reference=result.activity_result_id,
        )
    ]


def _stable_evidence(items: Iterable[Evidence]) -> list[Evidence]:
    by_id: dict[str, Evidence] = {}
    for item in items:
        previous = by_id.get(item.evidence_id)
        if previous is not None and previous != item:
            raise ValueError(f"conflicting evidence with ID {item.evidence_id}")
        by_id[item.evidence_id] = item
    return sorted(by_id.values(), key=lambda item: (item.observed_at, item.evidence_id))


def merge_evidence(*groups: Iterable[Evidence]) -> list[Evidence]:
    return _stable_evidence(item for group in groups for item in group)


def build_ability_profile(
    evidence: Iterable[Evidence],
    previous: Iterable[AbilityEstimate] | None = None,
) -> list[AbilityEstimate]:
    grouped: dict[str, list[Evidence]] = defaultdict(list)
    for item in evidence:
        if not item.skill_id.startswith("INTEREST_"):
            grouped[item.skill_id].append(item)
    previous_by_skill = {item.skill_id: item for item in previous or []}
    result: list[AbilityEstimate] = []
    for skill_id, items in sorted(grouped.items()):
        weighted_items = [
            (item, SOURCE_WEIGHTS[item.source_type.value] * item.confidence)
            for item in items
        ]
        denominator = sum(weight for _, weight in weighted_items)
        estimated_level = sum(
            item.normalized_value * weight for item, weight in weighted_items
        ) / denominator
        confidence = min(1.0, denominator / len(weighted_items))
        trend = AbilityTrend.UNKNOWN
        if skill_id in previous_by_skill:
            delta = estimated_level - previous_by_skill[skill_id].estimated_level
            if delta >= ABILITY_TREND_THRESHOLD:
                trend = AbilityTrend.IMPROVING
            elif delta <= -ABILITY_TREND_THRESHOLD:
                trend = AbilityTrend.DECLINING
            else:
                trend = AbilityTrend.STABLE
        result.append(
            AbilityEstimate(
                skill_id=skill_id,
                estimated_level=round(estimated_level, 6),
                confidence=round(confidence, 6),
                trend=trend,
                evidence_ids=sorted(item.evidence_id for item in items),
                estimate_version=ESTIMATE_VERSION,
            )
        )
    return result


def build_gaps(
    student: StudentProfile,
    ability_profile: Iterable[AbilityEstimate],
    evidence: Iterable[Evidence],
    activity_results: Iterable[ActivityResult] = (),
) -> list[Gap]:
    evidence_list = list(evidence)
    ability_by_skill = {item.skill_id: item for item in ability_profile}
    gaps: list[Gap] = []
    for skill_id, expected in sorted(ACADEMIC_THRESHOLDS.items()):
        estimate = ability_by_skill.get(skill_id)
        if estimate is None or estimate.estimated_level >= expected:
            continue
        size = round(expected - estimate.estimated_level, 6)
        priority = GapPriority.HIGH if size >= ACADEMIC_HIGH_PRIORITY_GAP else GapPriority.MEDIUM
        evidence_ids = estimate.evidence_ids
        gaps.append(
            Gap(
                gap_id=stable_id("GAP", "academic", skill_id),
                gap_type=GapType.ACADEMIC,
                skill_id=skill_id,
                career_group_ids=[],
                current_level=estimate.estimated_level,
                expected_level=expected,
                gap_size=size,
                priority=priority,
                reason=f"Mức hiện tại dưới ngưỡng; dựa trên evidence: {', '.join(evidence_ids)}.",
                evidence_ids=evidence_ids,
                gap_version=GAP_VERSION,
            )
        )

    completed_groups = _completed_exploration_groups(activity_results)
    for career_group_id in student.career_interest_ids:
        if career_group_id in completed_groups:
            continue
        evidence_ids = sorted(
            item.evidence_id
            for item in evidence_list
            if item.skill_id == f"INTEREST_{career_group_id}"
        )
        gaps.append(
            Gap(
                gap_id=stable_id("GAP", "exploration", career_group_id),
                gap_type=GapType.EXPLORATION,
                skill_id=None,
                career_group_ids=[career_group_id],
                current_level=None,
                expected_level=None,
                gap_size=None,
                priority=GapPriority.HIGH,
                reason=(
                    "Chưa có micro-experience đạt chuẩn; dựa trên evidence: "
                    f"{', '.join(evidence_ids) or 'không có activity evidence'}."
                ),
                evidence_ids=evidence_ids,
                gap_version=GAP_VERSION,
            )
        )

    if len(student.career_interest_ids) >= 2 and not all(
        item in completed_groups for item in student.career_interest_ids
    ):
        decision_evidence = sorted(
            item.evidence_id
            for item in evidence_list
            if item.skill_id.startswith("INTEREST_")
        )
        gaps.append(
            Gap(
                gap_id=stable_id("GAP", "decision", *student.career_interest_ids),
                gap_type=GapType.DECISION,
                skill_id=None,
                career_group_ids=list(student.career_interest_ids),
                current_level=None,
                expected_level=None,
                gap_size=None,
                priority=GapPriority.MEDIUM,
                reason=(
                    "Chưa đủ trải nghiệm để so sánh các hướng; dựa trên evidence: "
                    f"{', '.join(decision_evidence)}."
                ),
                evidence_ids=decision_evidence,
                gap_version=GAP_VERSION,
            )
        )
    return sorted(gaps, key=lambda item: (item.gap_type.value, item.gap_id))


def _completed_exploration_groups(
    results: Iterable[ActivityResult],
) -> set[str]:
    completed: set[str] = set()
    for item in results:
        if (
            item.completed
            and item.rubric_score is not None
            and item.max_score is not None
            and item.rubric_score / item.max_score
            >= CAREER_EXPLORATION_RULES["minimum_rubric_level"]
        ):
            completed.add(item.career_group_id)
    return completed


def generate_weekly_plan(
    student: StudentProfile,
    gaps: Iterable[Gap],
    generated_at: datetime,
    plan_id: str,
    completed_activity_ids: Iterable[str] = (),
) -> WeeklyPlan:
    gap_list = list(gaps)
    completed = set(completed_activity_ids)
    selected: list[tuple[str, Gap]] = []
    remaining = student.weekly_available_minutes

    academic_gaps = sorted(
        (
            item
            for item in gap_list
            if item.gap_type is GapType.ACADEMIC and item.priority is GapPriority.HIGH
        ),
        key=lambda item: (-float(item.gap_size or 0), item.gap_id),
    )
    for gap in academic_gaps:
        activity_id = "ACTIVITY_TRIG_PRACTICE" if gap.skill_id == "SKILL_TRIG_TRANSFORMATION" else None
        if activity_id and activity_id not in completed:
            minutes = ACTIVITY_CATALOG[activity_id]["estimated_minutes"]
            if minutes <= remaining:
                selected.append((activity_id, gap))
                remaining -= minutes
                break

    if not student.exam_week:
        exploration_by_group = {
            item.career_group_ids[0]: item
            for item in gap_list
            if item.gap_type is GapType.EXPLORATION
        }
        for career_group_id in student.career_interest_ids:
            gap = exploration_by_group.get(career_group_id)
            activity_id = CAREER_ACTIVITY_BY_GROUP.get(career_group_id)
            if gap is None or activity_id is None or activity_id in completed:
                continue
            minutes = ACTIVITY_CATALOG[activity_id]["estimated_minutes"]
            if minutes <= remaining:
                selected.append((activity_id, gap))
                remaining -= minutes
            break

    tasks = [
        PlanTask(
            task_id=stable_id("TASK", plan_id, activity_id),
            task_type=ACTIVITY_CATALOG[activity_id]["task_type"],
            title=ACTIVITY_CATALOG[activity_id]["title"],
            skill_id=ACTIVITY_CATALOG[activity_id]["skill_id"],
            career_group_id=ACTIVITY_CATALOG[activity_id]["career_group_id"],
            estimated_minutes=ACTIVITY_CATALOG[activity_id]["estimated_minutes"],
            reason=gap.reason,
            evidence_ids=gap.evidence_ids,
            activity_version=ACTIVITY_VERSION,
        )
        for activity_id, gap in selected
    ]
    return WeeklyPlan(
        plan_id=plan_id,
        student_id=student.student_id,
        weekly_budget_minutes=student.weekly_available_minutes,
        total_planned_minutes=sum(item.estimated_minutes for item in tasks),
        tasks=tasks,
        generated_at=generated_at,
        rule_version=CONFIG_VERSION,
    )


def outcome_status(delta: float) -> OutcomeStatus:
    if delta <= OUTCOME_THRESHOLDS["regression"]:
        return OutcomeStatus.REGRESSION
    if delta < OUTCOME_THRESHOLDS["partial_improvement"]:
        return OutcomeStatus.NO_MEANINGFUL_CHANGE
    if delta < OUTCOME_THRESHOLDS["meaningful_improvement"]:
        return OutcomeStatus.PARTIAL_IMPROVEMENT
    return OutcomeStatus.MEANINGFUL_IMPROVEMENT


def evaluate_assessment_outcomes(
    before: AssessmentAttempt,
    after: AssessmentAttempt,
    before_evidence: Iterable[Evidence],
    after_evidence: Iterable[Evidence],
) -> list[OutcomeEvaluation]:
    before_scores = {item.skill_id: item.score / item.max_score for item in before.skill_scores}
    before_ids = {item.skill_id: item.evidence_id for item in before_evidence}
    after_ids = {item.skill_id: item.evidence_id for item in after_evidence}
    result: list[OutcomeEvaluation] = []
    for item in sorted(after.skill_scores, key=lambda score: score.skill_id):
        if item.skill_id not in before_scores:
            continue
        before_value = before_scores[item.skill_id]
        after_value = item.score / item.max_score
        delta = round(after_value - before_value, 10)
        result.append(
            OutcomeEvaluation(
                evaluation_id=stable_id("OUTCOME", before.attempt_id, after.attempt_id, item.skill_id),
                student_id=after.student_id,
                metric_type=item.skill_id,
                before_value=before_value,
                after_value=after_value,
                delta=delta,
                status=outcome_status(delta),
                evidence_ids=sorted([before_ids[item.skill_id], after_ids[item.skill_id]]),
                rule_version=CONFIG_VERSION,
            )
        )
    return result


def evaluate_interest_outcome(
    activity: ActivityResult,
    activity_evidence: Iterable[Evidence],
) -> OutcomeEvaluation:
    before_value = activity.interest_before / activity.interest_max_score
    after_value = activity.interest_after / activity.interest_max_score
    delta = round(after_value - before_value, 10)
    return OutcomeEvaluation(
        evaluation_id=stable_id("OUTCOME", activity.activity_result_id, "interest"),
        student_id=activity.student_id,
        metric_type=f"INTEREST_{activity.career_group_id}",
        before_value=before_value,
        after_value=after_value,
        delta=delta,
        status=outcome_status(delta),
        evidence_ids=sorted(item.evidence_id for item in activity_evidence),
        rule_version=CONFIG_VERSION,
    )


def select_next_step(
    student: StudentProfile,
    gaps: Iterable[Gap],
    completed_activity_ids: Iterable[str],
) -> PlanTask | None:
    completed = set(completed_activity_ids)
    gap_by_group = {
        item.career_group_ids[0]: item
        for item in gaps
        if item.gap_type is GapType.EXPLORATION
    }
    for career_group_id in student.career_interest_ids:
        activity_id = CAREER_ACTIVITY_BY_GROUP.get(career_group_id)
        gap = gap_by_group.get(career_group_id)
        if activity_id is None or activity_id in completed or gap is None:
            continue
        catalog = ACTIVITY_CATALOG[activity_id]
        return PlanTask(
            task_id=stable_id("TASK", "next-step", activity_id),
            task_type=catalog["task_type"],
            title=catalog["title"],
            skill_id=catalog["skill_id"],
            career_group_id=catalog["career_group_id"],
            estimated_minutes=catalog["estimated_minutes"],
            reason=gap.reason,
            evidence_ids=gap.evidence_ids,
            activity_version=ACTIVITY_VERSION,
        )
    return None
