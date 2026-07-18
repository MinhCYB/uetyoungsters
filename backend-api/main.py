"""Career Compass backend API — modular monolith entry point."""

from fastapi import FastAPI

app = FastAPI(title="Career Compass API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend-api"}
