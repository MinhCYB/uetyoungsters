import re
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


def _structured(text: str) -> dict:
    emails = sorted(set(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)))
    phones = sorted(set(re.findall(r"(?<!\d)(?:\+?84|0)[\d .-]{8,13}\d", text)))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "emails": emails,
        "phones": phones,
        "line_count": len(lines),
        "character_count": len(text),
        "preview": "\n".join(lines[:20]),
    }


def extract_document(filename: str, content: bytes) -> tuple[str, dict]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif extension == ".docx":
        document = Document(BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    elif extension == ".txt":
        text = content.decode("utf-8", errors="replace")
    elif extension == ".doc":
        raise ValueError("Định dạng DOC cũ đã được lưu nhưng cần chuyển sang DOCX hoặc PDF để trích xuất")
    else:
        raise ValueError("Định dạng tài liệu không được hỗ trợ")
    text = text.replace("\x00", "").strip()
    if not text:
        raise ValueError("Không trích xuất được văn bản; CV có thể là bản scan và cần OCR")
    return text, _structured(text)
