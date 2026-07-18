"""Career Compass backend API — modular monolith entry point."""

from fastapi import FastAPI

from database import init_db
from modules.assessment.router import router as assessment_router
from modules.auth.router import router as auth_router
from modules.auth.provisioning import router as provisioning_router

app = FastAPI(title="Career Compass API", version="0.1.0")


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(assessment_router, prefix="/api/assessment", tags=["assessment"])
app.include_router(auth_router)  # already has prefix="/api/auth"
app.include_router(provisioning_router)  # routes use full paths, no extra prefix


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend-api"}

