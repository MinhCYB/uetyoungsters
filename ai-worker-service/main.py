"""Generic synchronous HTTP gateway to the Gemini API."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_MODEL = "gemini-2.5-flash"
JSON_INSTRUCTION = (
    "Return only valid JSON. Do not include explanatory text or Markdown code fences."
)


class Message(BaseModel):
    """An Anthropic message; content blocks are deliberately passed through."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str | list[dict[str, Any]]


class InferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_prompt: str | None = None
    messages: list[Message] = Field(min_length=1)
    model: str | None = None
    max_tokens: int | None = Field(default=None, gt=0)
    response_format: Literal["text", "json"] = "text"


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class InferResponse(BaseModel):
    content: str | dict[str, Any] | list[Any] | int | float | bool | None
    parsed: bool
    model: str
    usage: Usage


def _required_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required for ai-worker-service")
    return key


def _default_max_tokens() -> int:
    raw_value = os.environ.get("DEFAULT_MAX_TOKENS", "2048")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("DEFAULT_MAX_TOKENS must be an integer") from exc
    if value <= 0:
        raise RuntimeError("DEFAULT_MAX_TOKENS must be greater than zero")
    return value


@asynccontextmanager
async def lifespan(_: FastAPI):
    _required_api_key()
    _default_max_tokens()
    yield


app = FastAPI(title="AI Worker Service", version="1.0.0", lifespan=lifespan)


def get_gemini_client() -> genai.Client:
    return genai.Client(
        api_key=_required_api_key(),
        http_options=types.HttpOptions(timeout=60_000),
    )


def _gemini_part(block: dict[str, Any]) -> dict[str, Any]:
    """Map the gateway's text/image/document blocks to Gemini inline parts."""
    if block.get("type") == "text":
        return {"text": block.get("text", "")}
    if block.get("type") in {"image", "document"}:
        source = block.get("source", {})
        if source.get("type") != "base64" or not source.get("media_type") or not source.get("data"):
            raise ValueError("image/document blocks require a base64 source, media_type, and data")
        return {"inline_data": {"mime_type": source["media_type"], "data": source["data"]}}
    raise ValueError(f"unsupported content block type: {block.get('type')}")


def _gemini_contents(messages: list[Message]) -> list[dict[str, Any]]:
    contents = []
    for message in messages:
        parts = [{"text": message.content}] if isinstance(message.content, str) else [
            _gemini_part(block) for block in message.content
        ]
        contents.append({"role": "model" if message.role == "assistant" else "user", "parts": parts})
    return contents


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-worker-service"}


@app.post("/infer", response_model=InferResponse)
async def infer(
    request: InferRequest,
    client: genai.Client = Depends(get_gemini_client),
) -> InferResponse:
    model = request.model or os.environ.get("DEFAULT_MODEL", DEFAULT_MODEL)
    max_tokens = request.max_tokens or _default_max_tokens()
    system_prompt = request.system_prompt
    if request.response_format == "json":
        system_prompt = "\n\n".join(part for part in (system_prompt, JSON_INSTRUCTION) if part)

    try:
        contents = _gemini_contents(request.messages)
        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc

    text = response.text or ""
    content: Any = text
    parsed = request.response_format == "text"
    if request.response_format == "json":
        try:
            content = json.loads(text)
            parsed = True
        except json.JSONDecodeError:
            parsed = False

    return InferResponse(
        content=content,
        parsed=parsed,
        model=model,
        usage=Usage(
            input_tokens=response.usage_metadata.prompt_token_count or 0,
            output_tokens=response.usage_metadata.candidates_token_count or 0,
        ),
    )
