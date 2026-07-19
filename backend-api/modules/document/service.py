from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from modules.candidate.models import CandidateProfile

from .extraction import extract_document
from .models import ProfileDocument
from .repository import get_owned_document, list_owned_documents
from .storage import document_storage

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def documents_for_user(db: Session, user_id: str):
    profile = db.query(CandidateProfile).filter_by(user_id=user_id).one_or_none()
    if not profile:
        return []
    return list_owned_documents(db, profile.id)


def profile_for_user(db: Session, user_id: str) -> CandidateProfile:
    profile = db.query(CandidateProfile).filter_by(user_id=user_id).one_or_none()
    if not profile:
        raise HTTPException(422, "Người dùng chưa có candidate profile")
    return profile


def upload_document(db: Session, user_id: str, upload: UploadFile) -> ProfileDocument:
    profile = profile_for_user(db, user_id)
    filename = Path(upload.filename or "document").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Chỉ hỗ trợ PDF, DOC, DOCX hoặc TXT")
    content = upload.file.read(MAX_DOCUMENT_BYTES + 1)
    if not content:
        raise HTTPException(422, "Tệp tải lên đang trống")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(413, "Tệp CV không được vượt quá 10 MB")
    document_id = str(uuid4())
    object_key = f"profiles/{profile.id}/documents/{document_id}/{filename}"
    mime_type = upload.content_type or "application/octet-stream"
    document_storage().put(object_key, content, mime_type)
    row = ProfileDocument(
        id=document_id,
        candidate_profile_id=profile.id,
        document_type="CV",
        original_filename=filename,
        object_key=object_key,
        mime_type=mime_type,
        size_bytes=len(content),
        checksum=sha256(content).hexdigest(),
        extraction_status="pending",
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        document_storage().delete(object_key)
        raise
    return row


def process_document(db: Session, document_id: str) -> None:
    row = db.get(ProfileDocument, document_id)
    if not row or row.extraction_status == "completed":
        return
    row.extraction_status = "processing"
    db.commit()
    try:
        content = document_storage().get(row.object_key)
        text, structured = extract_document(row.original_filename, content)
        row.extracted_text = text
        row.structured_data = structured
        row.extraction_version = "local-parser-1.0.0"
        row.extraction_status = "completed"
        db.commit()
    except Exception as error:
        db.rollback()
        row = db.get(ProfileDocument, document_id)
        if row:
            row.extraction_status = "failed"
            row.structured_data = {"error": str(error)[:500]}
            db.commit()


def retry_document(db: Session, user_id: str, document_id: str) -> ProfileDocument:
    profile = profile_for_user(db, user_id)
    row = get_owned_document(db, document_id, profile.id)
    if not row:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    row.extraction_status = "pending"
    row.structured_data = {}
    db.commit()
    db.refresh(row)
    return row


def delete_document(db: Session, user_id: str, document_id: str) -> None:
    profile = profile_for_user(db, user_id)
    row = get_owned_document(db, document_id, profile.id)
    if not row:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    object_key = row.object_key
    db.delete(row)
    db.commit()
    document_storage().delete(object_key)


def document_for_user(db: Session, user_id: str, document_id: str) -> ProfileDocument:
    profile = profile_for_user(db, user_id)
    row = get_owned_document(db, document_id, profile.id)
    if not row:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    return row


def download_url(db: Session, user_id: str, document_id: str) -> str:
    row = document_for_user(db, user_id, document_id)
    return document_storage().presigned_get(row.object_key, timedelta(minutes=15))
