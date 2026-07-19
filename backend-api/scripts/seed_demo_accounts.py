"""Create the five demo roles and their required school relationships.

Safe to run repeatedly: existing demo rows are updated instead of duplicated.
Never run this script in production.
"""
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal, init_db
from modules.auth.models import (ClassAssignment, Role, SchoolClass, Tenant,
                                 User, UserStatus)
from modules.auth.security import hash_password
from modules.candidate.models import CandidateProfile


PASSWORD = os.getenv("DEMO_PASSWORD", "Demo@123456")
TENANT_CODE = "DEMO_SCHOOL"
ACCOUNTS = (
    ("superadmin@demo.example.com", "Demo Super Admin", Role.SUPERADMIN),
    ("admin@demo.example.com", "Demo School Admin", Role.TENANT_ADMIN),
    ("teacher@demo.example.com", "Demo Homeroom Teacher", Role.HOMEROOM_TEACHER),
    ("student@demo.example.com", "Demo Student", Role.STUDENT),
    ("professional@demo.example.com", "Demo Professional", Role.PROFESSIONAL),
)


def upsert_user(db, email: str, name: str, role: Role, tenant_id: str | None) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email)
        db.add(user)
    user.display_name = name
    user.password_hash = hash_password(PASSWORD)
    user.role = role
    user.tenant_id = tenant_id
    user.status = UserStatus.ACTIVE
    user.must_change_password = False
    user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
    db.flush()
    return user


def seed() -> None:
    init_db()
    with SessionLocal() as db:
        # Migrate the initially documented .local demo addresses, which strict
        # EmailStr validation correctly rejects at the login boundary.
        for email, _, _ in ACCOUNTS:
            legacy_email = email.replace("@demo.example.com", "@demo.local")
            legacy = db.scalar(select(User).where(User.email == legacy_email))
            current = db.scalar(select(User).where(User.email == email))
            if legacy and not current:
                legacy.email = email
        db.flush()
        superadmin = upsert_user(db, *ACCOUNTS[0], tenant_id=None)

        tenant = db.scalar(select(Tenant).where(Tenant.code == TENANT_CODE))
        if not tenant:
            tenant = Tenant(code=TENANT_CODE, name="Career Compass Demo School", created_by=superadmin.id)
            db.add(tenant)
            db.flush()
        tenant.status = "ACTIVE"

        admin = upsert_user(db, *ACCOUNTS[1], tenant_id=tenant.id)
        teacher = upsert_user(db, *ACCOUNTS[2], tenant_id=tenant.id)
        student = upsert_user(db, *ACCOUNTS[3], tenant_id=tenant.id)
        professional = upsert_user(db, *ACCOUNTS[4], tenant_id=None)

        classroom = db.scalar(select(SchoolClass).where(
            SchoolClass.tenant_id == tenant.id,
            SchoolClass.name == "Demo 12A1",
            SchoolClass.school_year == "2026-2027",
        ))
        if not classroom:
            classroom = SchoolClass(tenant_id=tenant.id, name="Demo 12A1", grade_level="12", school_year="2026-2027")
            db.add(classroom)
            db.flush()

        assignment = db.scalar(select(ClassAssignment).where(
            ClassAssignment.class_id == classroom.id,
            ClassAssignment.teacher_id == teacher.id,
        ))
        if not assignment:
            db.add(ClassAssignment(
                tenant_id=tenant.id,
                class_id=classroom.id,
                teacher_id=teacher.id,
                starts_at=date(2026, 1, 1),
                ends_at=None,
                created_by=admin.id,
            ))

        student_profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == student.id))
        if not student_profile:
            student_profile = CandidateProfile(user_id=student.id)
            db.add(student_profile)
        student_profile.tenant_id = tenant.id
        student_profile.class_id = classroom.id
        student_profile.profile_type = "HIGH_SCHOOL"
        student_profile.student_code = "DEMO-STUDENT-001"
        student_profile.school = tenant.name
        student_profile.grade = "12"

        professional_profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == professional.id))
        if not professional_profile:
            professional_profile = CandidateProfile(user_id=professional.id)
            db.add(professional_profile)
        professional_profile.tenant_id = None
        professional_profile.class_id = None
        professional_profile.profile_type = "PROFESSIONAL"
        professional_profile.current_job = "Data Analyst"
        professional_profile.experience_years = 2

        db.commit()
        print("Seeded 5 demo roles, tenant, class, assignment, and candidate profiles.")


if __name__ == "__main__":
    seed()
