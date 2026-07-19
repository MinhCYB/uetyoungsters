"""HTTP endpoints for the assessment module."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from modules.auth.dependencies import current_user
from modules.auth.models import User

from .schemas import AssessmentDraftUpdate, AssessmentSubmission
from .models import Assessment
from .service import (AssessmentServiceError, create_question_set, delete_assessment,
                      get_draft, save_draft, submit)

router = APIRouter()


@router.delete("/{assessment_id}", status_code=204)
def remove_assessment(assessment_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    call_service(delete_assessment, db, assessment_id, user)
    return Response(status_code=204)


@router.get("")
def assessment_history(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(Assessment).where(Assessment.user_id == user.id).order_by(Assessment.created_at.desc())).all()
    return [{
        "id": row.id,
        "question_set_id": row.question_set_id,
        "mode": row.mode,
        "status": row.status,
        "version": row.version,
        "last_saved_at": row.last_saved_at,
        "created_at": row.created_at,
        "submitted_at": row.submitted_at,
    } for row in rows]


def call_service(operation, *args):
    try:
        return operation(*args)
    except AssessmentServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/{assessment_id}/draft")
def get_assessment_draft(
    assessment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return call_service(get_draft, db, assessment_id, user)


@router.patch("/{assessment_id}/draft")
def save_assessment_draft(
    assessment_id: str,
    payload: AssessmentDraftUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return call_service(save_draft, db, assessment_id, payload, user)


@router.get("/questions")
def create_assessment_question_set(
    mode: str = Query(default="standard_25_35_min"),
    seed: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return call_service(create_question_set, db, user, mode, seed)


@router.post("/submit")
def submit_assessment(
    submission: AssessmentSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return call_service(submit, db, submission, user)
