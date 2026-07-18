"""Router FastAPI cho module khảo sát hướng nghiệp (assessment)."""
from hashlib import sha256
from secrets import randbits
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from .store import load_question_bank, save_answers, save_assessment
from database import get_db
from .models import Assessment
from modules.auth.dependencies import current_user
from modules.auth.models import User
from .question_bank import generate_question_set, get_question

router = APIRouter()


def _frontend_question(question: dict, bank: dict) -> dict:
    """Enrich a bank item with the scale and referenced child items needed by UI."""
    item = dict(question)
    scale_id = item.get("scale_id")
    item["scale"] = bank["scales"].get(scale_id) if scale_id else None
    if item.get("item_ids"):
        item["items"] = [child for child_id in item["item_ids"] if (child := get_question(child_id, bank=bank))]
    item["required"] = item.get("required", True)
    return item


def _question_set_id(mode: str, seed: int, ids: list[str], assessment_id: str) -> str:
    digest = sha256(f"{assessment_id}:{mode}:{seed}:{','.join(ids)}".encode()).hexdigest()[:16]
    return f"qs_{digest}"


def _is_visible(question: dict, responses: dict[str, Any]) -> bool:
    condition = question.get("display_if")
    if not condition:
        return True
    answer = responses.get(condition["question_id"])
    operator, expected = condition["operator"], condition["value"]
    if operator == "equals":
        return answer == expected
    if operator == "not_equals":
        return answer not in (None, "") and answer != expected
    if operator == "in":
        return answer in expected
    return False


def _option_values(question: dict) -> list[Any]:
    return [option.get("value") if isinstance(option, dict) else option for option in question.get("options") or []]


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _validate_answer(question: dict, value: Any) -> str | None:
    question_type = question["type"]
    if question_type in ("single_choice", "value_item"):
        if value not in _option_values(question):
            return "Lựa chọn không thuộc danh sách cho phép"
    elif question_type == "multi_choice":
        if not isinstance(value, list) or len(value) != len(set(map(str, value))):
            return "Câu trả lời phải là danh sách lựa chọn không trùng"
        if any(item not in _option_values(question) for item in value):
            return "Danh sách chứa lựa chọn không hợp lệ"
        if question.get("min_selections") and len(value) < question["min_selections"]:
            return f"Cần chọn ít nhất {question['min_selections']} mục"
        if question.get("max_selections") and len(value) > question["max_selections"]:
            return f"Chỉ được chọn tối đa {question['max_selections']} mục"
    elif question_type in ("likert_5", "number"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "Giá trị phải là một số"
        scale = question.get("scale") or {}
        minimum = question.get("min", scale.get("min"))
        maximum = question.get("max", scale.get("max"))
        if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
            return f"Giá trị phải nằm trong khoảng {minimum}–{maximum}"
    elif question_type == "ranking":
        allowed = set(question.get("item_ids") or [])
        if not isinstance(value, list) or len(value) != question.get("required_count", 5):
            return f"Phải xếp hạng đúng {question.get('required_count', 5)} mục"
        if len(value) != len(set(value)) or any(item not in allowed for item in value):
            return "Danh sách xếp hạng chứa mục trùng hoặc không hợp lệ"
    elif question_type == "point_allocation":
        if not isinstance(value, dict) or set(value) != set(_option_values(question)):
            return "Phải phân bổ điểm cho đúng tất cả nhóm giá trị"
        if any(isinstance(points, bool) or not isinstance(points, (int, float)) or points < 0 for points in value.values()):
            return "Điểm phân bổ phải là số không âm"
        if abs(sum(value.values()) - question.get("total_points", 100)) > 0.001:
            return f"Tổng điểm phải bằng {question.get('total_points', 100)}"
    elif question_type == "tradeoff_group":
        required_ids = set(question.get("item_ids") or [])
        if not isinstance(value, dict) or set(value) != required_ids or any(not str(answer).strip() for answer in value.values()):
            return "Phải trả lời đầy đủ tất cả tình huống đánh đổi"
        min_words = question.get("min_words_per_item", 1)
        min_chars = question.get("min_chars_per_item", 1)
        if any(len(str(answer).split()) < min_words or len(str(answer).strip()) < min_chars for answer in value.values()):
            return f"Mỗi tình huống cần ít nhất {min_words} từ và {min_chars} ký tự"
    elif question_type in ("open_text", "performance_task"):
        if not isinstance(value, str):
            return "Câu trả lời phải là văn bản"
        text = value.strip()
        word_count = len(text.split())
        if word_count < question.get("min_words", 1) or len(text) < question.get("min_chars", 1):
            return f"Câu trả lời cần ít nhất {question.get('min_words', 1)} từ và {question.get('min_chars', 1)} ký tự"
        if question.get("max_words") and word_count > question["max_words"]:
            return f"Câu trả lời không được vượt quá {question['max_words']} từ"
    return None


class AssessmentSubmission(BaseModel):
    assessment_id: str
    question_set_id: str
    mode: str = "standard_25_35_min"
    seed: int
    responses: dict[str, Any] = Field(default_factory=dict)


@router.get("/questions")
def create_assessment_question_set(
    mode: str = Query(default="standard_25_35_min"),
    seed: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Create a balanced question set from the versioned question bank."""
    actual_seed = seed if isinstance(seed, int) else randbits(63)
    try:
        bank = load_question_bank(db)
        generated = generate_question_set(mode=mode, seed=actual_seed, bank=bank)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    ids = generated["question_ids"]
    assessment_id = str(uuid4())
    question_set_id = _question_set_id(mode, actual_seed, ids, assessment_id)
    save_assessment(db, assessment_id=assessment_id, question_set_id=question_set_id, mode=mode, seed=actual_seed, schema_version=bank["schema_version"], question_ids=ids, user_id=user.id, tenant_id=user.tenant_id)
    return {
        "assessment_id": assessment_id,
        "question_set_id": question_set_id,
        "mode": mode,
        "seed": actual_seed,
        "schema_version": bank["schema_version"],
        "questions": [_frontend_question(question, bank) for question in generated["questions"]],
        "ai_instructions": generated["ai_instructions"],
    }


@router.post("/submit")
def submit_assessment(submission: AssessmentSubmission, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Rebuild and validate a submitted assessment without trusting client flow."""
    try:
        bank = load_question_bank(db)
        generated = generate_question_set(mode=submission.mode, seed=submission.seed, bank=bank)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    assessment = db.get(Assessment, submission.assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên khảo sát tương ứng trong database")
    expected_set_id = _question_set_id(submission.mode, submission.seed, generated["question_ids"], assessment.id)
    if submission.question_set_id != expected_set_id:
        raise HTTPException(status_code=409, detail="question_set_id không khớp mode và seed")

    if assessment.question_set_id != expected_set_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên khảo sát tương ứng trong database")
    if assessment.mode != submission.mode or assessment.seed != submission.seed or assessment.question_ids != generated["question_ids"]:
        raise HTTPException(status_code=409, detail="Thông tin bộ đề không khớp bản đã phát hành")

    questions = {item["id"]: _frontend_question(item, bank) for item in generated["questions"]}
    unknown_ids = sorted(set(submission.responses) - set(questions))
    errors = [{"question_id": question_id, "error": "ID câu hỏi không thuộc bộ đề"} for question_id in unknown_ids]
    sanitized = {}
    for question_id, question in questions.items():
        visible = _is_visible(question, submission.responses)
        supplied = question_id in submission.responses and not _is_empty(submission.responses[question_id])
        if not visible:
            if question_id in submission.responses:
                errors.append({"question_id": question_id, "error": "Không được gửi câu trả lời cho câu hỏi bị ẩn bởi flow"})
            continue
        if question.get("required", True) and not supplied:
            errors.append({"question_id": question_id, "error": "Câu hỏi bắt buộc chưa được trả lời"})
            continue
        if not supplied:
            continue
        value = submission.responses[question_id]
        if error := _validate_answer(question, value):
            errors.append({"question_id": question_id, "error": error})
        else:
            sanitized[question_id] = value
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Bài nộp không hợp lệ", "errors": errors})
    save_answers(db, assessment, questions, sanitized)
    return {
        "status": "accepted",
        "assessment_id": assessment.id,
        "question_set_id": expected_set_id,
        "answer_count": len(sanitized),
        "responses": sanitized,
    }
