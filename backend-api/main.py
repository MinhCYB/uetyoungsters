from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from modules.auth import models
from modules.auth.provisioning import router as provisioning_router
from modules.auth.router import router as auth_router

Base.metadata.create_all(engine)
app = FastAPI(title="Career Compass API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(provisioning_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend-api"}
