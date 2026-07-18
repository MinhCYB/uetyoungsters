from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

import phase1_demo.student_companion.application.facade as facade_module
from phase1_demo.scripts.export_contract_examples import export_contract_examples
from phase1_demo.student_companion.application import MarketContextProvider
from phase1_demo.student_companion.application.facade import StudentCompanionFacade
from phase1_demo.student_companion.contracts import (
    ContractMetadata,
    FollowupEvaluationRequest,
    InitialAnalysisRequest,
    InitialAnalysisResponse,
    PlanGenerationRequest,
)
from phase1_demo.student_companion.domain import MarketCareerGroup
from phase1_demo.student_companion.infrastructure.demo_contract_adapter import (
    DemoContractAdapter,
)
from phase1_demo.student_companion.infrastructure.market import (
    ReadOnlyMarketContextProvider,
)


EXAMPLE_ROOT = Path("phase1_demo/integration_examples")


class StubMarketProvider:
    def get_market_context(self, career_group_ids: list[str]) -> list[MarketCareerGroup]:
        records = {
            "CAREER_GROUP_DATA_AI": MarketCareerGroup(
                career_group_id="CAREER_GROUP_DATA_AI",
                display_name="Data/AI",
                market_signal="Deterministic test signal",
                sample_size=2,
                foundation_skill_ids=["SKILL_DATA_REASONING"],
                snapshot_version="test-market-v1",
                taxonomy_version="0.4.0",
                data_mode="pipeline_export",
                source_output_files=["test-market.json"],
            ),
            "CAREER_GROUP_ECONOMICS": MarketCareerGroup(
                career_group_id="CAREER_GROUP_ECONOMICS",
                display_name="Kinh tế",
                market_signal="Deterministic test signal",
                sample_size=8,
                foundation_skill_ids=["SKILL_DECISION_MAKING"],
                snapshot_version="test-market-v1",
                taxonomy_version="0.4.0",
                data_mode="pipeline_export",
                source_output_files=["test-market.json"],
            ),
        }
        return [records[item] for item in career_group_ids if item in records]


def _adapter() -> DemoContractAdapter:
    return DemoContractAdapter()


def _facade() -> StudentCompanionFacade:
    return StudentCompanionFacade(StubMarketProvider())


def _initial_response():
    request = _adapter().load_initial_request()
    return request, _facade().analyze(request)


def _planned_snapshot():
    request, response = _initial_response()
    plan_request = _adapter().load_plan_request(request.student, response.snapshot)
    plan_response = _facade().generate_plan(plan_request)
    return request, response.snapshot.model_copy(
        update={"active_plan": plan_response.plan},
        deep=True,
    )


def test_initial_analysis_request_is_valid() -> None:
    request = _adapter().load_initial_request()
    assert request.metadata.contract_version == "1.0.0"
    assert request.assessment_attempts[0].assessment_type.value == "pretest"


def test_nested_student_id_mismatch_is_rejected() -> None:
    request = _adapter().load_initial_request()
    data = request.model_dump()
    data["academic_records"][0]["student_id"] = "OTHER_STUDENT"
    with pytest.raises(ValidationError, match="nested student_id"):
        InitialAnalysisRequest.model_validate(data)


def test_duplicate_record_id_is_rejected() -> None:
    request = _adapter().load_initial_request()
    data = request.model_dump()
    data["academic_records"] = [
        data["academic_records"][0],
        data["academic_records"][0],
    ]
    with pytest.raises(ValidationError, match="duplicate IDs"):
        InitialAnalysisRequest.model_validate(data)


def test_missing_diagnostic_or_pretest_is_rejected() -> None:
    request = _adapter().load_initial_request()
    data = request.model_dump()
    data["assessment_attempts"][0]["assessment_type"] = "posttest"
    with pytest.raises(ValidationError, match="diagnostic or pretest"):
        InitialAnalysisRequest.model_validate(data)


def test_initial_facade_runs_from_public_contract() -> None:
    request, response = _initial_response()
    assert response.student_id == request.student.student_id
    assert response.snapshot.ability_profile == response.ability_profile
    assert response.snapshot.gaps == response.gaps
    assert response.market_context


def test_facade_has_no_fixture_or_server_dependency() -> None:
    source = inspect.getsource(facade_module).lower()
    assert "fixture" not in source
    assert "run_demo" not in source
    assert "demo_service" not in source


def test_facade_is_deterministic() -> None:
    request = _adapter().load_initial_request()
    first = _facade().analyze(request).model_dump_json()
    second = _facade().analyze(request).model_dump_json()
    assert first == second


def test_plan_request_student_mismatch_is_rejected() -> None:
    request, response = _initial_response()
    student = request.student.model_copy(update={"student_id": "OTHER_STUDENT"})
    with pytest.raises(ValidationError, match="snapshot.student_id"):
        PlanGenerationRequest(
            metadata=request.metadata,
            student=student,
            snapshot=response.snapshot,
            completed_activity_ids=[],
        )


def test_plan_response_does_not_exceed_budget() -> None:
    request, response = _initial_response()
    plan_request = _adapter().load_plan_request(request.student, response.snapshot)
    plan_response = _facade().generate_plan(plan_request)
    assert plan_response.plan.total_planned_minutes <= request.student.weekly_available_minutes
    assert plan_response.plan.total_planned_minutes == sum(
        item.estimated_minutes for item in plan_response.plan.tasks
    )


def test_followup_without_posttest_or_activity_is_rejected() -> None:
    request, snapshot = _planned_snapshot()
    with pytest.raises(ValidationError, match="posttest or activity"):
        FollowupEvaluationRequest(
            metadata=request.metadata,
            student=request.student,
            previous_snapshot=snapshot,
            assessment_attempts=[],
            activity_results=[],
        )


def test_followup_facade_creates_snapshot_lineage() -> None:
    _, snapshot = _planned_snapshot()
    followup = _adapter().load_followup_request(snapshot)
    response = _facade().evaluate_followup(followup)
    assert response.previous_snapshot_id == snapshot.snapshot_id
    assert response.current_snapshot.previous_snapshot_id == snapshot.snapshot_id
    assert response.student_id == response.current_snapshot.student_id
    assert response.next_step.career_group_id == "CAREER_GROUP_ECONOMICS"


def test_evidence_summary_has_unique_sources() -> None:
    _, response = _initial_response()
    sources = [item.source_type for item in response.evidence_summary]
    assert len(sources) == len(set(sources))
    assert all(item.evidence_count > 0 for item in response.evidence_summary)


def test_contract_json_round_trip() -> None:
    request, response = _initial_response()
    restored_request = InitialAnalysisRequest.model_validate_json(
        request.model_dump_json()
    )
    restored_response = InitialAnalysisResponse.model_validate_json(
        response.model_dump_json()
    )
    assert restored_request == request
    assert restored_response == response


def test_unknown_contract_field_is_rejected() -> None:
    data = _adapter().load_initial_request().model_dump()
    data["unknown_field"] = "not-allowed"
    with pytest.raises(ValidationError, match="Extra inputs"):
        InitialAnalysisRequest.model_validate(data)


def test_unsupported_contract_version_is_rejected() -> None:
    metadata = _adapter().load_initial_request().metadata.model_dump()
    metadata["contract_version"] = "2.0.0"
    with pytest.raises(ValidationError):
        ContractMetadata.model_validate(metadata)


def test_demo_adapter_creates_expected_request_contracts() -> None:
    adapter = _adapter()
    initial = adapter.load_initial_request()
    response = _facade().analyze(initial)
    plan = adapter.load_plan_request(initial.student, response.snapshot)
    followup = adapter.load_followup_request(response.snapshot)
    assert isinstance(initial, InitialAnalysisRequest)
    assert isinstance(plan, PlanGenerationRequest)
    assert isinstance(followup, FollowupEvaluationRequest)
    assert followup.previous_snapshot.snapshot_id == response.snapshot.snapshot_id


def test_market_adapter_satisfies_protocol() -> None:
    assert isinstance(ReadOnlyMarketContextProvider(), MarketContextProvider)


def test_export_script_creates_all_six_files(tmp_path) -> None:
    paths = export_contract_examples(tmp_path)
    assert len(paths) == 6
    assert all(path.is_file() for path in paths)
    assert {path.name for path in paths} == {
        "initial_analysis_request.json",
        "initial_analysis_response.json",
        "plan_generation_request.json",
        "plan_generation_response.json",
        "followup_evaluation_request.json",
        "followup_evaluation_response.json",
    }


def test_export_is_byte_deterministic(tmp_path) -> None:
    canonical = {path.name: path.read_bytes() for path in EXAMPLE_ROOT.glob("*.json")}
    export_contract_examples(tmp_path)
    first = {path.name: path.read_bytes() for path in tmp_path.glob("*.json")}
    export_contract_examples(tmp_path)
    second = {path.name: path.read_bytes() for path in tmp_path.glob("*.json")}
    assert first == second
    assert {path.name: path.read_bytes() for path in EXAMPLE_ROOT.glob("*.json")} == canonical


def test_small_market_sample_produces_warning() -> None:
    _, response = _initial_response()
    warnings = [item for item in response.warnings if item.warning_code == "small_market_sample"]
    assert len(warnings) == 1
    assert warnings[0].affected_field == "market_context"
