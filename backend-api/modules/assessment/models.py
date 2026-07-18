"""Normalized database models for the assessment domain."""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class QuestionBankVersion(Base):
    __tablename__ = "question_bank_versions"
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(12), default="vi")
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    version: Mapped[str] = mapped_column(ForeignKey("question_bank_versions.version"), index=True)
    section: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(160), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(40), index=True)
    order_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    scored: Mapped[bool] = mapped_column(Boolean, default=False)
    scale_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class QuestionOption(Base):
    __tablename__ = "question_options"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(String(240))
    label: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("question_id", "value", name="uq_question_option_value"),)


class QuestionCondition(Base):
    __tablename__ = "question_conditions"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    depends_on_question_id: Mapped[str] = mapped_column(String(120), index=True)
    operator: Mapped[str] = mapped_column(String(24))
    expected_value: Mapped[object] = mapped_column(JSON)


class QuestionScale(Base):
    __tablename__ = "question_scales"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[str] = mapped_column(ForeignKey("question_bank_versions.version"), index=True)
    minimum: Mapped[int] = mapped_column(Integer)
    maximum: Mapped[int] = mapped_column(Integer)
    labels: Mapped[list] = mapped_column(JSON)


class QuestionBlueprint(Base):
    __tablename__ = "question_blueprints"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    version: Mapped[str] = mapped_column(ForeignKey("question_bank_versions.version"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class BlueprintRule(Base):
    __tablename__ = "blueprint_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blueprint_id: Mapped[str] = mapped_column(ForeignKey("question_blueprints.id", ondelete="CASCADE"), index=True)
    section_key: Mapped[str] = mapped_column(String(100))
    order_index: Mapped[int] = mapped_column(Integer)
    rule_config: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("blueprint_id", "section_key", name="uq_blueprint_section"),)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    question_set_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(80))
    seed: Mapped[int] = mapped_column(BigInteger)
    schema_version: Mapped[str] = mapped_column(String(40))
    question_ids: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="in_progress", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"
    __table_args__ = (UniqueConstraint("assessment_id", "question_id", name="uq_assessment_answer"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(120), index=True)
    question_type: Mapped[str] = mapped_column(String(40))
    answer: Mapped[object] = mapped_column(JSON)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
