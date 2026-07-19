from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from modules.auth.dependencies import current_user
from modules.auth.models import Role, User

from database import SessionLocal
from .schemas import DocumentDetail, DocumentDownload, DocumentSummary
from .service import (delete_document, document_for_user, documents_for_user,
                      download_url, process_document, retry_document,
                      upload_document)

router = APIRouter()


def require_profile_document_access(user: User) -> None:
    if user.role == Role.STUDENT:
        raise HTTPException(403, "Hồ sơ học sinh/sinh viên do giáo viên quản lý; tài khoản người học chỉ làm bài đánh giá")


@router.get("", response_model=list[DocumentSummary])
def my_documents(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return documents_for_user(db, user.id)


def _process_in_background(document_id: str) -> None:
    with SessionLocal() as db:
        process_document(db, document_id)


@router.post("", response_model=DocumentSummary, status_code=201)
def upload_cv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_profile_document_access(user)
    row = upload_document(db, user.id, file)
    background_tasks.add_task(_process_in_background, row.id)
    return row


@router.get("/{document_id}", response_model=DocumentDetail)
def document_detail(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return document_for_user(db, user.id, document_id)


@router.get("/{document_id}/analysis-payload")
def document_analysis_payload(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = document_for_user(db, user.id, document_id)
    if row.extraction_status != "completed":
        from fastapi import HTTPException
        raise HTTPException(409, "CV chưa trích xuất xong")
    return {
        "schema_version": "1.0.0",
        "document_id": row.id,
        "document_type": row.document_type,
        "extraction_version": row.extraction_version,
        "checksum": row.checksum,
        "text": row.extracted_text,
        "structured_data": row.structured_data,
    }


@router.get("/{document_id}/download", response_model=DocumentDownload)
def document_download(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {"url": download_url(db, user.id, document_id), "expires_in": 900}


@router.post("/{document_id}/extract", response_model=DocumentSummary, status_code=202)
def retry_extraction(document_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_profile_document_access(user)
    row = retry_document(db, user.id, document_id)
    background_tasks.add_task(_process_in_background, row.id)
    return row


@router.delete("/{document_id}", status_code=204)
def remove_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_profile_document_access(user)
    delete_document(db, user.id, document_id)
    return Response(status_code=204)
