import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db
from modules.assessment.router import router as assessment_router
from modules.auth.provisioning import router as provisioning_router
from modules.auth.router import router as auth_router
from modules.companion.router import router as companion_router
from modules.recommendation.router import router as career_router

app = FastAPI(title="Career Compass API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/companion"):
        return JSONResponse(status_code=422, content={"error": {"code": "contract_validation_failed", "message": "Request does not satisfy the Companion contract.", "details": exc.errors()}})
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.on_event("startup")
def on_startup():
    if os.getenv("SKIP_DB_INIT") != "1":
        init_db()


app.include_router(assessment_router, prefix="/api/assessment", tags=["assessment"])
app.include_router(career_router, prefix="/api/careers", tags=["careers"])
app.include_router(auth_router)
app.include_router(provisioning_router)
app.include_router(companion_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend-api"}
