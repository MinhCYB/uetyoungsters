"""Career Compass backend API — modular monolith entry point."""

from fastapi import FastAPI

from database import init_db
from modules.assessment.router import router as assessment_router

app = FastAPI(title="Career Compass API", version="0.1.0")


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(assessment_router, prefix="/api/assessment", tags=["assessment"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend-api"}
