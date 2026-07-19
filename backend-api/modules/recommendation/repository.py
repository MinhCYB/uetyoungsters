import unicodedata

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import CareerAlias, CareerCatalogItem


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def import_catalog(db: Session, payload: dict) -> int:
    version = payload["taxonomy_version"]
    imported = 0
    for item in payload.get("careers", []):
        career_id = item["career_id"]
        aliases = item.get("aliases", [])
        search_text = normalize(" ".join([item["canonical_name"], *aliases]))
        row = db.get(CareerCatalogItem, career_id)
        values = dict(canonical_name=item["canonical_name"], search_text=search_text,
                      taxonomy_version=version, active=True,
                      metadata_json={key: value for key, value in item.items() if key not in {"career_id", "canonical_name", "aliases"}})
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            db.add(CareerCatalogItem(id=career_id, **values))
        db.flush()
        db.query(CareerAlias).filter_by(career_id=career_id).delete()
        seen_aliases = set()
        for alias in aliases:
            normalized_alias = normalize(alias)
            if normalized_alias in seen_aliases:
                continue
            seen_aliases.add(normalized_alias)
            db.add(CareerAlias(career_id=career_id, alias=alias, normalized_alias=normalized_alias))
        imported += 1
    db.commit()
    return imported


def search_catalog(db: Session, query: str, limit: int) -> tuple[int, list[CareerCatalogItem]]:
    term = normalize(query.strip())
    base = db.query(CareerCatalogItem).filter(CareerCatalogItem.active.is_(True))
    if term:
        pattern = f"%{term}%"
        base = base.filter(or_(CareerCatalogItem.search_text.ilike(pattern), CareerCatalogItem.canonical_name.ilike(pattern)))
    total = base.count()
    return total, base.order_by(CareerCatalogItem.canonical_name).limit(limit).all()
