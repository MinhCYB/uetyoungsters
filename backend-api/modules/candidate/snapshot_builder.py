"""Build versioned AI payloads from normalized application data."""
import re
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.assessment.models import Assessment
from modules.auth.models import User

from .analysis_contracts import (AcademicRecord as AcademicRecordContract,
                                 AssessmentAttempt, AssessmentPurpose,
                                 InitialAnalysisRequest, Student,
                                 StudentProfilePayload)
from .models import AcademicRecord, CandidateProfile


class SnapshotBuildError(ValueError):
    pass


def _token(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.casefold().replace("-", "_")).strip("_")


def _external(prefix: str, value: str) -> str:
    return f"{prefix}_{_token(value)}"


def build_student_snapshot(db: Session, user: User) -> StudentProfilePayload:
    profile = db.query(CandidateProfile).filter_by(user_id=user.id).one_or_none()
    if not profile:
        raise SnapshotBuildError("Người dùng chưa có candidate profile")
    if profile.profile_type not in {"HIGH_SCHOOL", "UNIVERSITY"}:
        raise SnapshotBuildError("Contract AI 1.0.0 hiện chỉ hỗ trợ học sinh và sinh viên")
    if not profile.tenant_id or not profile.class_id:
        raise SnapshotBuildError("Hồ sơ học sinh/sinh viên chưa được gắn với trường và lớp")

    student_id = _external("stu", user.id)
    academic_rows = db.query(AcademicRecord).filter_by(candidate_profile_id=profile.id).order_by(AcademicRecord.created_at).all()
    assessments = db.query(Assessment).filter_by(user_id=user.id).order_by(Assessment.created_at).all()

    return StudentProfilePayload(
        schema_version="1.0.0",
        profile_version=profile.version,
        generated_at=datetime.now(timezone.utc),
        student=Student(
            student_id=student_id,
            tenant_id=_external("ten", profile.tenant_id),
            class_id=_external("cls", profile.class_id),
            student_code=profile.student_code or user.id[:8],
            display_name=user.display_name or user.email.split("@", 1)[0],
            profile_type=profile.profile_type,
            grade_level=profile.grade,
            date_of_birth=None,
        ),
        academic_records=[
            AcademicRecordContract(
                record_id=_external("acr", row.id),
                student_id=student_id,
                subject_id=_external("subject", row.subject),
                subject_name=row.subject,
                period=row.semester,
                score=row.score,
                score_scale=10,
                recorded_at=row.updated_at,
                source="user_entry",
            )
            for row in academic_rows
        ],
        teacher_observations=[],
        assessment_attempts=[
            AssessmentAttempt(
                attempt_id=_external("att", row.id),
                student_id=student_id,
                assessment_id=row.id,
                purpose=AssessmentPurpose.DIAGNOSTIC,
                started_at=row.created_at,
                submitted_at=row.submitted_at,
                status="submitted" if row.status == "submitted" else "in_progress",
                total_score=None,
                total_max_score=None,
                skill_scores=[],
            )
            for row in assessments
        ],
        self_report=None,
        activity_results=[],
    )


def build_initial_analysis_request(db: Session, user: User) -> InitialAnalysisRequest:
    now = datetime.now(timezone.utc)
    return InitialAnalysisRequest(
        request_id=f"iar_{uuid4().hex}",
        requested_at=now,
        profile=build_student_snapshot(db, user),
    )
