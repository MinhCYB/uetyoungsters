"""Database models for the recommendation domain.

Stores RIASEC-based career matching results.  career_id references the
career schema owned by crawl-service — no hard FK across services.
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


class MatchedResult(Base):
    """One matching computation for a user + assessment, producing RIASEC scores."""
    __tablename__ = "matched_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    riasec_scores: Mapped[dict] = mapped_column(JSON)
    taxonomy_version: Mapped[str] = mapped_column(String(40))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MatchedResultItem(Base):
    """Individual career match within a MatchedResult, ranked by score."""
    __tablename__ = "matched_result_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    matched_result_id: Mapped[str] = mapped_column(
        ForeignKey("matched_results.id", ondelete="CASCADE"), index=True
    )
    # No hard FK — career_id references career.occupations in crawl-service schema
    career_id: Mapped[str] = mapped_column(String(120))
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
