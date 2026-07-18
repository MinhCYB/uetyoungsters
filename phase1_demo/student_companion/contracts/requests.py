"""Versioned request models for the public Student Companion facade."""

from __future__ import annotations

from pydantic import model_validator

from phase1_demo.student_companion.contracts.common import ContractMetadata, ContractModel
from phase1_demo.student_companion.domain import (
    AcademicRecord,
    ActivityResult,
    AssessmentAttempt,
    AssessmentType,
    SelfReport,
    StudentProfile,
    StudentSnapshot,
    TeacherObservation,
)


def _duplicates(values: list[str]) -> bool:
    return len(values) != len(set(values))


def _validate_student_ids(expected: str, values: list[str]) -> None:
    if any(value != expected for value in values):
        raise ValueError("all nested student_id values must match student.student_id")


class InitialAnalysisRequest(ContractModel):
    metadata: ContractMetadata
    student: StudentProfile
    academic_records: list[AcademicRecord]
    teacher_observations: list[TeacherObservation]
    assessment_attempts: list[AssessmentAttempt]
    self_report: SelfReport | None
    prior_activity_results: list[ActivityResult]

    @model_validator(mode="after")
    def validate_request_consistency(self) -> InitialAnalysisRequest:
        _validate_student_ids(
            self.student.student_id,
            [
                *(item.student_id for item in self.academic_records),
                *(item.student_id for item in self.teacher_observations),
                *(item.student_id for item in self.assessment_attempts),
                *(item.student_id for item in self.prior_activity_results),
                *([self.self_report.student_id] if self.self_report else []),
            ],
        )
        identifiers = {
            "academic_records": [item.record_id for item in self.academic_records],
            "teacher_observations": [
                item.observation_id for item in self.teacher_observations
            ],
            "assessment_attempts": [item.attempt_id for item in self.assessment_attempts],
            "prior_activity_results": [
                item.activity_result_id for item in self.prior_activity_results
            ],
        }
        for field_name, values in identifiers.items():
            if _duplicates(values):
                raise ValueError(f"{field_name} must not contain duplicate IDs")
        if not any(
            item.assessment_type in {AssessmentType.DIAGNOSTIC, AssessmentType.PRETEST}
            for item in self.assessment_attempts
        ):
            raise ValueError(
                "assessment_attempts requires at least one diagnostic or pretest"
            )
        return self


class PlanGenerationRequest(ContractModel):
    metadata: ContractMetadata
    student: StudentProfile
    snapshot: StudentSnapshot
    completed_activity_ids: list[str]

    @model_validator(mode="after")
    def validate_request_consistency(self) -> PlanGenerationRequest:
        if self.student.student_id != self.snapshot.student_id:
            raise ValueError("student.student_id must match snapshot.student_id")
        if _duplicates(self.completed_activity_ids):
            raise ValueError("completed_activity_ids must not contain duplicates")
        return self


class FollowupEvaluationRequest(ContractModel):
    metadata: ContractMetadata
    student: StudentProfile
    previous_snapshot: StudentSnapshot
    assessment_attempts: list[AssessmentAttempt]
    activity_results: list[ActivityResult]

    @model_validator(mode="after")
    def validate_request_consistency(self) -> FollowupEvaluationRequest:
        if self.student.student_id != self.previous_snapshot.student_id:
            raise ValueError("student.student_id must match previous_snapshot.student_id")
        _validate_student_ids(
            self.student.student_id,
            [
                *(item.student_id for item in self.assessment_attempts),
                *(item.student_id for item in self.activity_results),
            ],
        )
        attempt_ids = [item.attempt_id for item in self.assessment_attempts]
        result_ids = [item.activity_result_id for item in self.activity_results]
        if _duplicates(attempt_ids):
            raise ValueError("assessment_attempts must not contain duplicate attempt_id values")
        if _duplicates(result_ids):
            raise ValueError("activity_results must not contain duplicate activity_result_id values")
        has_posttest = any(
            item.assessment_type is AssessmentType.POSTTEST
            for item in self.assessment_attempts
        )
        if not has_posttest and not self.activity_results:
            raise ValueError("follow-up requires at least one posttest or activity result")
        return self

