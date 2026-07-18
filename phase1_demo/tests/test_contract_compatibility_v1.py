from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from phase1_demo.student_companion.application.facade import StudentCompanionFacade
from phase1_demo.student_companion.application.service import DemoService
from phase1_demo.student_companion.contracts import (
    CONTRACT_VERSION,
    ContractWarning,
    FollowupEvaluationRequest,
    FollowupEvaluationResponse,
    InitialAnalysisRequest,
    InitialAnalysisResponse,
    PlanGenerationRequest,
    PlanGenerationResponse,
)


EXAMPLE_ROOT = Path("phase1_demo/integration_examples")
CONTRACT_MODELS = {
    "initial_analysis_request.json": InitialAnalysisRequest,
    "initial_analysis_response.json": InitialAnalysisResponse,
    "plan_generation_request.json": PlanGenerationRequest,
    "plan_generation_response.json": PlanGenerationResponse,
    "followup_evaluation_request.json": FollowupEvaluationRequest,
    "followup_evaluation_response.json": FollowupEvaluationResponse,
}
SCHEMA_FINGERPRINTS = {
    InitialAnalysisRequest: "5a0b207c2dce301589b59288b060d5dc413386be6d3a4efeedb7c0b61f603679",
    InitialAnalysisResponse: "97ef44f8192682798e97745865be28cd070ed25360de8f9d03976f49cfec6535",
    PlanGenerationRequest: "e6ddf278f633d0769253b12ff5cb63c866088aff7a573478c1e55abb10cfb0bb",
    PlanGenerationResponse: "44aa2fadf1f917cac72e9ddef5ac409b5009e8c1faf37265657048521995e17c",
    FollowupEvaluationRequest: "642fa97a94fae68f74371923ca0c6e89d9576f8b1d96ccd0ca479b0b388de1ea",
    FollowupEvaluationResponse: "bc658a3b378a88b96fc553063e646f6ae4cfe38b309adeff9325bbdaa844610a",
}


def _stable_schema(value):
    if isinstance(value, dict):
        return {
            key: _stable_schema(item)
            for key, item in value.items()
            if key not in {"title", "description"}
        }
    if isinstance(value, list):
        return [_stable_schema(item) for item in value]
    return value


@pytest.mark.parametrize("filename,model", CONTRACT_MODELS.items())
def test_v1_integration_example_still_parses(filename: str, model) -> None:
    payload = (EXAMPLE_ROOT / filename).read_text(encoding="utf-8")
    restored = model.model_validate_json(payload)
    assert restored.metadata.contract_version == "1.0.0"


@pytest.mark.parametrize("model,expected", SCHEMA_FINGERPRINTS.items())
def test_v1_public_schema_fingerprint_is_frozen(model, expected: str) -> None:
    schema = json.dumps(
        _stable_schema(model.model_json_schema()),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(schema).hexdigest() == expected


def test_contract_version_remains_1_0_0() -> None:
    assert CONTRACT_VERSION == "1.0.0"


@pytest.mark.parametrize(
    "method_name,request_name,response_name",
    [
        ("analyze", "InitialAnalysisRequest", "InitialAnalysisResponse"),
        ("generate_plan", "PlanGenerationRequest", "PlanGenerationResponse"),
        ("evaluate_followup", "FollowupEvaluationRequest", "FollowupEvaluationResponse"),
    ],
)
def test_facade_signature_is_frozen(
    method_name: str, request_name: str, response_name: str
) -> None:
    signature = inspect.signature(getattr(StudentCompanionFacade, method_name))
    assert list(signature.parameters) == ["self", "request"]
    assert request_name in str(signature.parameters["request"].annotation)
    assert response_name in str(signature.return_annotation)


def test_new_warning_rules_use_public_contract_warning() -> None:
    warning = ContractWarning(
        warning_code="conflicting_evidence",
        message="Evidence sources differ substantially.",
        affected_field="ability_profile.SKILL_TEST",
    )
    assert type(warning) is ContractWarning


def test_internal_policy_is_not_exposed_in_public_examples() -> None:
    combined = "".join(
        path.read_text(encoding="utf-8") for path in sorted(EXAMPLE_ROOT.glob("*.json"))
    )
    assert "priority_score" not in combined
    assert "conflict_threshold" not in combined
    assert "CONFIDENCE_POLICY" not in combined


def test_frontend_response_paths_remain_available() -> None:
    initial = InitialAnalysisResponse.model_validate_json(
        (EXAMPLE_ROOT / "initial_analysis_response.json").read_text(encoding="utf-8")
    )
    plan = PlanGenerationResponse.model_validate_json(
        (EXAMPLE_ROOT / "plan_generation_response.json").read_text(encoding="utf-8")
    )
    followup = FollowupEvaluationResponse.model_validate_json(
        (EXAMPLE_ROOT / "followup_evaluation_response.json").read_text(encoding="utf-8")
    )
    assert initial.ability_profile is not None and initial.gaps is not None
    assert plan.plan.tasks is not None
    assert followup.updated_gaps is not None and followup.current_snapshot is not None


def test_demo_service_still_reaches_advanced_stage() -> None:
    service = DemoService()
    service.analyze_initial_state()
    service.generate_weekly_plan()
    state = service.advance_two_weeks()
    assert state["stage"] == "advanced"
