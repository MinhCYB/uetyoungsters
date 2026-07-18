"""
Ket noi Postgres dung chung voi crawl-service (core chi doc du lieu do crawl-service ghi).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cc_user:cc_pass@localhost:5432/career_compass")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import (Assessment, AssessmentAnswer, BlueprintRule, Question, QuestionBankVersion,
                        QuestionBlueprint, QuestionCondition, QuestionOption, QuestionScale)
    Base.metadata.create_all(bind=engine, tables=[
        QuestionBankVersion.__table__, Question.__table__, QuestionOption.__table__,
        QuestionCondition.__table__, QuestionScale.__table__, QuestionBlueprint.__table__,
        BlueprintRule.__table__,
        Assessment.__table__, AssessmentAnswer.__table__,
    ])
