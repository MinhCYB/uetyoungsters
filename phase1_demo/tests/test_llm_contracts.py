from __future__ import annotations

import pytest
from pydantic import ValidationError

from phase1_demo.student_companion.llm.contracts import (
    CONTENT_CONTRACT_VERSION,
    ContentGenerationMetadata,
    FeedbackGenerationRequest,
    PlanExpansionRequest,
    ReassessmentGenerationRequest,
)
from phase1_demo.tests.content_factory import (
    feedback_request,
    metadata,
    plan_request,
    reassessment_request,
)


def test_valid_plan_expansion_request() -> None:
    request = plan_request()
    assert request.task.estimated_minutes == 20
    assert request.metadata.content_contract_version == "1.0.0"


@pytest.mark.parametrize("grade", [9, 13])
def test_invalid_grade_level_is_rejected(grade: int) -> None:
    data = metadata("plan-expansion-1.0.0").model_dump()
    data["grade_level"] = grade
    with pytest.raises(ValidationError):
        ContentGenerationMetadata.model_validate(data)


def test_unsupported_content_contract_version_is_rejected() -> None:
    data = metadata("plan-expansion-1.0.0").model_dump()
    data["content_contract_version"] = "2.0.0"
    with pytest.raises(ValidationError):
        ContentGenerationMetadata.model_validate(data)


@pytest.mark.parametrize(
    "factory,model",
    [
        (plan_request, PlanExpansionRequest),
        (reassessment_request, ReassessmentGenerationRequest),
        (feedback_request, FeedbackGenerationRequest),
    ],
)
def test_content_request_json_round_trip(factory, model) -> None:
    original = factory()
    assert model.model_validate_json(original.model_dump_json()) == original


def test_content_contract_rejects_extra_field() -> None:
    data = plan_request().model_dump()
    data["raw_profile"] = {"private": True}
    with pytest.raises(ValidationError, match="Extra inputs"):
        PlanExpansionRequest.model_validate(data)


def test_content_request_serialization_is_deterministic() -> None:
    assert plan_request().model_dump_json() == plan_request().model_dump_json()


def test_content_contract_version_constant_is_stable() -> None:
    assert CONTENT_CONTRACT_VERSION == "1.0.0"


def test_reassessment_rejects_duplicate_prior_fingerprint() -> None:
    with pytest.raises(ValidationError, match="prior_question_fingerprints"):
        reassessment_request(prior_question_fingerprints=["same", "same"])


def test_feedback_rejects_more_than_one_followup_question() -> None:
    with pytest.raises(ValidationError):
        feedback_request(max_followup_questions=2)
