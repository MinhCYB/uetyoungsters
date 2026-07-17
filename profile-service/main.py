"""
Entrypoint FastAPI app cua profile-service.
"""
from fastapi import FastAPI

app = FastAPI(title="Career Compass - Profile Service")


@app.get("/health")
def health():
    return {"status": "ok"}
