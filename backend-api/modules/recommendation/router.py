"""Public career catalog queried from PostgreSQL."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db

from .models import CareerAlias, CareerCatalogItem
from .repository import search_catalog
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


@router.get("/search")
def search_careers(
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total, matches = search_catalog(db, q, limit)
    return {
        "query": q,
        "total": total,
        "items": [{"id": item.id, "title": item.canonical_name} for item in matches],
    }


@router.get("/{career_id}")
def career_detail(career_id: str, db: Session = Depends(get_db)):
    item = db.get(CareerCatalogItem, career_id)
    if not item or not item.active:
        raise HTTPException(404, "Không tìm thấy nghề nghiệp")
    aliases = [row.alias for row in db.query(CareerAlias).filter_by(career_id=item.id).order_by(CareerAlias.alias)]
    return {
        "id": item.id,
        "title": item.canonical_name,
        "taxonomy_version": item.taxonomy_version,
        "aliases": aliases,
        **(item.metadata_json or {}),
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
