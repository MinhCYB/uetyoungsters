"""Public career catalog queried from PostgreSQL."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db

from .models import CareerAlias, CareerCatalogItem
from .repository import search_catalog

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
