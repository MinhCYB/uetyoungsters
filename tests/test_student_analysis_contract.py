import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-api"))

from modules.candidate.analysis_contracts import (  # noqa: E402
    StudentProfilePayload,
    to_followup_evaluation_request,
    to_initial_analysis_request,
)


def fixture(name):
    return json.loads((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))


def test_initial_profile_maps_to_initial_request():
    payload = fixture("student_profile_initial.json")
    profile = StudentProfilePayload.model_validate(payload)
    request = to_initial_analysis_request(payload, request_id="iar_uet_0001", requested_at=datetime.now(timezone.utc))
    assert profile.self_report is None
    assert {a.purpose.value for a in request.profile.assessment_attempts} == {"diagnostic", "pretest"}
    assert all(score.skill_id for attempt in request.profile.assessment_attempts for score in attempt.skill_scores)


def test_week3_profile_maps_to_followup_request():
    payload = fixture("student_profile_week3.json")
    request = to_followup_evaluation_request(
        payload,
        request_id="fer_uet_0001",
        requested_at=datetime.now(timezone.utc),
        baseline_analysis_id="analysis_uet_0001",
        window_started_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
        window_ended_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )
    assert request.profile.profile_version == 2
    assert any(a.purpose.value == "posttest" for a in request.profile.assessment_attempts)
    assert request.profile.activity_results[0].skill_id == "skill_data_literacy"


def test_followup_without_posttest_is_rejected():
    payload = fixture("student_profile_initial.json")
    with pytest.raises(ValidationError, match="posttest"):
        to_followup_evaluation_request(
            payload,
            request_id="fer_uet_0002",
            requested_at=datetime.now(timezone.utc),
            baseline_analysis_id="analysis_uet_0001",
            window_started_at=datetime(2026, 7, 19, tzinfo=timezone.utc),
            window_ended_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
        )


def test_child_student_id_mismatch_is_rejected():
    payload = fixture("student_profile_initial.json")
    payload["academic_records"][0]["student_id"] = "stu_other_0001"
    with pytest.raises(ValidationError, match="student_id"):
        StudentProfilePayload.model_validate(payload)
