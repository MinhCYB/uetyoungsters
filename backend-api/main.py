from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from modules.assessment.router import router as assessment_router
from modules.recommendation.router import router as career_router

app = FastAPI(title="Career Compass API", version="0.1.0")


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(assessment_router, prefix="/api/assessment", tags=["assessment"])
app.include_router(career_router, prefix="/api/careers", tags=["careers"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend-api"}
