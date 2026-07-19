"""Provider-neutral port for structured content generation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> str | dict:
        ...
