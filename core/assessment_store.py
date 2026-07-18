"""Database access for normalized question-bank and assessment data."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import (Assessment, AssessmentAnswer, BlueprintRule, Question, QuestionBankVersion,
                    QuestionBlueprint, QuestionCondition, QuestionOption, QuestionScale)


STRUCTURAL_KEYS = {"id", "section", "category", "prompt", "type", "order", "required", "scored", "scale_id", "options", "display_if"}


def import_question_bank(db: Session, bank: dict, status: str = "published") -> None:
    """Replace one version atomically from the in-memory Markdown parse result."""
    version = bank["schema_version"]
    existing = db.get(QuestionBankVersion, version)
    metadata = {"rubrics": bank["rubrics"], "sources": bank["sources"], "selection_rules": bank["selection_rules"]}
    if existing:
        existing.title, existing.language, existing.disclaimer = bank["title"], bank["language"], bank.get("disclaimer")
        existing.metadata_json = metadata
        existing.status = status
        existing.published_at = datetime.now(timezone.utc) if status == "published" else None
    else:
        db.add(QuestionBankVersion(version=version, title=bank["title"], language=bank["language"], disclaimer=bank.get("disclaimer"), status=status, metadata_json=metadata, published_at=datetime.now(timezone.utc) if status == "published" else None))
    db.flush()

    old_ids = [row.id for row in db.query(Question).filter_by(version=version).all()]
    if old_ids:
        db.query(QuestionCondition).filter(QuestionCondition.question_id.in_(old_ids)).delete(synchronize_session=False)
        db.query(QuestionOption).filter(QuestionOption.question_id.in_(old_ids)).delete(synchronize_session=False)
        db.query(Question).filter(Question.id.in_(old_ids)).delete(synchronize_session=False)
    for scale_id, scale in bank["scales"].items():
        db.merge(QuestionScale(id=scale_id, version=version, minimum=scale["min"], maximum=scale["max"], labels=scale["labels"]))
    for section, questions in bank["sections"].items():
        for question_id, item in questions.items():
            config = {key: value for key, value in item.items() if key not in STRUCTURAL_KEYS and value is not None}
            db.add(Question(id=question_id, version=version, section=section, category=item.get("category", "general"), prompt=item["prompt"], question_type=item["type"], order_index=item.get("order"), required=item.get("required", True), scored=item.get("scored", False), scale_id=item.get("scale_id"), config=config, active=True))
            for index, option in enumerate(item.get("options") or []):
                value = option.get("value") if isinstance(option, dict) else option
                label = option.get("label") if isinstance(option, dict) else option
                db.add(QuestionOption(question_id=question_id, value=str(value), label=str(label), order_index=index))
            if condition := item.get("display_if"):
                db.add(QuestionCondition(question_id=question_id, depends_on_question_id=condition["question_id"], operator=condition["operator"], expected_value=condition["value"]))
    for blueprint_id, rules in bank["generation_blueprints"].items():
        db.query(BlueprintRule).filter_by(blueprint_id=blueprint_id).delete()
        db.merge(QuestionBlueprint(id=blueprint_id, version=version, active=True))
        db.flush()
        for index, (section_key, rule) in enumerate(rules.items()):
            db.add(BlueprintRule(blueprint_id=blueprint_id, section_key=section_key, order_index=index, rule_config=rule))
    db.commit()


def load_question_bank(db: Session) -> dict:
    version = db.query(QuestionBankVersion).filter_by(status="published").order_by(QuestionBankVersion.published_at.desc()).first()
    if not version:
        raise RuntimeError("No published question bank. Run scripts/build_question_bank.py --database-url ...")
    bank = {"schema_version": version.version, "title": version.title, "language": version.language, "disclaimer": version.disclaimer, **version.metadata_json, "sections": {}, "scales": {}, "generation_blueprints": {}}
    for scale in db.query(QuestionScale).filter_by(version=version.version):
        bank["scales"][scale.id] = {"min": scale.minimum, "max": scale.maximum, "labels": scale.labels}
    conditions = {row.question_id: row for row in db.query(QuestionCondition).all()}
    option_rows = db.query(QuestionOption).order_by(QuestionOption.order_index).all()
    options = {}
    for row in option_rows:
        options.setdefault(row.question_id, []).append({"value": row.value, "label": row.label})
    for row in db.query(Question).filter_by(version=version.version, active=True):
        item = {"id": row.id, "section": row.section, "category": row.category, "prompt": row.prompt, "type": row.question_type, "required": row.required, "scored": row.scored, **(row.config or {})}
        if row.order_index is not None: item["order"] = row.order_index
        if row.scale_id: item["scale_id"] = row.scale_id
        if row.id in options: item["options"] = options[row.id]
        if condition := conditions.get(row.id): item["display_if"] = {"question_id": condition.depends_on_question_id, "operator": condition.operator, "value": condition.expected_value}
        bank["sections"].setdefault(row.section, {})[row.id] = item
    for blueprint in db.query(QuestionBlueprint).filter_by(version=version.version, active=True):
        bank["generation_blueprints"][blueprint.id] = {row.section_key: row.rule_config for row in db.query(BlueprintRule).filter_by(blueprint_id=blueprint.id).order_by(BlueprintRule.order_index)}
    return bank


def save_assessment(db: Session, *, assessment_id: str, **values) -> None:
    db.add(Assessment(id=assessment_id, **values)); db.commit()


def save_answers(db: Session, assessment: Assessment, questions: dict, responses: dict) -> None:
    db.query(AssessmentAnswer).filter_by(assessment_id=assessment.id).delete()
    for question_id, answer in responses.items():
        db.add(AssessmentAnswer(assessment_id=assessment.id, question_id=question_id, question_type=questions[question_id]["type"], answer=answer))
    assessment.status, assessment.submitted_at = "submitted", datetime.now(timezone.utc)
    db.commit()
