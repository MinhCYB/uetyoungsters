"""Stateless validated orchestration with one retry and deterministic fallback."""

from __future__ import annotations

import json

from .contracts import (
    ContentGenerationResultMetadata,
    DetailedLearningPlan,
    FeedbackGenerationRequest,
    PersonalizedFeedback,
    PlanExpansionRequest,
    ReassessmentGenerationRequest,
    ReassessmentPackage,
)
from .fallback_templates import stable_content_token
from .ports import LLMProvider
from .prompts import (
    FEEDBACK_PROMPT_VERSION,
    PLAN_EXPANSION_PROMPT_VERSION,
    REASSESSMENT_PROMPT_VERSION,
    build_feedback_prompts,
    build_plan_prompts,
    build_reassessment_prompts,
)
from .providers.template_provider import TemplateProvider
from .validators import (
    LLMInvariantViolation,
    LLMOutputParseError,
    LLMOutputValidationError,
    LLMProviderError,
    parse_provider_output,
    validate_feedback,
    validate_model,
    validate_plan,
    validate_reassessment,
)


class StudentCompanionContentOrchestrator:
    """Generate constrained content without owning any engine decision."""

    def __init__(
        self,
        provider: LLMProvider,
        fallback_provider: LLMProvider | None = None,
    ) -> None:
        self._provider = provider
        self._fallback_provider = fallback_provider or TemplateProvider()

    def expand_plan(self, request: PlanExpansionRequest) -> DetailedLearningPlan:
        self._require_prompt_version(request.metadata.prompt_version, PLAN_EXPANSION_PROMPT_VERSION)
        system_prompt, user_prompt = build_plan_prompts(request)
        return self._execute(
            request=request,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="DetailedLearningPlan",
            model_type=DetailedLearningPlan,
            invariant=validate_plan,
        )

    def generate_reassessment(
        self,
        request: ReassessmentGenerationRequest,
    ) -> ReassessmentPackage:
        self._require_prompt_version(
            request.metadata.prompt_version, REASSESSMENT_PROMPT_VERSION
        )
        system_prompt, user_prompt = build_reassessment_prompts(request)
        return self._execute(
            request=request,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="ReassessmentPackage",
            model_type=ReassessmentPackage,
            invariant=validate_reassessment,
        )

    def generate_feedback(
        self,
        request: FeedbackGenerationRequest,
    ) -> PersonalizedFeedback:
        self._require_prompt_version(request.metadata.prompt_version, FEEDBACK_PROMPT_VERSION)
        system_prompt, user_prompt = build_feedback_prompts(request)
        return self._execute(
            request=request,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name="PersonalizedFeedback",
            model_type=PersonalizedFeedback,
            invariant=validate_feedback,
        )

    @staticmethod
    def _require_prompt_version(actual: str, expected: str) -> None:
        if actual != expected:
            raise LLMInvariantViolation("request prompt_version does not match the use case")

    def _execute(
        self,
        *,
        request,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        model_type,
        invariant,
    ):
        warnings: list[str] = []
        for attempt in (1, 2):
            try:
                raw = self._provider.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema_name=schema_name,
                )
                return self._finalize(
                    raw=raw,
                    request=request,
                    schema_name=schema_name,
                    model_type=model_type,
                    invariant=invariant,
                    provider=self._provider,
                    validation_attempts=attempt,
                    warnings=warnings,
                )
            except (LLMOutputParseError, LLMOutputValidationError, LLMInvariantViolation) as exc:
                warnings.append(self._warning_code(exc))
            except Exception:
                warnings.append("provider_error")

        warnings.append("provider_fallback_used")
        try:
            raw = self._fallback_provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema_name=schema_name,
            )
            return self._finalize(
                raw=raw,
                request=request,
                schema_name=schema_name,
                model_type=model_type,
                invariant=invariant,
                provider=self._fallback_provider,
                validation_attempts=2,
                warnings=warnings,
            )
        except (LLMOutputParseError, LLMOutputValidationError, LLMInvariantViolation):
            raise
        except Exception as exc:
            raise LLMProviderError("deterministic fallback provider failed") from exc

    @staticmethod
    def _warning_code(exc: Exception) -> str:
        if isinstance(exc, LLMOutputParseError):
            return "provider_output_parse_error"
        if isinstance(exc, LLMOutputValidationError):
            return "provider_output_schema_error"
        return "provider_output_invariant_violation"

    def _finalize(
        self,
        *,
        raw: str | dict,
        request,
        schema_name: str,
        model_type,
        invariant,
        provider: LLMProvider,
        validation_attempts: int,
        warnings: list[str],
    ):
        payload = parse_provider_output(raw)
        provider_warnings = payload.pop("_warnings", [])
        payload.pop("content_id", None)
        payload.pop("result_metadata", None)
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        payload["content_id"] = stable_content_token(
            "CONTENT", request.metadata.request_id, schema_name, canonical
        )
        payload["result_metadata"] = ContentGenerationResultMetadata(
            content_mode=self._content_mode(provider),
            provider_name=provider.provider_name,
            prompt_version=request.metadata.prompt_version,
            validation_attempts=validation_attempts,
            warnings=sorted(set([*warnings, *provider_warnings])),
        ).model_dump(mode="json")
        model = validate_model(model_type, payload)
        invariant(model, request)
        return model

    @staticmethod
    def _content_mode(provider: LLMProvider) -> str:
        if isinstance(provider, TemplateProvider):
            return "template_fallback"
        if provider.provider_name == "fake_llm_provider_v1":
            return "fake_provider"
        return "external_llm"
