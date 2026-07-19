"""Roadmap service — personalised career roadmap generation.

Separate FastAPI service that calls LLM to generate roadmaps.
Communicates with backend-api via HTTP (not direct DB import).
"""

import os
from enum import Enum

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db, init_db
from models import Roadmap, SkillTestQuestion, SkillTestResult

app = FastAPI(title="Career Compass — Roadmap Service", version="0.1.0")

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://backend-api:8000")


def authenticated_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(401, "Thiếu access token")
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/auth/me",
            headers={"Authorization": authorization},
            timeout=5,
        )
    except requests.RequestException as error:
        raise HTTPException(503, "Không thể xác thực với backend-api") from error
    if response.status_code != 200:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    user = response.json()
    user["_authorization"] = authorization
    return user


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
    career_id: str
    skill_test_result_id: str


class RoadmapResponse(BaseModel):
    roadmap_id: str
    user_segment: str
    steps: dict


@app.post("/api/roadmap/generate", response_model=RoadmapResponse)
def generate_roadmap(request: RoadmapRequest, db: Session = Depends(get_db), user: dict = Depends(authenticated_user)):
    """Generate a personalised career roadmap.

    Currently returns a mock response.  Real LLM integration to be
    implemented separately.
    """
    # Verify skill test result exists
    skill_test = db.get(SkillTestResult, request.skill_test_result_id)
    if not skill_test or skill_test.user_id != user["id"]:
        raise HTTPException(status_code=404, detail="Skill test result not found")

    profile = {}
    try:
        profile_response = requests.get(
            f"{BACKEND_API_URL}/api/candidate/me",
            headers={"Authorization": user["_authorization"]},
            timeout=5,
        )
        if profile_response.status_code == 200:
            profile = profile_response.json()
    except requests.RequestException:
        pass

    profile_type = profile.get("profile_type")

    segment = compute_user_segment(
        role=user["role"],
        education_stage=profile_type if profile_type in {"HIGH_SCHOOL", "UNIVERSITY"} else None,
        current_major_career_id=profile.get("current_career_id") if profile_type == "UNIVERSITY" else None,
        current_career_id=profile.get("current_career_id"),
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
        user_id=user["id"],
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


class SkillSubmission(BaseModel):
    career_id: str
    responses: dict[str, str]


class SkillQuestionInput(BaseModel):
    career_id: str
    prompt: str
    question_type: str = "single_choice"
    options: dict | None = None
    correct_answer: str | None = None
    difficulty: str | None = None


@app.post("/api/roadmap/skill-tests/questions", status_code=201)
def create_skill_question(payload: SkillQuestionInput, db: Session = Depends(get_db), user: dict = Depends(authenticated_user)):
    if user["role"] not in {"SUPERADMIN", "TENANT_ADMIN"}:
        raise HTTPException(403, "Bạn không có quyền tạo câu hỏi kỹ năng")
    row = SkillTestQuestion(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "career_id": row.career_id, "prompt": row.prompt, "question_type": row.question_type, "options": row.options, "difficulty": row.difficulty}


@app.get("/api/roadmap/skill-tests/questions")
def skill_questions(career_id: str = Query(...), db: Session = Depends(get_db), user: dict = Depends(authenticated_user)):
    rows = db.scalars(select(SkillTestQuestion).where(SkillTestQuestion.career_id == career_id, SkillTestQuestion.active.is_(True)).order_by(SkillTestQuestion.created_at)).all()
    return [{"id": row.id, "prompt": row.prompt, "question_type": row.question_type, "options": row.options, "difficulty": row.difficulty} for row in rows]


@app.post("/api/roadmap/skill-tests/submit", status_code=201)
def submit_skill_test(payload: SkillSubmission, db: Session = Depends(get_db), user: dict = Depends(authenticated_user)):
    rows = db.scalars(select(SkillTestQuestion).where(SkillTestQuestion.career_id == payload.career_id, SkillTestQuestion.active.is_(True))).all()
    if not rows:
        raise HTTPException(404, "Chưa có bộ kiểm tra kỹ năng cho nghề này")
    unknown = set(payload.responses) - {row.id for row in rows}
    if unknown:
        raise HTTPException(422, {"message": "Câu hỏi không hợp lệ", "question_ids": sorted(unknown)})
    gradable = [row for row in rows if row.correct_answer is not None]
    correct = sum(str(payload.responses.get(row.id, "")).strip().casefold() == str(row.correct_answer).strip().casefold() for row in gradable)
    score = round(correct / len(gradable) * 100, 2) if gradable else 0.0
    gaps = {row.id: row.prompt for row in gradable if str(payload.responses.get(row.id, "")).strip().casefold() != str(row.correct_answer).strip().casefold()}
    result = SkillTestResult(user_id=user["id"], career_id=payload.career_id, score=score, skill_gaps=gaps)
    db.add(result)
    db.commit()
    db.refresh(result)
    return {"id": result.id, "career_id": result.career_id, "score": result.score, "skill_gaps": result.skill_gaps, "tested_at": result.tested_at}


@app.get("/api/roadmap/skill-tests/results")
def my_skill_results(db: Session = Depends(get_db), user: dict = Depends(authenticated_user)):
    rows = db.scalars(select(SkillTestResult).where(SkillTestResult.user_id == user["id"]).order_by(SkillTestResult.tested_at.desc())).all()
    return [{"id": row.id, "career_id": row.career_id, "score": row.score, "skill_gaps": row.skill_gaps, "tested_at": row.tested_at} for row in rows]


@app.get("/api/roadmap")
def my_roadmaps(db: Session = Depends(get_db), user: dict = Depends(authenticated_user)):
    rows = db.scalars(select(Roadmap).where(Roadmap.user_id == user["id"]).order_by(Roadmap.generated_at.desc())).all()
    return [{"id": row.id, "career_id": row.career_id, "user_segment": row.user_segment, "steps": row.steps, "generated_at": row.generated_at} for row in rows]


@app.get("/api/roadmap/{roadmap_id}")
def roadmap_detail(roadmap_id: str, db: Session = Depends(get_db), user: dict = Depends(authenticated_user)):
    row = db.scalar(select(Roadmap).where(Roadmap.id == roadmap_id, Roadmap.user_id == user["id"]))
    if not row:
        raise HTTPException(404, "Không tìm thấy roadmap")
    return {"id": row.id, "career_id": row.career_id, "skill_test_result_id": row.skill_test_result_id, "user_segment": row.user_segment, "steps": row.steps, "generated_at": row.generated_at}
