import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database import get_db
from modules.auth.dependencies import require_roles
from modules.auth.models import AuditLog, ClassAssignment, Invitation, Role, SchoolClass, Tenant, User, UserStatus
from modules.auth.security import hash_token
from modules.candidate.models import AcademicRecord, CandidateProfile, TeacherEvaluation
from modules.candidate.schemas import (AcademicRecordInput, AcademicRecordResponse,
                                       CandidateProfileUpdate,
                                       TeacherEvaluationInput,
                                       TeacherEvaluationResponse)
from modules.assessment.models import Assessment

router = APIRouter(tags=["provisioning"])


class TenantInput(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")
    name: str = Field(min_length=2, max_length=200)


class InviteInput(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=160)


class StudentInvite(InviteInput):
    profile_type: Literal["HIGH_SCHOOL", "UNIVERSITY"] = "HIGH_SCHOOL"
    student_code: str = Field(min_length=1, max_length=80)
    gender: str | None = Field(default=None, max_length=30)
    age: int | None = Field(default=None, ge=10, le=100)
    region: str | None = Field(default=None, max_length=200)
    school: str | None = Field(default=None, max_length=240)
    grade: str | None = Field(default=None, max_length=40)
    major: str | None = Field(default=None, max_length=240)
    study_year: int | None = Field(default=None, ge=1, le=12)
    gpa: float | None = Field(default=None, ge=0, le=10)


class ClassInput(BaseModel):
    name: str
    grade_level: str
    school_year: str


class AssignmentInput(BaseModel):
    teacher_id: str
    starts_at: date
    ends_at: date | None = None


def audit(db, actor, action, resource_type, resource_id, tenant_id=None, details=None):
    db.add(AuditLog(actor_id=actor.id, tenant_id=tenant_id if tenant_id is not None else actor.tenant_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details or {}))


def invite(db, actor, payload, role, tenant_id, class_id=None):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(409, "Email đã có tài khoản")
    raw = secrets.token_urlsafe(32)
    profile_type = getattr(payload, "profile_type", None) if role == Role.STUDENT else None
    profile_data = payload.model_dump(exclude={"email", "display_name", "profile_type"}, exclude_none=True) if role == Role.STUDENT else {}
    row = Invitation(email=payload.email.lower(), display_name=payload.display_name, role=role, tenant_id=tenant_id, class_id=class_id, profile_type=profile_type, profile_data=profile_data, token_hash=hash_token(raw), expires_at=datetime.now(timezone.utc) + timedelta(days=3), invited_by=actor.id)
    db.add(row); db.flush(); audit(db, actor, "ACCOUNT_INVITED", "INVITATION", row.id, tenant_id, {"role": role.value, "profile_type": profile_type, "email": payload.email.lower()}); db.commit()
    return {"id": row.id, "email": row.email, "role": role.value, "profileType": profile_type, "expiresAt": row.expires_at, "acceptToken": raw}


@router.post("/api/admin/tenants", status_code=201)
def create_tenant(payload: TenantInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.SUPERADMIN))):
    if db.scalar(select(Tenant).where(Tenant.code == payload.code)):
        raise HTTPException(409, "Mã trường đã tồn tại")
    tenant = Tenant(code=payload.code, name=payload.name, created_by=actor.id)
    db.add(tenant); db.flush(); audit(db, actor, "TENANT_CREATED", "TENANT", tenant.id, tenant.id); db.commit(); db.refresh(tenant)
    return tenant


@router.get("/api/admin/tenants")
def list_tenants(status: str = "ACTIVE", db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.SUPERADMIN))):
    return db.scalars(select(Tenant).where(Tenant.status == status.upper()).order_by(Tenant.created_at.desc())).all()


@router.post("/api/admin/tenants/{tenant_id}/admins/invitations", status_code=201)
def invite_admin(tenant_id: str, payload: InviteInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.SUPERADMIN))):
    if not db.get(Tenant, tenant_id): raise HTTPException(404, "Không tìm thấy trường")
    return invite(db, actor, payload, Role.TENANT_ADMIN, tenant_id)


@router.get("/api/admin/audit-logs")
def audit_logs(db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.SUPERADMIN))):
    return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).all()


@router.post("/api/school/teachers/invitations", status_code=201)
def invite_teacher(payload: InviteInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.TENANT_ADMIN))):
    return invite(db, actor, payload, Role.HOMEROOM_TEACHER, actor.tenant_id)


@router.get("/api/school/teachers")
def teachers(status: UserStatus = UserStatus.ACTIVE, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.TENANT_ADMIN))):
    return db.scalars(select(User).where(User.tenant_id == actor.tenant_id, User.role == Role.HOMEROOM_TEACHER, User.status == status)).all()


@router.post("/api/school/classes", status_code=201)
def create_class(payload: ClassInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.TENANT_ADMIN))):
    row = SchoolClass(tenant_id=actor.tenant_id, **payload.model_dump())
    db.add(row); db.flush(); audit(db, actor, "CLASS_CREATED", "CLASS", row.id); db.commit(); db.refresh(row); return row


@router.get("/api/school/classes")
def classes(db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.TENANT_ADMIN))):
    return db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == actor.tenant_id)).all()


@router.post("/api/school/classes/{class_id}/assignments", status_code=201)
def assign_teacher(class_id: str, payload: AssignmentInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.TENANT_ADMIN))):
    classroom = db.get(SchoolClass, class_id); teacher = db.get(User, payload.teacher_id)
    if not classroom or classroom.tenant_id != actor.tenant_id or not teacher or teacher.tenant_id != actor.tenant_id or teacher.role != Role.HOMEROOM_TEACHER:
        raise HTTPException(404, "Lớp hoặc giáo viên không hợp lệ trong trường này")
    row = ClassAssignment(tenant_id=actor.tenant_id, class_id=class_id, created_by=actor.id, **payload.model_dump())
    db.add(row); db.flush(); audit(db, actor, "TEACHER_ASSIGNED", "CLASS_ASSIGNMENT", row.id); db.commit(); db.refresh(row); return row


def active_assignment(db, actor, class_id):
    today = date.today()
    return db.scalar(select(ClassAssignment).where(ClassAssignment.tenant_id == actor.tenant_id, ClassAssignment.teacher_id == actor.id, ClassAssignment.class_id == class_id, ClassAssignment.starts_at <= today, or_(ClassAssignment.ends_at.is_(None), ClassAssignment.ends_at >= today)))


@router.get("/api/teacher/classes")
def my_classes(db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    today = date.today()
    return db.scalars(select(SchoolClass).join(ClassAssignment, ClassAssignment.class_id == SchoolClass.id).where(ClassAssignment.teacher_id == actor.id, ClassAssignment.tenant_id == actor.tenant_id, ClassAssignment.starts_at <= today, or_(ClassAssignment.ends_at.is_(None), ClassAssignment.ends_at >= today))).all()


@router.get("/api/teacher/classes/{class_id}/students")
def class_students(class_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    if not active_assignment(db, actor, class_id): raise HTTPException(403, "Bạn không được phân công lớp này")
    rows = db.execute(select(User, CandidateProfile).join(CandidateProfile, CandidateProfile.user_id == User.id).where(CandidateProfile.tenant_id == actor.tenant_id, CandidateProfile.class_id == class_id)).all()
    return [{"id": user.id, "email": user.email, "display_name": user.display_name, "status": user.status.value, "profile_type": profile.profile_type, "student_code": profile.student_code} for user, profile in rows]


@router.post("/api/teacher/classes/{class_id}/students/invitations", status_code=201)
def invite_student(class_id: str, payload: StudentInvite, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    if not active_assignment(db, actor, class_id): raise HTTPException(403, "Bạn không được phân công lớp này")
    return invite(db, actor, payload, Role.STUDENT, actor.tenant_id, class_id)


def assigned_student_profile(db: Session, actor: User, class_id: str, student_id: str) -> CandidateProfile:
    if not active_assignment(db, actor, class_id):
        raise HTTPException(403, "Bạn không được phân công lớp này")
    profile = db.scalar(select(CandidateProfile).where(
        CandidateProfile.user_id == student_id,
        CandidateProfile.tenant_id == actor.tenant_id,
        CandidateProfile.class_id == class_id,
        CandidateProfile.profile_type.in_(("HIGH_SCHOOL", "UNIVERSITY")),
    ))
    if not profile:
        raise HTTPException(404, "Không tìm thấy người học trong lớp")
    return profile


@router.get("/api/teacher/classes/{class_id}/students/{student_id}/profile")
def student_profile(class_id: str, student_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    return assigned_student_profile(db, actor, class_id, student_id)


@router.patch("/api/teacher/classes/{class_id}/students/{student_id}/profile")
def update_student_profile(class_id: str, student_id: str, payload: CandidateProfileUpdate, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    profile = assigned_student_profile(db, actor, class_id, student_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("profile_type") not in (None, "HIGH_SCHOOL", "UNIVERSITY"):
        raise HTTPException(422, "Giáo viên chỉ quản lý hồ sơ người học")
    for key, value in changes.items():
        setattr(profile, key, value)
    profile.version += 1
    audit(db, actor, "STUDENT_PROFILE_UPDATED", "CANDIDATE_PROFILE", profile.id, details={"student_id": student_id})
    db.commit(); db.refresh(profile)
    return profile


@router.get("/api/teacher/classes/{class_id}/students/{student_id}/academic-records", response_model=list[AcademicRecordResponse])
def student_academic_records(class_id: str, student_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    profile = assigned_student_profile(db, actor, class_id, student_id)
    return db.scalars(select(AcademicRecord).where(AcademicRecord.candidate_profile_id == profile.id).order_by(AcademicRecord.semester, AcademicRecord.subject)).all()


@router.post("/api/teacher/classes/{class_id}/students/{student_id}/academic-records", response_model=AcademicRecordResponse, status_code=201)
def add_student_academic_record(class_id: str, student_id: str, payload: AcademicRecordInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    profile = assigned_student_profile(db, actor, class_id, student_id)
    row = AcademicRecord(candidate_profile_id=profile.id, **payload.model_dump())
    profile.version += 1
    db.add(row); db.flush()
    audit(db, actor, "STUDENT_ACADEMIC_RECORD_ADDED", "ACADEMIC_RECORD", row.id, details={"student_id": student_id, "subject": row.subject})
    db.commit(); db.refresh(row)
    return row


@router.get("/api/teacher/classes/{class_id}/students/{student_id}/evaluations", response_model=list[TeacherEvaluationResponse])
def student_evaluations(class_id: str, student_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    profile = assigned_student_profile(db, actor, class_id, student_id)
    return db.scalars(select(TeacherEvaluation).where(TeacherEvaluation.candidate_profile_id == profile.id).order_by(TeacherEvaluation.created_at.desc())).all()


@router.post("/api/teacher/classes/{class_id}/students/{student_id}/evaluations", response_model=TeacherEvaluationResponse, status_code=201)
def evaluate_student(class_id: str, student_id: str, payload: TeacherEvaluationInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    profile = assigned_student_profile(db, actor, class_id, student_id)
    row = TeacherEvaluation(candidate_profile_id=profile.id, teacher_id=actor.id, rating=0, **payload.model_dump())
    profile.version += 1
    db.add(row); db.flush(); audit(db, actor, "STUDENT_EVALUATED", "TEACHER_EVALUATION", row.id, details={"student_id": student_id})
    db.commit(); db.refresh(row)
    return row


@router.delete("/api/admin/tenants/{tenant_id}", status_code=204)
def disable_tenant(tenant_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.SUPERADMIN))):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Không tìm thấy trường")
    tenant.status = "DISABLED"
    db.query(User).filter(User.tenant_id == tenant.id).update({User.status: UserStatus.DISABLED}, synchronize_session=False)
    audit(db, actor, "TENANT_DISABLED", "TENANT", tenant.id, tenant.id, {"code": tenant.code})
    db.commit()
    return Response(status_code=204)


@router.delete("/api/school/teachers/{teacher_id}", status_code=204)
def disable_teacher(teacher_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.TENANT_ADMIN))):
    teacher = db.get(User, teacher_id)
    if not teacher or teacher.tenant_id != actor.tenant_id or teacher.role != Role.HOMEROOM_TEACHER:
        raise HTTPException(404, "Không tìm thấy giáo viên trong trường")
    assignment_count = db.query(ClassAssignment).filter_by(teacher_id=teacher.id, tenant_id=actor.tenant_id).delete(synchronize_session=False)
    teacher.status = UserStatus.DISABLED
    audit(db, actor, "TEACHER_DISABLED", "USER", teacher.id, details={"email": teacher.email, "assignments_removed": assignment_count})
    db.commit()
    return Response(status_code=204)


@router.delete("/api/teacher/classes/{class_id}/students/{student_id}", status_code=204)
def remove_student(class_id: str, student_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    if not active_assignment(db, actor, class_id):
        raise HTTPException(403, "Bạn không được phân công lớp này")
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == student_id, CandidateProfile.tenant_id == actor.tenant_id, CandidateProfile.class_id == class_id))
    if not profile:
        raise HTTPException(404, "Không tìm thấy học sinh trong lớp")
    profile.class_id = None
    profile.version += 1
    audit(db, actor, "STUDENT_REMOVED_FROM_CLASS", "USER", student_id, details={"class_id": class_id})
    db.commit()
    return Response(status_code=204)


@router.get("/api/teacher/classes/{class_id}/assessment-status")
def class_assessment_status(class_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    if not active_assignment(db, actor, class_id):
        raise HTTPException(403, "Bạn không được phân công lớp này")
    rows = db.execute(select(User, CandidateProfile).join(CandidateProfile, CandidateProfile.user_id == User.id).where(CandidateProfile.tenant_id == actor.tenant_id, CandidateProfile.class_id == class_id)).all()
    result = []
    for student, profile in rows:
        assessment = db.scalar(select(Assessment).where(Assessment.user_id == student.id).order_by(Assessment.created_at.desc()).limit(1))
        result.append({"student_id": student.id, "display_name": student.display_name, "email": student.email, "profile_type": profile.profile_type, "assessment_id": assessment.id if assessment else None, "assessment_status": assessment.status if assessment else "not_started", "last_saved_at": assessment.last_saved_at if assessment else None, "submitted_at": assessment.submitted_at if assessment else None})
    return result


@router.patch("/api/admin/tenants/{tenant_id}/restore")
def restore_tenant(tenant_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.SUPERADMIN))):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Không tìm thấy trường")
    tenant.status = "ACTIVE"
    restored = db.query(User).filter(User.tenant_id == tenant.id, User.status == UserStatus.DISABLED).update({User.status: UserStatus.ACTIVE}, synchronize_session=False)
    audit(db, actor, "TENANT_RESTORED", "TENANT", tenant.id, tenant.id, {"code": tenant.code, "users_restored": restored})
    db.commit(); db.refresh(tenant)
    return tenant


@router.patch("/api/school/teachers/{teacher_id}/restore")
def restore_teacher(teacher_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.TENANT_ADMIN))):
    teacher = db.get(User, teacher_id)
    if not teacher or teacher.tenant_id != actor.tenant_id or teacher.role != Role.HOMEROOM_TEACHER:
        raise HTTPException(404, "Không tìm thấy giáo viên trong trường")
    teacher.status = UserStatus.ACTIVE
    audit(db, actor, "TEACHER_RESTORED", "USER", teacher.id, details={"email": teacher.email, "requires_reassignment": True})
    db.commit(); db.refresh(teacher)
    return teacher


@router.get("/api/teacher/classes/{class_id}/removed-students")
def removed_students(class_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    if not active_assignment(db, actor, class_id):
        raise HTTPException(403, "Bạn không được phân công lớp này")
    rows = db.execute(select(User, CandidateProfile).join(CandidateProfile, CandidateProfile.user_id == User.id).where(CandidateProfile.tenant_id == actor.tenant_id, CandidateProfile.class_id.is_(None), User.role == Role.STUDENT)).all()
    return [{"id": user.id, "email": user.email, "display_name": user.display_name, "status": user.status.value, "profile_type": profile.profile_type, "student_code": profile.student_code} for user, profile in rows]


@router.patch("/api/teacher/classes/{class_id}/students/{student_id}/restore")
def restore_student(class_id: str, student_id: str, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    if not active_assignment(db, actor, class_id):
        raise HTTPException(403, "Bạn không được phân công lớp này")
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == student_id, CandidateProfile.tenant_id == actor.tenant_id, CandidateProfile.class_id.is_(None)))
    if not profile:
        raise HTTPException(404, "Không tìm thấy học sinh đã gỡ")
    profile.class_id = class_id
    profile.version += 1
    audit(db, actor, "STUDENT_RESTORED_TO_CLASS", "USER", student_id, details={"class_id": class_id})
    db.commit()
    return {"student_id": student_id, "class_id": class_id, "status": "restored"}
