"""Public career catalog backed by the canonical taxonomy."""

import json
import os
import unicodedata
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from database import get_db

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


def _crawl_schema() -> str:
    schema = os.getenv("CRAWL_DATABASE_SCHEMA", "").strip()
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise RuntimeError("CRAWL_DATABASE_SCHEMA must be configured as a lowercase SQL identifier")
    return schema


@router.get("/{career_id}")
def career_detail(career_id: str, db: Session = Depends(get_db)):
    """Return the latest evidence-backed career profile from the crawl warehouse."""
    catalog_item = next((item for item in career_catalog() if item["id"] == career_id), None)
    if not catalog_item:
        raise HTTPException(status_code=404, detail="Không tìm thấy nghề trong taxonomy")
    try:
        schema = _crawl_schema()
        profile = db.execute(
            text(f'SELECT * FROM "{schema}".career_profiles WHERE career_id = :career_id'),
            {"career_id": career_id},
        ).mappings().first()
        if not profile:
            raise HTTPException(status_code=404, detail="Nghề chưa có profile đã publish")
        sources = db.execute(text(
            f'SELECT evidence_id, source_name, source_type, source_url, title, collected_at '
            f'FROM "{schema}".career_evidence WHERE career_id = :career_id '
            'ORDER BY collected_at DESC NULLS LAST LIMIT 10'
        ), {"career_id": career_id}).mappings().all()
    except HTTPException:
        raise
    except (RuntimeError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail=f"Career warehouse chưa sẵn sàng: {exc}") from exc
    result = dict(profile)
    result["sources"] = [dict(source) for source in sources]
    return result
