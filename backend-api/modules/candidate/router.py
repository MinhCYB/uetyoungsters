from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from modules.auth.dependencies import current_user
from modules.auth.models import Role, User

from .snapshot_builder import (SnapshotBuildError,
                               build_initial_analysis_request,
                               build_student_snapshot)
from .models import AcademicRecord, CandidateProfile
from .schemas import (AcademicRecordInput, AcademicRecordResponse,
                      CandidateProfileResponse, CandidateProfileUpdate)

router = APIRouter()


def _profile(db: Session, user: User) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        raise HTTPException(404, "Người dùng chưa có candidate profile")
    return profile


@router.get("/me", response_model=CandidateProfileResponse)
def my_profile(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _profile(db, user)


@router.patch("/me", response_model=CandidateProfileResponse)
def update_my_profile(payload: CandidateProfileUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    profile = _profile(db, user)
    if user.role == Role.STUDENT or profile.profile_type in {"HIGH_SCHOOL", "UNIVERSITY"}:
        raise HTTPException(403, "Hồ sơ học sinh/sinh viên do giáo viên quản lý; bạn chỉ có thể làm bài đánh giá năng lực")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    profile.version += 1
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/me/academic-records", response_model=list[AcademicRecordResponse])
def academic_records(db: Session = Depends(get_db), user: User = Depends(current_user)):
    profile = _profile(db, user)
    return db.scalars(select(AcademicRecord).where(AcademicRecord.candidate_profile_id == profile.id).order_by(AcademicRecord.semester, AcademicRecord.subject)).all()


@router.post("/me/academic-records", response_model=AcademicRecordResponse, status_code=201)
def create_academic_record(payload: AcademicRecordInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    profile = _profile(db, user)
    if user.role == Role.STUDENT:
        raise HTTPException(403, "Bảng điểm của người học do giáo viên quản lý")
    row = AcademicRecord(candidate_profile_id=profile.id, **payload.model_dump())
    profile.version += 1
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _owned_record(db: Session, user: User, record_id: str) -> tuple[CandidateProfile, AcademicRecord]:
    profile = _profile(db, user)
    row = db.scalar(select(AcademicRecord).where(AcademicRecord.id == record_id, AcademicRecord.candidate_profile_id == profile.id))
    if not row:
        raise HTTPException(404, "Không tìm thấy bản ghi học tập")
    return profile, row


@router.put("/me/academic-records/{record_id}", response_model=AcademicRecordResponse)
def update_academic_record(record_id: str, payload: AcademicRecordInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == Role.STUDENT:
        raise HTTPException(403, "Bảng điểm của người học do giáo viên quản lý")
    profile, row = _owned_record(db, user, record_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    profile.version += 1
    db.commit()
    db.refresh(row)
    return row


@router.delete("/me/academic-records/{record_id}", status_code=204)
def delete_academic_record(record_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == Role.STUDENT:
        raise HTTPException(403, "Bảng điểm của người học do giáo viên quản lý")
    profile, row = _owned_record(db, user, record_id)
    profile.version += 1
    db.delete(row)
    db.commit()
    return Response(status_code=204)


def _build(operation, db: Session, user: User):
    try:
        return operation(db, user)
    except SnapshotBuildError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/me/snapshot")
def my_snapshot(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _build(build_student_snapshot, db, user)


@router.get("/me/initial-analysis-request")
def my_initial_analysis_request(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _build(build_initial_analysis_request, db, user)
