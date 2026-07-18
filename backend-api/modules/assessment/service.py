"""Application services for assessment creation, drafts, and submission."""
from datetime import datetime, timezone
from hashlib import sha256
from secrets import randbits
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.auth.models import User

from .models import Assessment, Question
from .question_bank import generate_question_set, get_question
from .repository import (delete_owned_assessment, get_owned_assessment, load_draft_answers,
                         load_question_bank, save_answers, save_assessment,
                         upsert_draft_answers)
from .schemas import AssessmentDraftUpdate, AssessmentSubmission
from .validation import is_empty, is_visible, validate_answer


class AssessmentServiceError(Exception):
    def __init__(self, status_code: int, detail):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def frontend_question(question: dict, bank: dict) -> dict:
    item = dict(question)
    scale_id = item.get("scale_id")
    item["scale"] = bank["scales"].get(scale_id) if scale_id else None
    if item.get("item_ids"):
        item["items"] = [child for child_id in item["item_ids"] if (child := get_question(child_id, bank=bank))]
    item["required"] = item.get("required", True)
    return item


def question_set_id(mode: str, seed: int, ids: list[str], assessment_id: str) -> str:
    digest = sha256(f"{assessment_id}:{mode}:{seed}:{','.join(ids)}".encode()).hexdigest()[:16]
    return f"qs_{digest}"


def owned_assessment(db: Session, assessment_id: str, user: User) -> Assessment:
    assessment = get_owned_assessment(db, assessment_id, user.id)
    if not assessment:
        raise AssessmentServiceError(404, "Không tìm thấy phiên khảo sát")
    return assessment


def draft_questions(db: Session, assessment: Assessment, question_ids: set[str]) -> dict[str, dict]:
    unknown_ids = sorted(question_ids - set(assessment.question_ids))
    if unknown_ids:
        raise AssessmentServiceError(422, {"message": "Câu hỏi không thuộc bộ đề", "question_ids": unknown_ids})
    rows = db.query(Question).filter(Question.id.in_(question_ids)).all() if question_ids else []
    questions = {row.id: {"type": row.question_type} for row in rows}
    missing_ids = sorted(question_ids - set(questions))
    if missing_ids:
        raise AssessmentServiceError(422, {"message": "Không tìm thấy câu hỏi", "question_ids": missing_ids})
    return questions


def get_draft(db: Session, assessment_id: str, user: User) -> dict:
    assessment = owned_assessment(db, assessment_id, user)
    return {
        "assessment_id": assessment.id,
        "question_set_id": assessment.question_set_id,
        "status": assessment.status,
        "version": assessment.version,
        "last_saved_at": assessment.last_saved_at.isoformat() if assessment.last_saved_at else None,
        "current_question_id": assessment.current_question_id,
        "responses": load_draft_answers(db, assessment.id),
    }


def delete_assessment(db: Session, assessment_id: str, user: User) -> None:
    delete_owned_assessment(db, owned_assessment(db, assessment_id, user))


def save_draft(db: Session, assessment_id: str, payload: AssessmentDraftUpdate, user: User) -> dict:
    assessment = owned_assessment(db, assessment_id, user)
    if assessment.status != "in_progress":
        raise AssessmentServiceError(409, "Bài đánh giá đã được nộp")
    if payload.question_set_id != assessment.question_set_id:
        raise AssessmentServiceError(409, "question_set_id không khớp phiên khảo sát")
    if payload.current_question_id and payload.current_question_id not in assessment.question_ids:
        raise AssessmentServiceError(422, "current_question_id không thuộc bộ đề")
    questions = draft_questions(db, assessment, set(payload.responses))
    saved_at = datetime.now(timezone.utc)
    saved = upsert_draft_answers(
        db, assessment, questions, payload.responses,
        expected_version=payload.version,
        current_question_id=payload.current_question_id,
        saved_at=saved_at,
    )
    if not saved:
        current = owned_assessment(db, assessment_id, user)
        raise AssessmentServiceError(409, {
            "message": "Draft đã được cập nhật ở phiên khác",
            "current_version": current.version,
            "last_saved_at": current.last_saved_at.isoformat() if current.last_saved_at else None,
        })
    return {
        "status": "saved",
        "assessment_id": assessment.id,
        "saved_count": len(payload.responses),
        "version": payload.version + 1,
        "current_question_id": payload.current_question_id,
        "saved_at": saved_at.isoformat(),
    }


def create_question_set(db: Session, user: User, mode: str, seed: int | None) -> dict:
    actual_seed = seed if isinstance(seed, int) else randbits(63)
    try:
        bank = load_question_bank(db)
        generated = generate_question_set(mode=mode, seed=actual_seed, bank=bank)
    except RuntimeError as error:
        raise AssessmentServiceError(503, str(error)) from error
    except ValueError as error:
        raise AssessmentServiceError(400, str(error)) from error
    ids = generated["question_ids"]
    assessment_id = str(uuid4())
    set_id = question_set_id(mode, actual_seed, ids, assessment_id)
    save_assessment(db, assessment_id=assessment_id, question_set_id=set_id, mode=mode, seed=actual_seed,
                    schema_version=bank["schema_version"], question_ids=ids, user_id=user.id, tenant_id=user.tenant_id)
    return {
        "assessment_id": assessment_id,
        "question_set_id": set_id,
        "mode": mode,
        "seed": actual_seed,
        "schema_version": bank["schema_version"],
        "version": 1,
        "last_saved_at": None,
        "current_question_id": None,
        "questions": [frontend_question(question, bank) for question in generated["questions"]],
        "ai_instructions": generated["ai_instructions"],
    }


def submit(db: Session, submission: AssessmentSubmission, user: User) -> dict:
    try:
        bank = load_question_bank(db)
        generated = generate_question_set(mode=submission.mode, seed=submission.seed, bank=bank)
    except RuntimeError as error:
        raise AssessmentServiceError(503, str(error)) from error
    except ValueError as error:
        raise AssessmentServiceError(400, str(error)) from error
    assessment = owned_assessment(db, submission.assessment_id, user)
    expected_set_id = question_set_id(submission.mode, submission.seed, generated["question_ids"], assessment.id)
    if submission.question_set_id != expected_set_id:
        raise AssessmentServiceError(409, "question_set_id không khớp mode và seed")
    if assessment.question_set_id != expected_set_id:
        raise AssessmentServiceError(404, "Không tìm thấy phiên khảo sát tương ứng trong database")
    if assessment.mode != submission.mode or assessment.seed != submission.seed or assessment.question_ids != generated["question_ids"]:
        raise AssessmentServiceError(409, "Thông tin bộ đề không khớp bản đã phát hành")

    questions = {item["id"]: frontend_question(item, bank) for item in generated["questions"]}
    unknown_ids = sorted(set(submission.responses) - set(questions))
    errors = [{"question_id": question_id, "error": "ID câu hỏi không thuộc bộ đề"} for question_id in unknown_ids]
    sanitized = {}
    for question_id, question in questions.items():
        visible = is_visible(question, submission.responses)
        supplied = question_id in submission.responses and not is_empty(submission.responses[question_id])
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
        if error := validate_answer(question, value):
            errors.append({"question_id": question_id, "error": error})
        else:
            sanitized[question_id] = value
    if errors:
        raise AssessmentServiceError(422, {"message": "Bài nộp không hợp lệ", "errors": errors})
    save_answers(db, assessment, questions, sanitized)
    return {
        "status": "accepted",
        "assessment_id": assessment.id,
        "question_set_id": expected_set_id,
        "answer_count": len(sanitized),
        "responses": sanitized,
    }
