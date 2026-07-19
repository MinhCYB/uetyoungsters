from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend-api"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from modules.companion.schemas import FeedbackRequest
from modules.companion.service import (
    CompanionError,
    CompanionService,
    build_content_orchestrator,
)
from modules.companion.store import CompanionStore
from phase1_demo.student_companion.llm.orchestrator import StudentCompanionContentOrchestrator
from phase1_demo.student_companion.llm.providers import (
    AIWorkerConfigurationError,
    AIWorkerConnectionError,
    AIWorkerEmptyResponseError,
    AIWorkerHTTPError,
    AIWorkerInvalidResponseError,
    AIWorkerProvider,
    AIWorkerTimeoutError,
    AIWorkerUnparsedResponseError,
    TemplateProvider,
)
from phase1_demo.student_companion.llm.validators import (
    LLMInvariantViolation,
    LLMOutputParseError,
    LLMOutputValidationError,
    LLMProviderError,
)


def _gateway_response(content, *, parsed: bool = True, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={
            "content": content,
            "parsed": parsed,
            "model": "worker-owned-test-model",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        },
    )


def _provider(handler, *, base_url: str = "http://ai-worker-service:8000"):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return AIWorkerProvider(
        base_url=base_url,
        timeout_seconds=5,
        max_tokens=2048,
        client=client,
    ), client


def _service(provider: AIWorkerProvider, *, allow_fallback: bool = False) -> CompanionService:
    orchestrator = StudentCompanionContentOrchestrator(
        provider,
        TemplateProvider(),
        allow_fallback=allow_fallback,
    )
    return CompanionService(CompanionStore(), orchestrator)


def _analyze_and_plan(service: CompanionService) -> tuple[dict, dict]:
    analysis = service.analyze(
        student_id="stu_uet_0001",
        profile_version=1,
        fixture_selector="initial",
    )
    return analysis, service.generate_plan(analysis["analysis_id"])


def test_live_llm_success_uses_worker_contract_and_preserves_public_shapes() -> None:
    calls: list[dict] = []
    schemas = {
        "plan_expansion": "DetailedLearningPlan",
        "reassessment": "ReassessmentPackage",
        "feedback": "PersonalizedFeedback",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        user_payload = json.loads(payload["messages"][0]["content"])
        content = TemplateProvider().generate_structured(
            system_prompt=payload["system_prompt"],
            user_prompt=payload["messages"][0]["content"],
            schema_name=schemas[user_payload["use_case"]],
        )
        return _gateway_response(content)

    provider, client = _provider(handler)
    try:
        live = _service(provider)
        _, plan = _analyze_and_plan(live)
        task = next(item for item in plan["activities"] if item["skill_id"])
        detail = live.expand_plan(plan["plan_id"], task["activity_id"], 4)
        reassessment = live.reassessment(plan["plan_id"], task["skill_id"], 3, 10)
        question = reassessment["questions"][0]
        feedback = live.feedback(FeedbackRequest(
            question_id=question["question_id"],
            skill_id=question["skill_id"],
            question_prompt=question["prompt"],
            student_answer="Sai",
            expected_answer=question["correct_answer"],
            is_correct=False,
        ))
    finally:
        client.close()

    assert [item["response_format"] for item in calls] == ["json", "json", "json"]
    assert [item["max_tokens"] for item in calls] == [2048, 2048, 2048]
    assert all(set(item) == {"system_prompt", "messages", "response_format", "max_tokens"} for item in calls)
    assert all(item["messages"][0]["role"] == "user" for item in calls)
    assert all("model" not in item for item in calls)
    assert all("Output must validate against this JSON Schema" in item["system_prompt"] for item in calls)
    assert detail["result_metadata"]["content_mode"] == "external_llm"
    assert reassessment["result_metadata"]["content_mode"] == "external_llm"
    assert feedback["result_metadata"]["content_mode"] == "external_llm"
    assert feedback["graded_answer"] == {"is_correct": False}

    template = CompanionService(
        CompanionStore(),
        StudentCompanionContentOrchestrator(TemplateProvider()),
    )
    _, template_plan = _analyze_and_plan(template)
    template_task = next(item for item in template_plan["activities"] if item["skill_id"])
    template_detail = template.expand_plan(template_plan["plan_id"], template_task["activity_id"], 4)
    template_reassessment = template.reassessment(template_plan["plan_id"], template_task["skill_id"], 3, 10)
    template_question = template_reassessment["questions"][0]
    template_feedback = template.feedback(FeedbackRequest(
        question_id=template_question["question_id"],
        skill_id=template_question["skill_id"],
        question_prompt=template_question["prompt"],
        student_answer="Sai",
        expected_answer=template_question["correct_answer"],
        is_correct=False,
    ))
    assert set(detail) == set(template_detail)
    assert set(reassessment) == set(template_reassessment)
    assert set(feedback) == set(template_feedback)


@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (_gateway_response("not-json", parsed=False), AIWorkerUnparsedResponseError),
        (_gateway_response(None), AIWorkerEmptyResponseError),
        (_gateway_response(["not", "an", "object"]), AIWorkerInvalidResponseError),
        (httpx.Response(400, json={"detail": "private request detail"}), AIWorkerHTTPError),
        (httpx.Response(503, json={"detail": "private upstream detail"}), AIWorkerHTTPError),
        (httpx.Response(200, json={"unexpected": True}), AIWorkerInvalidResponseError),
    ],
)
def test_ai_worker_response_failures_are_distinct(response, error_type) -> None:
    provider, client = _provider(lambda _: response)
    try:
        with pytest.raises(error_type):
            provider.generate_structured(
                system_prompt="system",
                user_prompt="{}",
                schema_name="DetailedLearningPlan",
            )
    finally:
        client.close()


@pytest.mark.parametrize(
    ("transport_error_type", "error_type"),
    [
        (httpx.ReadTimeout, AIWorkerTimeoutError),
        (httpx.ConnectError, AIWorkerConnectionError),
    ],
)
def test_ai_worker_transport_failures_are_distinct(transport_error_type, error_type) -> None:
    def handler(request: httpx.Request):
        raise transport_error_type("private transport detail", request=request)

    provider, client = _provider(handler)
    try:
        with pytest.raises(error_type):
            provider.generate_structured(
                system_prompt="system",
                user_prompt="{}",
                schema_name="DetailedLearningPlan",
            )
    finally:
        client.close()


def test_live_mode_missing_configuration_is_distinct() -> None:
    provider, client = _provider(lambda _: _gateway_response({}), base_url="")
    try:
        with pytest.raises(AIWorkerConfigurationError):
            provider.generate_structured(
                system_prompt="system",
                user_prompt="{}",
                schema_name="DetailedLearningPlan",
            )
    finally:
        client.close()


def test_runtime_defaults_to_fail_closed_live_mode(monkeypatch) -> None:
    monkeypatch.delenv("COMPANION_LLM_MODE", raising=False)
    monkeypatch.delenv("AI_WORKER_URL", raising=False)
    service = CompanionService(CompanionStore(), build_content_orchestrator())
    _, plan = _analyze_and_plan(service)
    task = plan["activities"][0]

    with pytest.raises(CompanionError) as captured:
        service.expand_plan(plan["plan_id"], task["activity_id"], 4)

    assert captured.value.code == "llm_configuration_missing"


def test_invalid_llm_content_is_rejected_without_public_contract_leak() -> None:
    provider, client = _provider(lambda _: _gateway_response({"unexpected": "private-value"}))
    try:
        service = _service(provider)
        _, plan = _analyze_and_plan(service)
        task = plan["activities"][0]
        with pytest.raises(CompanionError) as captured:
            service.expand_plan(plan["plan_id"], task["activity_id"], 4)
    finally:
        client.close()

    assert captured.value.code == "llm_output_schema_invalid"
    assert captured.value.status_code == 502
    assert "private-value" not in captured.value.message


def test_deterministic_fallback_requires_explicit_opt_in() -> None:
    provider, client = _provider(lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline", request=request)))
    try:
        service = _service(provider, allow_fallback=True)
        _, plan = _analyze_and_plan(service)
        task = plan["activities"][0]
        result = service.expand_plan(plan["plan_id"], task["activity_id"], 4)
    finally:
        client.close()

    assert result["result_metadata"]["content_mode"] == "template_fallback"
    assert "provider_fallback_used" in result["result_metadata"]["warnings"]


@pytest.mark.parametrize(
    ("error", "public_code", "status_code"),
    [
        (AIWorkerConfigurationError("secret config detail"), "llm_configuration_missing", 503),
        (AIWorkerConnectionError("secret connection detail"), "ai_worker_unreachable", 503),
        (AIWorkerTimeoutError("secret timeout detail"), "ai_worker_timeout", 504),
        (AIWorkerHTTPError("secret HTTP detail"), "ai_worker_http_error", 502),
        (AIWorkerUnparsedResponseError("secret parse detail"), "ai_worker_unparsed_response", 502),
        (AIWorkerEmptyResponseError("secret empty detail"), "ai_worker_empty_response", 502),
        (AIWorkerInvalidResponseError("secret envelope detail"), "ai_worker_invalid_response", 502),
        (LLMOutputParseError("secret JSON detail"), "llm_output_invalid_json", 502),
        (LLMOutputValidationError("secret schema detail"), "llm_output_schema_invalid", 502),
        (LLMInvariantViolation("secret invariant detail"), "llm_output_rejected", 502),
        (LLMProviderError("secret provider detail"), "llm_provider_failed", 502),
    ],
)
def test_provider_failures_map_to_safe_public_errors(error, public_code, status_code) -> None:
    def fail():
        raise error

    with pytest.raises(CompanionError) as captured:
        CompanionService._generate_content(fail)

    assert captured.value.code == public_code
    assert captured.value.status_code == status_code
    assert "secret" not in captured.value.message.casefold()
