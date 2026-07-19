"""Typed HTTP provider for the generic AI Worker gateway."""

from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..validators import LLMProviderError


class AIWorkerProviderError(LLMProviderError):
    """Base error with a stable internal category and no sensitive detail."""

    code = "ai_worker_error"


class AIWorkerConfigurationError(AIWorkerProviderError):
    code = "ai_worker_configuration_missing"


class AIWorkerConnectionError(AIWorkerProviderError):
    code = "ai_worker_connection_error"


class AIWorkerTimeoutError(AIWorkerProviderError):
    code = "ai_worker_timeout"


class AIWorkerHTTPError(AIWorkerProviderError):
    code = "ai_worker_http_error"


class AIWorkerInvalidResponseError(AIWorkerProviderError):
    code = "ai_worker_invalid_response"


class AIWorkerUnparsedResponseError(AIWorkerProviderError):
    code = "ai_worker_unparsed_response"


class AIWorkerEmptyResponseError(AIWorkerProviderError):
    code = "ai_worker_empty_response"


class _GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AIWorkerMessage(_GatewayModel):
    role: Literal["user", "assistant"]
    content: str


class AIWorkerInferRequest(_GatewayModel):
    system_prompt: str
    messages: list[AIWorkerMessage] = Field(min_length=1)
    response_format: Literal["json"] = "json"
    max_tokens: int = Field(gt=0)


class AIWorkerUsage(_GatewayModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class AIWorkerInferResponse(_GatewayModel):
    content: Any
    parsed: bool
    model: str
    usage: AIWorkerUsage


class AIWorkerProvider:
    """Call AI Worker without owning provider model selection or business rules."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        max_tokens: int = 2048,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.strip().rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens
        self._client = client

    @property
    def provider_name(self) -> str:
        return "ai_worker_gateway_v1"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> dict:
        del schema_name
        self._validate_configuration()
        request = AIWorkerInferRequest(
            system_prompt=system_prompt,
            messages=[AIWorkerMessage(role="user", content=user_prompt)],
            response_format="json",
            max_tokens=self._max_tokens,
        )
        try:
            if self._client is not None:
                response = self._client.post(
                    f"{self._base_url}/infer",
                    json=request.model_dump(mode="json"),
                    timeout=self._timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    response = client.post(
                        f"{self._base_url}/infer",
                        json=request.model_dump(mode="json"),
                    )
        except httpx.TimeoutException as exc:
            raise AIWorkerTimeoutError("AI Worker request timed out") from exc
        except httpx.RequestError as exc:
            raise AIWorkerConnectionError("AI Worker is unreachable") from exc

        if response.is_error:
            raise AIWorkerHTTPError("AI Worker returned an HTTP error")
        try:
            envelope = AIWorkerInferResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise AIWorkerInvalidResponseError("AI Worker returned an invalid response") from exc
        if not envelope.parsed:
            raise AIWorkerUnparsedResponseError("AI Worker could not parse JSON output")
        if envelope.content in (None, "", {}, []):
            raise AIWorkerEmptyResponseError("AI Worker returned empty content")
        if not isinstance(envelope.content, dict):
            raise AIWorkerInvalidResponseError("AI Worker JSON content must be an object")
        return dict(envelope.content)

    def _validate_configuration(self) -> None:
        if not self._base_url:
            raise AIWorkerConfigurationError("AI_WORKER_URL is required in live mode")
        if self._timeout_seconds <= 0:
            raise AIWorkerConfigurationError("AI worker timeout must be positive")
        if self._max_tokens <= 0:
            raise AIWorkerConfigurationError("AI worker max tokens must be positive")
