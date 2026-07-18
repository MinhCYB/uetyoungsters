"""Roadmap service — personalised career roadmap generation.

Separate FastAPI service that calls LLM to generate roadmaps.
Communicates with backend-api via HTTP (not direct DB import).
"""

import os
from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, init_db
from models import Roadmap, SkillTestResult

app = FastAPI(title="Career Compass — Roadmap Service", version="0.1.0")

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://backend-api:8000")


# ---------------------------------------------------------------------------
# User segment enum + computation
# ---------------------------------------------------------------------------

class UserSegment(str, Enum):
    HS_FOUNDATION = "HS_FOUNDATION"
    SV_SAME_MAJOR = "SV_SAME_MAJOR"
    SV_DIFF_MAJOR = "SV_DIFF_MAJOR"
    WORKER_SAME_FIELD = "WORKER_SAME_FIELD"
    WORKER_DIFF_FIELD = "WORKER_DIFF_FIELD"


def compute_user_segment(
    role: str,
    education_stage: str | None,
    current_major_career_id: str | None,
    current_career_id: str | None,
    target_career_id: str,
) -> UserSegment:
    """Determine user segment for roadmap personalisation.

    Parameters are fetched at runtime from backend-api — NOT stored
    permanently on the user record.
    """
    if role == "STUDENT":
        if education_stage == "HIGH_SCHOOL":
            return UserSegment.HS_FOUNDATION
        # UNIVERSITY
        if current_major_career_id and current_major_career_id == target_career_id:
            return UserSegment.SV_SAME_MAJOR
        return UserSegment.SV_DIFF_MAJOR

    if role == "PROFESSIONAL":
        if current_career_id and current_career_id == target_career_id:
            return UserSegment.WORKER_SAME_FIELD
        return UserSegment.WORKER_DIFF_FIELD

    # Fallback for unknown roles
    return UserSegment.HS_FOUNDATION


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/roadmap/health")
def health():
    return {"status": "ok", "service": "roadmap-service"}


class RoadmapRequest(BaseModel):
    user_id: str
    career_id: str
    skill_test_result_id: str
    # User profile info (fetched by caller or passed through)
    role: str
    education_stage: str | None = None
    current_major_career_id: str | None = None
    current_career_id: str | None = None


class RoadmapResponse(BaseModel):
    roadmap_id: str
    user_segment: str
    steps: dict


@app.post("/api/roadmap/generate", response_model=RoadmapResponse)
def generate_roadmap(request: RoadmapRequest, db: Session = Depends(get_db)):
    """Generate a personalised career roadmap.

    Currently returns a mock response.  Real LLM integration to be
    implemented separately.
    """
    # Verify skill test result exists
    skill_test = db.get(SkillTestResult, request.skill_test_result_id)
    if not skill_test:
        raise HTTPException(status_code=404, detail="Skill test result not found")

    segment = compute_user_segment(
        role=request.role,
        education_stage=request.education_stage,
        current_major_career_id=request.current_major_career_id,
        current_career_id=request.current_career_id,
        target_career_id=request.career_id,
    )

    # Mock roadmap steps — replace with LLM call
    mock_steps = {
        "phases": [
            {"title": "Nền tảng", "duration": "3 tháng", "tasks": ["TODO: LLM-generated tasks"]},
            {"title": "Phát triển", "duration": "6 tháng", "tasks": ["TODO: LLM-generated tasks"]},
            {"title": "Chuyên sâu", "duration": "6 tháng", "tasks": ["TODO: LLM-generated tasks"]},
        ]
    }

    roadmap = Roadmap(
        user_id=request.user_id,
        career_id=request.career_id,
        skill_test_result_id=request.skill_test_result_id,
        user_segment=segment.value,
        llm_prompt_version="v0.1.0-mock",
        steps=mock_steps,
    )
    db.add(roadmap)
    db.commit()
    db.refresh(roadmap)

    return RoadmapResponse(
        roadmap_id=roadmap.id,
        user_segment=segment.value,
        steps=mock_steps,
    )
