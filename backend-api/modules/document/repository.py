from sqlalchemy.orm import Session

from .models import ProfileDocument


def list_owned_documents(db: Session, candidate_profile_id: str) -> list[ProfileDocument]:
    return db.query(ProfileDocument).filter_by(candidate_profile_id=candidate_profile_id).order_by(ProfileDocument.uploaded_at.desc()).all()


def get_owned_document(db: Session, document_id: str, candidate_profile_id: str) -> ProfileDocument | None:
    return db.query(ProfileDocument).filter_by(id=document_id, candidate_profile_id=candidate_profile_id).one_or_none()
