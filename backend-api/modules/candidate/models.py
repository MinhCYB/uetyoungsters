"""Database models for the candidate domain.

Contains student academic records and professional CV document tracking.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class CandidateProfile(Base):
    """One common profile for high-school, university, and professional users."""
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    class_id: Mapped[str | None] = mapped_column(ForeignKey("classes.id"), nullable=True, index=True)
    profile_type: Mapped[str] = mapped_column(String(30), index=True)
    student_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    school: Mapped[str | None] = mapped_column(String(240), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(40), nullable=True)
    major: Mapped[str | None] = mapped_column(String(240), nullable=True)
    study_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_job: Mapped[str | None] = mapped_column(String(240), nullable=True)
    experience_years: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_career_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    basic_information: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

class AcademicRecord(Base):
    """Transcript-like records owned by the common candidate profile."""
    __tablename__ = "academic_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candidate_profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    score: Mapped[float] = mapped_column(Float)
    semester: Mapped[str] = mapped_column(String(40))
    conduct: Mapped[str | None] = mapped_column(String(40), nullable=True)  # hạnh kiểm
    teacher_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class TeacherEvaluation(Base):
    """A teacher's dated evaluation of one learner in an assigned class."""
    __tablename__ = "teacher_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candidate_profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer, default=0)
    observation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
