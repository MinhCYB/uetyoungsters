"""Scriptable deterministic provider for tests and offline demos."""

from __future__ import annotations

from collections.abc import Iterable

from ..ports import LLMProvider


class FakeLLMProvider:
    def __init__(
        self,
        scripted_outputs: Iterable[str | dict | BaseException] = (),
        *,
        delegate: LLMProvider | None = None,
    ) -> None:
        self._outputs = tuple(scripted_outputs)
        self._delegate = delegate
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "fake_llm_provider_v1"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> str | dict:
        index = self.call_count
        self.call_count += 1
        if self._outputs:
            item = self._outputs[min(index, len(self._outputs) - 1)]
            if isinstance(item, BaseException):
                raise item
            return item
        if self._delegate is not None:
            return self._delegate.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema_name=schema_name,
            )
        raise RuntimeError("fake provider has no scripted output")
