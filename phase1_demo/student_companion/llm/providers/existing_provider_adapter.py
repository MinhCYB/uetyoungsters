"""Fail-closed placeholder for the repository's unimplemented LLM client."""

from __future__ import annotations

from ..validators import LLMProviderError


class ExistingProviderAdapter:
    """No live provider is configured in the repository for this demo runtime."""

    @property
    def provider_name(self) -> str:
        return "existing_provider_unavailable"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> str | dict:
        del system_prompt, user_prompt, schema_name
        raise LLMProviderError("existing provider is not configured")
