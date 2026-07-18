"""Database models for the candidate domain.

Contains student academic records and professional CV document tracking.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class AcademicRecord(Base):
    """Transcript-like records for student profiles (grades, conduct, notes)."""
    __tablename__ = "academic_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    score: Mapped[float] = mapped_column(Float)
    semester: Mapped[str] = mapped_column(String(40))
    conduct: Mapped[str | None] = mapped_column(String(40), nullable=True)  # hạnh kiểm
    teacher_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class CvDocument(Base):
    """Uploaded CV/resume files tracked for async parsing by ai-worker-service."""
    __tablename__ = "cv_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    professional_profile_id: Mapped[str] = mapped_column(ForeignKey("professional_profiles.id"), index=True)
    object_key: Mapped[str] = mapped_column(String(500))  # MinIO/S3 path
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | processing | done | failed
