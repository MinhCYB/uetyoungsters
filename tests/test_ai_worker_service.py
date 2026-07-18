from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import types

from fastapi.testclient import TestClient


MODULE_PATH = Path("ai-worker-service/main.py")
if "google.genai" not in sys.modules:
    google_stub = types.ModuleType("google")
    genai_stub = types.ModuleType("google.genai")
    types_stub = types.ModuleType("google.genai.types")
    genai_stub.Client = object
    types_stub.HttpOptions = lambda **kwargs: SimpleNamespace(**kwargs)
    types_stub.GenerateContentConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    genai_stub.types = types_stub
    google_stub.genai = genai_stub
    sys.modules["google"] = google_stub
    sys.modules["google.genai"] = genai_stub
    sys.modules["google.genai.types"] = types_stub
SPEC = importlib.util.spec_from_file_location("ai_worker_main", MODULE_PATH)
ai_worker = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = ai_worker
SPEC.loader.exec_module(ai_worker)


class FakeModels:
    def __init__(self, text='hello', error=None):
        self.text = text
        self.error = error
        self.call = None

    async def generate_content(self, **kwargs):
        self.call = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, usage_metadata=SimpleNamespace(
            prompt_token_count=7, candidates_token_count=3
        ))


class FakeClient:
    def __init__(self, models):
        self.aio = SimpleNamespace(models=models)


def client_for(monkeypatch, models):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DEFAULT_MODEL", "test-gemini-model")
    monkeypatch.setenv("DEFAULT_MAX_TOKENS", "2048")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "60")
    ai_worker.app.dependency_overrides[ai_worker.get_gemini_client] = lambda: FakeClient(models)
    return TestClient(ai_worker.app)


def test_health(monkeypatch):
    messages = FakeModels()
    with client_for(monkeypatch, messages) as client:
        assert client.get("/health").json() == {"status": "ok", "service": "ai-worker-service"}


def test_infer_forwards_multiturn_and_content_blocks(monkeypatch):
    messages = FakeModels("raw response")
    with client_for(monkeypatch, messages) as client:
        response = client.post("/infer", json={
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "reply"},
                {"role": "user", "content": [{"type": "text", "text": "next"}]},
            ]
        })
    assert response.status_code == 200
    assert response.json() == {
        "content": "raw response", "parsed": True,
        "model": "test-gemini-model",
        "usage": {"input_tokens": 7, "output_tokens": 3},
    }
    assert messages.call["contents"][2]["parts"] == [{"text": "next"}]
    assert messages.call["contents"][1]["role"] == "model"


def test_json_response_is_parsed_and_instruction_is_added(monkeypatch):
    messages = FakeModels('{"score": 9}')
    with client_for(monkeypatch, messages) as client:
        response = client.post("/infer", json={
            "system_prompt": "You are a scorer.",
            "messages": [{"role": "user", "content": "score this"}],
            "response_format": "json",
        })
    assert response.json()["content"] == {"score": 9}
    assert response.json()["parsed"] is True
    assert ai_worker.JSON_INSTRUCTION in messages.call["config"].system_instruction


def test_invalid_json_is_returned_unchanged(monkeypatch):
    messages = FakeModels("not-json")
    with client_for(monkeypatch, messages) as client:
        response = client.post("/infer", json={
            "messages": [{"role": "user", "content": "answer"}],
            "response_format": "json",
        })
    assert response.json()["content"] == "not-json"
    assert response.json()["parsed"] is False


def test_upstream_failure_returns_502(monkeypatch):
    messages = FakeModels(error=TimeoutError("timed out"))
    with client_for(monkeypatch, messages) as client:
        response = client.post("/infer", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 502
    assert "timed out" in response.json()["detail"]
