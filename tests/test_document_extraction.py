import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1] / "backend-api"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from modules.document.extraction import extract_document


def test_extract_text_cv_builds_safe_structured_metadata():
    text, structured = extract_document(
        "candidate.txt",
        b"Candidate Name\nEmail: candidate@example.com\nPhone: 0901234567\nPython and SQL",
    )

    assert "Python and SQL" in text
    assert structured["emails"] == ["candidate@example.com"]
    assert structured["phones"] == ["0901234567"]
    assert structured["character_count"] == len(text)


def test_legacy_doc_is_stored_but_requires_conversion_for_extraction():
    try:
        extract_document("legacy.doc", b"legacy-binary")
    except ValueError as error:
        assert "DOCX hoặc PDF" in str(error)
    else:
        raise AssertionError("Legacy DOC extraction must not silently succeed")
