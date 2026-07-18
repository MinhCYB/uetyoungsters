"""Public career catalog backed by the canonical taxonomy."""

import json
import os
import unicodedata
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter()


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


@lru_cache(maxsize=1)
def career_catalog() -> list[dict]:
    configured = os.getenv("CAREER_TAXONOMY_PATH")
    candidates = [
        Path(configured) if configured else None,
        Path(__file__).resolve().parents[2] / "data" / "taxonomy.json",
        Path(__file__).resolve().parents[3] / "crawl-service" / "data" / "taxonomy.json",
    ]
    path = next((item for item in candidates if item and item.exists()), None)
    if not path:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        {
            "id": item["career_id"],
            "title": item["canonical_name"],
            "aliases": item.get("aliases", []),
            "searchText": normalize(" ".join([item["canonical_name"], *item.get("aliases", [])])),
        }
        for item in payload.get("careers", [])
    ]


@router.get("/search")
def search_careers(q: str = Query(default="", max_length=120), limit: int = Query(default=20, ge=1, le=100)):
    """Search canonical careers by display name and aliases."""
    term = normalize(q.strip())
    matches = [item for item in career_catalog() if not term or term in item["searchText"]]
    return {
        "query": q,
        "total": len(matches),
        "items": [{"id": item["id"], "title": item["title"]} for item in matches[:limit]],
    }
