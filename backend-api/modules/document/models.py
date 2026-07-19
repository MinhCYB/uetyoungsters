from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ProfileDocument(Base):
    __tablename__ = "profile_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    candidate_profile_id: Mapped[str] = mapped_column(ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(30), default="CV", index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
