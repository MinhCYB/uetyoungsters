"""Validated loaders for the synthetic demo inputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from phase1_demo.student_companion.domain import (
    AcademicRecord,
    ActivityResult,
    AssessmentAttempt,
    SelfReport,
    StudentProfile,
    TeacherObservation,
)


DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures"


@dataclass(frozen=True)
class InitialFixtures:
    student: StudentProfile
    academic_records: tuple[AcademicRecord, ...]
    teacher_observations: tuple[TeacherObservation, ...]
    pretest_attempt: AssessmentAttempt
    self_report: SelfReport


@dataclass(frozen=True)
class FollowupFixtures:
    posttest_attempt: AssessmentAttempt
    activity_result: ActivityResult


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_initial_fixtures(root: Path = DEFAULT_FIXTURE_ROOT) -> InitialFixtures:
    folder = root / "student_t0"
    fixtures = InitialFixtures(
        student=StudentProfile.model_validate(_read_json(folder / "student.json")),
        academic_records=tuple(
            AcademicRecord.model_validate(item)
            for item in _read_json(folder / "academic_records.json")
        ),
        teacher_observations=tuple(
            TeacherObservation.model_validate(item)
            for item in _read_json(folder / "teacher_observations.json")
        ),
        pretest_attempt=AssessmentAttempt.model_validate(
            _read_json(folder / "pretest_attempt.json")
        ),
        self_report=SelfReport.model_validate(_read_json(folder / "self_report.json")),
    )
    student_ids = {
        fixtures.student.student_id,
        fixtures.pretest_attempt.student_id,
        fixtures.self_report.student_id,
        *(item.student_id for item in fixtures.academic_records),
        *(item.student_id for item in fixtures.teacher_observations),
    }
    if len(student_ids) != 1:
        raise ValueError("T0 fixtures must reference exactly one student_id")
    return fixtures


def load_followup_fixtures(root: Path = DEFAULT_FIXTURE_ROOT) -> FollowupFixtures:
    folder = root / "student_t1"
    fixtures = FollowupFixtures(
        posttest_attempt=AssessmentAttempt.model_validate(
            _read_json(folder / "posttest_attempt.json")
        ),
        activity_result=ActivityResult.model_validate(
            _read_json(folder / "activity_result.json")
        ),
    )
    if fixtures.posttest_attempt.student_id != fixtures.activity_result.student_id:
        raise ValueError("T1 fixtures must reference exactly one student_id")
    return fixtures

