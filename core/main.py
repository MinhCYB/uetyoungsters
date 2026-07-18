"""
Entrypoint FastAPI app cua core.
"""
from fastapi import FastAPI

app = FastAPI(title="Career Compass - Core")


@app.get("/health")
def health():
    return {"status": "ok"}
