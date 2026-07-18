import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database import get_db
from modules.auth.dependencies import require_roles
from modules.auth.models import AuditLog, ClassAssignment, Invitation, Role, SchoolClass, StudentProfile, Tenant, User
from modules.auth.security import hash_token

router = APIRouter(tags=["provisioning"])


class TenantInput(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")
    name: str = Field(min_length=2, max_length=200)


class InviteInput(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=160)


class StudentInvite(InviteInput):
    profile_type: str = "HIGH_SCHOOL"


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
    row = Invitation(email=payload.email.lower(), display_name=payload.display_name, role=role, tenant_id=tenant_id, class_id=class_id, token_hash=hash_token(raw), expires_at=datetime.now(timezone.utc) + timedelta(days=3), invited_by=actor.id)
    db.add(row); db.flush(); audit(db, actor, "ACCOUNT_INVITED", "INVITATION", row.id, tenant_id, {"role": role.value, "email": payload.email.lower()}); db.commit()
    return {"id": row.id, "email": row.email, "role": role.value, "expiresAt": row.expires_at, "acceptToken": raw}


@router.post("/api/admin/tenants", status_code=201)
def create_tenant(payload: TenantInput, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.SUPERADMIN))):
    if db.scalar(select(Tenant).where(Tenant.code == payload.code)):
        raise HTTPException(409, "Mã trường đã tồn tại")
    tenant = Tenant(code=payload.code, name=payload.name, created_by=actor.id)
    db.add(tenant); db.flush(); audit(db, actor, "TENANT_CREATED", "TENANT", tenant.id, tenant.id); db.commit(); db.refresh(tenant)
    return tenant


@router.get("/api/admin/tenants")
def list_tenants(db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.SUPERADMIN))):
    return db.scalars(select(Tenant).order_by(Tenant.created_at.desc())).all()


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
def teachers(db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.TENANT_ADMIN))):
    return db.scalars(select(User).where(User.tenant_id == actor.tenant_id, User.role == Role.HOMEROOM_TEACHER)).all()


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
    return db.execute(select(User, StudentProfile).join(StudentProfile, StudentProfile.user_id == User.id).where(StudentProfile.tenant_id == actor.tenant_id, StudentProfile.class_id == class_id)).all()


@router.post("/api/teacher/classes/{class_id}/students/invitations", status_code=201)
def invite_student(class_id: str, payload: StudentInvite, db: Session = Depends(get_db), actor: User = Depends(require_roles(Role.HOMEROOM_TEACHER))):
    if not active_assignment(db, actor, class_id): raise HTTPException(403, "Bạn không được phân công lớp này")
    return invite(db, actor, payload, Role.STUDENT, actor.tenant_id, class_id)