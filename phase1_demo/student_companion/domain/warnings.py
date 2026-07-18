"""Pure deterministic warning rules for Student Companion Engine V1."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from phase1_demo.student_companion.config import (
    CAREER_ACTIVITY_BY_GROUP,
    CONFIDENCE_POLICY,
)
from phase1_demo.student_companion.contracts.common import ContractWarning
from phase1_demo.student_companion.domain.enums import AssessmentType
from phase1_demo.student_companion.domain.models import (
    AbilityEstimate,
    AssessmentAttempt,
    Evidence,
    MarketCareerGroup,
)


def _warning(code: str, message: str, field: str | None) -> ContractWarning:
    return ContractWarning(
        warning_code=code,
        message=message,
        affected_field=field,
    )


def normalize_warnings(
    warnings: Iterable[ContractWarning],
) -> list[ContractWarning]:
    """Deduplicate by code/field and return a stable order."""

    unique: dict[tuple[str, str], ContractWarning] = {}
    for item in warnings:
        key = (item.warning_code, item.affected_field or "")
        unique.setdefault(key, item)
    return sorted(
        unique.values(),
        key=lambda item: (item.warning_code, item.affected_field or "", item.message),
    )


def evidence_warnings(
    evidence: Iterable[Evidence],
    ability_profile: Iterable[AbilityEstimate],
) -> list[ContractWarning]:
    grouped: dict[str, list[Evidence]] = defaultdict(list)
    for item in evidence:
        if not item.skill_id.startswith("INTEREST_"):
            grouped[item.skill_id].append(item)

    warnings: list[ContractWarning] = []
    for estimate in sorted(ability_profile, key=lambda item: item.skill_id):
        items = grouped.get(estimate.skill_id, [])
        field = f"ability_profile.{estimate.skill_id}"
        if len(items) < CONFIDENCE_POLICY["minimum_evidence_count"]:
            warnings.append(
                _warning(
                    "insufficient_evidence",
                    "This ability estimate is based on limited evidence.",
                    field,
                )
            )
        if items:
            spread = max(item.normalized_value for item in items) - min(
                item.normalized_value for item in items
            )
            if spread > CONFIDENCE_POLICY["conflict_threshold"]:
                warnings.append(
                    _warning(
                        "conflicting_evidence",
                        "Evidence sources differ substantially for this ability.",
                        field,
                    )
                )
        if estimate.confidence < CONFIDENCE_POLICY["low_confidence_threshold"]:
            warnings.append(
                _warning(
                    "low_confidence_estimate",
                    "This estimate has low confidence and should not support a strong conclusion.",
                    field,
                )
            )
    return normalize_warnings(warnings)


def initial_warnings(
    request,
    market_context: Iterable[MarketCareerGroup],
    evidence: Iterable[Evidence],
    ability_profile: Iterable[AbilityEstimate],
) -> list[ContractWarning]:
    warnings: list[ContractWarning] = []
    optional_fields = (
        ("academic_records", request.academic_records),
        ("teacher_observations", request.teacher_observations),
        ("self_report", request.self_report),
    )
    for field_name, value in optional_fields:
        if not value:
            warnings.append(
                _warning(
                    "optional_data_missing",
                    f"Optional input '{field_name}' was not provided.",
                    field_name,
                )
            )

    evidence_list = list(evidence)
    if len(evidence_list) < 2:
        warnings.append(
            _warning(
                "insufficient_evidence",
                "Ability estimates are based on fewer than two evidence items.",
                "ability_profile",
            )
        )
    warnings.extend(evidence_warnings(evidence_list, ability_profile))

    market_items = list(market_context)
    returned_groups = {item.career_group_id for item in market_items}
    known_activity_groups = set(CAREER_ACTIVITY_BY_GROUP)
    for index, group_id in enumerate(request.student.career_interest_ids):
        if group_id not in returned_groups or group_id not in known_activity_groups:
            warnings.append(
                _warning(
                    "unknown_career_group",
                    "A career interest is not recognized by the available market context or activity catalog.",
                    f"student.career_interest_ids.{index}",
                )
            )
    for item in market_items:
        if item.sample_size < 5:
            warnings.append(
                _warning(
                    "small_market_sample",
                    f"Market sample for {item.career_group_id} is below 5.",
                    "market_context",
                )
            )
    return normalize_warnings(warnings)


def followup_warnings(request) -> list[ContractWarning]:
    baselines = [
        item
        for item in request.assessment_attempts
        if item.assessment_type in {AssessmentType.DIAGNOSTIC, AssessmentType.PRETEST}
    ]
    posttests = [
        item
        for item in request.assessment_attempts
        if item.assessment_type is AssessmentType.POSTTEST
    ]
    warnings: list[ContractWarning] = []
    for index, posttest in enumerate(posttests):
        candidates = [
            item
            for item in baselines
            if item.assessment_id == posttest.assessment_id
            and item.completed_at <= posttest.completed_at
        ]
        if not candidates:
            warnings.append(
                _warning(
                    "baseline_not_found",
                    "No comparable baseline was provided for a posttest.",
                    f"assessment_attempts.posttest.{index}",
                )
            )
            continue
        baseline = sorted(candidates, key=lambda item: (item.completed_at, item.attempt_id))[-1]
        before_skills = {item.skill_id for item in baseline.skill_scores}
        after_skills = {item.skill_id for item in posttest.skill_scores}
        if not before_skills.intersection(after_skills):
            warnings.append(
                _warning(
                    "assessment_scale_mismatch",
                    "The baseline and posttest do not contain a comparable skill score.",
                    f"assessment_attempts.posttest.{index}.skill_scores",
                )
            )
    return normalize_warnings(warnings)


def stale_profile_version_warning(
    current_version: str | None,
    expected_version: str | None,
) -> list[ContractWarning]:
    if not current_version or not expected_version or current_version == expected_version:
        return []
    return [
        _warning(
            "stale_profile_version",
            "The supplied student profile version differs from the expected version.",
            "student.schema_version",
        )
    ]


def scales_are_comparable(before: AssessmentAttempt, after: AssessmentAttempt) -> bool:
    """Valid positive scales compare by normalized score, regardless of max value."""

    before_skills = {item.skill_id for item in before.skill_scores}
    after_skills = {item.skill_id for item in after.skill_scores}
    return bool(before_skills.intersection(after_skills))
