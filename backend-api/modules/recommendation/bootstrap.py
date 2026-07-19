import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from .models import CareerCatalogItem
from .repository import import_catalog


def ensure_career_catalog(db: Session) -> int:
    if db.query(CareerCatalogItem).count():
        return 0
    configured = os.getenv("CAREER_TAXONOMY_PATH")
    candidates = [
        Path(configured) if configured else None,
        Path(__file__).resolve().parents[2] / "data" / "taxonomy.json",
        Path(__file__).resolve().parents[3] / "crawl-service" / "data" / "taxonomy.json",
    ]
    path = next((candidate for candidate in candidates if candidate and candidate.exists()), None)
    if not path:
        return 0
    return import_catalog(db, json.loads(path.read_text(encoding="utf-8")))
