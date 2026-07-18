"""FastAPI routes for the Student Companion golden path."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .schemas import AnalyzeRequest, ExpandPlanRequest, FeedbackRequest, FollowupRequest, PlanRequest, ReassessmentRequest
from .service import CompanionError, companion_service


router = APIRouter(prefix="/api/companion", tags=["companion"])


def _error(exc: CompanionError | ValidationError) -> JSONResponse:
    if isinstance(exc, CompanionError):
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message, "details": []}})
    return JSONResponse(status_code=422, content={"error": {"code": "contract_validation_failed", "message": "Request does not satisfy the Companion contract.", "details": exc.errors(include_url=False)}})


@router.post("/analyze")
def analyze(payload: AnalyzeRequest):
    try:
        return companion_service.analyze(**payload.model_dump())
    except (CompanionError, ValidationError) as exc:
        return _error(exc)


@router.post("/plan")
def plan(payload: PlanRequest):
    try:
        return companion_service.generate_plan(payload.analysis_id)
    except (CompanionError, ValidationError) as exc:
        return _error(exc)


@router.post("/followup")
def followup(payload: FollowupRequest):
    try:
        return companion_service.followup(**payload.model_dump())
    except (CompanionError, ValidationError) as exc:
        return _error(exc)


@router.post("/content/expand-plan")
def expand_plan(payload: ExpandPlanRequest):
    try:
        return companion_service.expand_plan(payload.plan_id, payload.task_id, payload.max_steps)
    except (CompanionError, ValidationError) as exc:
        return _error(exc)


@router.post("/content/reassessment")
def reassessment(payload: ReassessmentRequest):
    try:
        return companion_service.reassessment(payload.plan_id, payload.target_skill_id, payload.question_count, payload.max_score)
    except (CompanionError, ValidationError) as exc:
        return _error(exc)


@router.post("/content/feedback")
def feedback(payload: FeedbackRequest):
    try:
        return companion_service.feedback(payload)
    except (CompanionError, ValidationError) as exc:
        return _error(exc)


@router.post("/reset")
def reset():
    companion_service.store.reset()
    return {"status": "reset", "message": "Demo state cleared."}
