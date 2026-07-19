from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_type: str
    original_filename: str
    mime_type: str | None
    size_bytes: int | None
    extraction_status: str
    uploaded_at: datetime


class DocumentDetail(DocumentSummary):
    checksum: str | None
    extracted_text: str | None
    structured_data: dict
    extraction_version: str | None
    updated_at: datetime


class DocumentDownload(BaseModel):
    url: str
    expires_in: int
