"""Database models for the roadmap service.

Separate service with its own DB models — does NOT import from backend-api.
Cross-service references (user_id, career_id) are stored as plain strings.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# Skill Test
# ---------------------------------------------------------------------------

class SkillTestQuestion(Base):
    """Career-specific skill assessment questions (managed by roadmap-service)."""
    __tablename__ = "skill_test_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    career_id: Mapped[str] = mapped_column(String(120), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(40))  # single_choice | open_text | etc.
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)  # easy | medium | hard
    active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SkillTestResult(Base):
    """Result of a user's skill test for a specific career."""
    __tablename__ = "skill_test_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)  # no FK — cross-service
    career_id: Mapped[str] = mapped_column(String(120), index=True)
    score: Mapped[float] = mapped_column(Float)
    skill_gaps: Mapped[dict] = mapped_column(JSON, default=dict)
    tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# Expert Resource
# ---------------------------------------------------------------------------

class ExpertResource(Base):
    """Curated resources for career-specific learning paths."""
    __tablename__ = "expert_resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    career_id: Mapped[str] = mapped_column(String(120), index=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    added_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# Roadmap
# ---------------------------------------------------------------------------

class Roadmap(Base):
    """LLM-generated personalised career roadmap for a user."""
    __tablename__ = "roadmaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)  # no FK — cross-service
    career_id: Mapped[str] = mapped_column(String(120), index=True)
    skill_test_result_id: Mapped[str] = mapped_column(
        ForeignKey("skill_test_results.id"), index=True
    )
    # Runtime-computed segment — see compute_user_segment() in main.py
    user_segment: Mapped[str] = mapped_column(String(30))
    llm_prompt_version: Mapped[str] = mapped_column(String(40))
    steps: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
