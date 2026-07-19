from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from phase1_demo.student_companion.domain import (
    AbilityEstimate,
    AcademicRecord,
    ActivityResult,
    AssessmentAttempt,
    CareerInterestRating,
    Evidence,
    Gap,
    MarketCareerGroup,
    OutcomeEvaluation,
    PlanTask,
    SelfReport,
    SkillScore,
    StudentProfile,
    StudentSnapshot,
    TeacherObservation,
    WeeklyPlan,
)


NOW = datetime(2026, 7, 18, 9, 0, tzinfo=timezone.utc)


def student_profile_data() -> dict:
    return {
        "student_id": "student-001",
        "display_name": "Minh Anh",
        "grade_level": 11,
        "weekly_available_minutes": 45,
        "career_interest_ids": ["career-data-ai", "career-economics"],
        "career_clarity": "exploring",
        "exam_week": False,
        "schema_version": "1.0.0",
    }


def academic_record_data() -> dict:
    return {
        "record_id": "record-001",
        "student_id": "student-001",
        "subject_id": "math",
        "topic_id": "trigonometry",
        "score": 4.5,
        "max_score": 10.0,
        "observed_at": NOW,
        "source": "school-record",
        "schema_version": "1.0.0",
    }


def teacher_observation_data() -> dict:
    return {
        "observation_id": "observation-001",
        "student_id": "student-001",
        "skill_id": "skill-trigonometry",
        "observation_type": "weakness",
        "severity": "high",
        "confidence": 0.9,
        "note": "Needs more practice applying identities.",
        "observed_at": NOW,
        "schema_version": "1.0.0",
    }


def activity_result_data() -> dict:
    return {
        "activity_result_id": "result-001",
        "activity_id": "activity-001",
        "student_id": "student-001",
        "career_group_id": "career-data-ai",
        "completed": True,
        "rubric_score": 8.0,
        "max_score": 10.0,
        "interest_before": 7.0,
        "interest_after": 8.0,
        "interest_max_score": 10.0,
        "preferred_part": "Finding patterns",
        "completed_at": NOW,
        "activity_version": "1.0.0",
        "schema_version": "1.0.0",
    }


def evidence_data() -> dict:
    return {
        "evidence_id": "evidence-001",
        "student_id": "student-001",
        "skill_id": "skill-trigonometry",
        "source_type": "assessment",
        "raw_value": 4.5,
        "normalized_value": 0.45,
        "confidence": 0.95,
        "observed_at": NOW,
        "source_reference": "attempt-001",
        "evidence_version": "1.0.0",
    }


def academic_gap_data() -> dict:
    return {
        "gap_id": "gap-001",
        "gap_type": "academic",
        "skill_id": "skill-trigonometry",
        "career_group_ids": [],
        "current_level": 0.45,
        "expected_level": 0.7,
        "gap_size": 0.25,
        "priority": "high",
        "reason": "Current evidence is below the expected foundation level.",
        "evidence_ids": ["evidence-001"],
        "gap_version": "1.0.0",
    }


def plan_task_data() -> dict:
    return {
        "task_id": "task-001",
        "task_type": "academic_practice",
        "title": "Practice trigonometry",
        "skill_id": "skill-trigonometry",
        "career_group_id": None,
        "estimated_minutes": 20,
        "reason": "Address the highest academic gap.",
        "evidence_ids": ["evidence-001"],
        "activity_version": "1.0.0",
    }


def weekly_plan_data() -> dict:
    return {
        "plan_id": "plan-001",
        "student_id": "student-001",
        "weekly_budget_minutes": 45,
        "total_planned_minutes": 20,
        "tasks": [plan_task_data()],
        "generated_at": NOW,
        "rule_version": "1.0.0",
    }


def outcome_data() -> dict:
    return {
        "evaluation_id": "evaluation-001",
        "student_id": "student-001",
        "metric_type": "skill-trigonometry",
        "before_value": 0.45,
        "after_value": 0.65,
        "delta": 0.2,
        "status": "meaningful_improvement",
        "evidence_ids": ["evidence-001", "evidence-002"],
        "rule_version": "1.0.0",
    }


def snapshot_data() -> dict:
    return {
        "snapshot_id": "snapshot-002",
        "previous_snapshot_id": "snapshot-001",
        "student_id": "student-001",
        "created_at": NOW,
        "ability_profile": [
            {
                "skill_id": "skill-trigonometry",
                "estimated_level": 0.65,
                "confidence": 0.9,
                "trend": "improving",
                "evidence_ids": ["evidence-001", "evidence-002"],
                "estimate_version": "1.0.0",
            }
        ],
        "gaps": [academic_gap_data()],
        "active_plan": weekly_plan_data(),
        "outcomes": [outcome_data()],
        "market_snapshot_version": "market-2026-07-18",
        "pipeline_version": "1.0.0",
    }


def test_student_profile_is_valid() -> None:
    profile = StudentProfile.model_validate(student_profile_data())
    assert profile.grade_level == 11
    assert profile.career_clarity.value == "exploring"


@pytest.mark.parametrize("grade_level", [9, 13])
def test_student_profile_rejects_grade_outside_high_school(grade_level: int) -> None:
    data = student_profile_data()
    data["grade_level"] = grade_level
    with pytest.raises(ValidationError):
        StudentProfile.model_validate(data)


def test_student_profile_rejects_zero_weekly_minutes() -> None:
    data = student_profile_data()
    data["weekly_available_minutes"] = 0
    with pytest.raises(ValidationError):
        StudentProfile.model_validate(data)


def test_student_profile_rejects_duplicate_career_interests() -> None:
    data = student_profile_data()
    data["career_interest_ids"] = ["career-data-ai", "career-data-ai"]
    with pytest.raises(ValidationError):
        StudentProfile.model_validate(data)


def test_student_profile_rejects_blank_identity_fields() -> None:
    data = student_profile_data()
    data["student_id"] = "  "
    with pytest.raises(ValidationError):
        StudentProfile.model_validate(data)


def test_academic_record_rejects_score_above_maximum() -> None:
    data = academic_record_data()
    data["score"] = 10.1
    with pytest.raises(ValidationError):
        AcademicRecord.model_validate(data)


def test_academic_record_rejects_non_positive_maximum() -> None:
    data = academic_record_data()
    data["max_score"] = 0
    with pytest.raises(ValidationError):
        AcademicRecord.model_validate(data)


def test_teacher_observation_rejects_confidence_above_one() -> None:
    data = teacher_observation_data()
    data["confidence"] = 1.01
    with pytest.raises(ValidationError):
        TeacherObservation.model_validate(data)


def test_teacher_observation_rejects_blank_note() -> None:
    data = teacher_observation_data()
    data["note"] = "  "
    with pytest.raises(ValidationError):
        TeacherObservation.model_validate(data)


def test_skill_score_rejects_score_above_maximum() -> None:
    with pytest.raises(ValidationError):
        SkillScore(skill_id="skill-1", score=6, max_score=5)


def test_assessment_attempt_rejects_duplicate_skill_id() -> None:
    score = {"skill_id": "skill-1", "score": 4, "max_score": 5}
    with pytest.raises(ValidationError):
        AssessmentAttempt(
            attempt_id="attempt-1",
            student_id="student-001",
            assessment_id="assessment-1",
            assessment_type="pretest",
            skill_scores=[score, score],
            completed_at=NOW,
            assessment_version="1.0.0",
            schema_version="1.0.0",
        )


def test_assessment_attempt_rejects_empty_skill_scores() -> None:
    with pytest.raises(ValidationError):
        AssessmentAttempt(
            attempt_id="attempt-1",
            student_id="student-001",
            assessment_id="assessment-1",
            assessment_type="pretest",
            skill_scores=[],
            completed_at=NOW,
            assessment_version="1.0.0",
            schema_version="1.0.0",
        )


def test_career_interest_rating_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        CareerInterestRating(career_group_id="career-1", interest_score=11, max_score=10)


def test_self_report_rejects_duplicate_career_interest() -> None:
    rating = {"career_group_id": "career-1", "interest_score": 7, "max_score": 10}
    with pytest.raises(ValidationError):
        SelfReport(
            report_id="report-1",
            student_id="student-001",
            career_interests=[rating, rating],
            preferred_task_types=["analysis"],
            stated_strength_skill_ids=["skill-1"],
            stated_weakness_skill_ids=["skill-2"],
            note=None,
            observed_at=NOW,
            schema_version="1.0.0",
        )


def test_self_report_rejects_duplicate_skill_ids() -> None:
    with pytest.raises(ValidationError):
        SelfReport(
            report_id="report-1",
            student_id="student-001",
            career_interests=[],
            preferred_task_types=[],
            stated_strength_skill_ids=["skill-1", "skill-1"],
            stated_weakness_skill_ids=[],
            note=None,
            observed_at=NOW,
            schema_version="1.0.0",
        )


def test_activity_result_rejects_completed_without_rubric_score() -> None:
    data = activity_result_data()
    data["rubric_score"] = None
    with pytest.raises(ValidationError):
        ActivityResult.model_validate(data)


def test_activity_result_rejects_interest_above_maximum() -> None:
    data = activity_result_data()
    data["interest_after"] = 11
    with pytest.raises(ValidationError):
        ActivityResult.model_validate(data)


def test_activity_result_rejects_rubric_score_above_maximum() -> None:
    data = activity_result_data()
    data["rubric_score"] = 11
    with pytest.raises(ValidationError):
        ActivityResult.model_validate(data)


def test_evidence_rejects_normalized_value_outside_unit_interval() -> None:
    data = evidence_data()
    data["normalized_value"] = 1.1
    with pytest.raises(ValidationError):
        Evidence.model_validate(data)


def test_ability_estimate_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(ValidationError):
        AbilityEstimate(
            skill_id="skill-1",
            estimated_level=0.5,
            confidence=0.8,
            trend="stable",
            evidence_ids=["evidence-1", "evidence-1"],
            estimate_version="1.0.0",
        )


def test_academic_gap_rejects_missing_skill_id() -> None:
    data = academic_gap_data()
    data["skill_id"] = None
    with pytest.raises(ValidationError):
        Gap.model_validate(data)


def test_academic_gap_rejects_missing_levels() -> None:
    data = academic_gap_data()
    data["gap_size"] = None
    with pytest.raises(ValidationError):
        Gap.model_validate(data)


def test_exploration_gap_rejects_multiple_career_groups() -> None:
    data = academic_gap_data()
    data.update(
        gap_type="exploration",
        skill_id=None,
        career_group_ids=["career-1", "career-2"],
        current_level=None,
        expected_level=None,
        gap_size=None,
    )
    with pytest.raises(ValidationError):
        Gap.model_validate(data)


def test_decision_gap_rejects_only_one_career_group() -> None:
    data = academic_gap_data()
    data.update(
        gap_type="decision",
        skill_id=None,
        career_group_ids=["career-1"],
        current_level=None,
        expected_level=None,
        gap_size=None,
    )
    with pytest.raises(ValidationError):
        Gap.model_validate(data)


def test_market_career_group_rejects_duplicate_foundation_skills() -> None:
    with pytest.raises(ValidationError):
        MarketCareerGroup(
            career_group_id="career-1",
            display_name="Data and AI",
            market_signal="Growing foundation skill demand",
            sample_size=10,
            foundation_skill_ids=["skill-1", "skill-1"],
            snapshot_version="snapshot-1",
            taxonomy_version="0.4.0",
            data_mode="pipeline_export",
            source_output_files=["career_skill_matrix.parquet"],
        )


def test_market_career_group_rejects_unknown_data_mode() -> None:
    with pytest.raises(ValidationError):
        MarketCareerGroup(
            career_group_id="career-1",
            display_name="Data and AI",
            market_signal="Signal",
            sample_size=0,
            foundation_skill_ids=[],
            snapshot_version="snapshot-1",
            taxonomy_version=None,
            data_mode="live_api",
            source_output_files=[],
        )


def test_plan_task_requires_skill_for_academic_practice() -> None:
    data = plan_task_data()
    data["skill_id"] = None
    with pytest.raises(ValidationError):
        PlanTask.model_validate(data)


def test_plan_task_requires_career_for_micro_experience() -> None:
    data = plan_task_data()
    data.update(task_type="career_micro_experience", skill_id=None, career_group_id=None)
    with pytest.raises(ValidationError):
        PlanTask.model_validate(data)


def test_weekly_plan_rejects_total_above_budget() -> None:
    data = weekly_plan_data()
    data["weekly_budget_minutes"] = 15
    with pytest.raises(ValidationError):
        WeeklyPlan.model_validate(data)


def test_weekly_plan_rejects_total_not_equal_to_task_sum() -> None:
    data = weekly_plan_data()
    data["total_planned_minutes"] = 19
    with pytest.raises(ValidationError):
        WeeklyPlan.model_validate(data)


def test_weekly_plan_rejects_duplicate_task_ids() -> None:
    data = weekly_plan_data()
    data["tasks"] = [plan_task_data(), plan_task_data()]
    data["total_planned_minutes"] = 40
    with pytest.raises(ValidationError):
        WeeklyPlan.model_validate(data)


def test_outcome_evaluation_rejects_incorrect_delta() -> None:
    data = outcome_data()
    data["delta"] = 0.19
    with pytest.raises(ValidationError):
        OutcomeEvaluation.model_validate(data)


def test_student_snapshot_rejects_duplicate_ability_skill_id() -> None:
    data = snapshot_data()
    estimate = data["ability_profile"][0]
    data["ability_profile"] = [estimate, estimate]
    with pytest.raises(ValidationError):
        StudentSnapshot.model_validate(data)


def test_student_snapshot_rejects_duplicate_gap_id() -> None:
    data = snapshot_data()
    data["gaps"] = [academic_gap_data(), academic_gap_data()]
    with pytest.raises(ValidationError):
        StudentSnapshot.model_validate(data)


def test_student_snapshot_rejects_self_referencing_previous_snapshot() -> None:
    data = snapshot_data()
    data["previous_snapshot_id"] = data["snapshot_id"]
    with pytest.raises(ValidationError):
        StudentSnapshot.model_validate(data)


def test_student_profile_json_round_trip() -> None:
    original = StudentProfile.model_validate(student_profile_data())
    restored = StudentProfile.model_validate_json(original.model_dump_json())
    assert restored == original


def test_student_snapshot_json_round_trip() -> None:
    original = StudentSnapshot.model_validate(snapshot_data())
    restored = StudentSnapshot.model_validate_json(original.model_dump_json())
    assert restored == original


def test_same_student_input_serializes_to_identical_json() -> None:
    first = StudentProfile.model_validate(student_profile_data()).model_dump_json()
    second = StudentProfile.model_validate(student_profile_data()).model_dump_json()
    assert first == second

