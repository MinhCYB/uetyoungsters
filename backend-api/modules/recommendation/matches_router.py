from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from modules.auth.dependencies import current_user
from modules.auth.models import User

from .models import CareerCatalogItem, MatchedResult, MatchedResultItem

router = APIRouter()


def _serialize(db: Session, result: MatchedResult) -> dict:
    rows = db.scalars(select(MatchedResultItem).where(MatchedResultItem.matched_result_id == result.id).order_by(MatchedResultItem.rank)).all()
    careers = {row.id: row for row in db.scalars(select(CareerCatalogItem).where(CareerCatalogItem.id.in_([item.career_id for item in rows]))).all()} if rows else {}
    return {
        "id": result.id,
        "assessment_id": result.assessment_id,
        "riasec_scores": result.riasec_scores,
        "taxonomy_version": result.taxonomy_version,
        "computed_at": result.computed_at,
        "items": [{
            "career_id": item.career_id,
            "career_title": careers[item.career_id].canonical_name if item.career_id in careers else None,
            "score": item.score,
            "rank": item.rank,
            "explanation": item.explanation,
        } for item in rows],
    }


@router.get("")
def my_recommendations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(MatchedResult).where(MatchedResult.user_id == user.id).order_by(MatchedResult.computed_at.desc())).all()
    return [_serialize(db, row) for row in rows]


@router.get("/{result_id}")
def recommendation_detail(result_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(MatchedResult).where(MatchedResult.id == result_id, MatchedResult.user_id == user.id))
    if not row:
        raise HTTPException(404, "Không tìm thấy kết quả gợi ý nghề nghiệp")
    return _serialize(db, row)
