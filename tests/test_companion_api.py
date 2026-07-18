from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend-api"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import main as backend_main
from modules.companion.store import companion_store


@pytest.fixture()
def client(monkeypatch):
    companion_store.reset()
    monkeypatch.setenv("SKIP_DB_INIT", "1")

    def unexpected_init_db() -> None:
        raise AssertionError("init_db must not run in local demo mode")

    monkeypatch.setattr(backend_main, "init_db", unexpected_init_db)
    with TestClient(backend_main.app) as test_client:
        yield test_client
    companion_store.reset()


def test_startup_skips_database_init_in_demo_mode(monkeypatch) -> None:
    calls = []
    monkeypatch.setenv("SKIP_DB_INIT", "1")
    monkeypatch.setattr(backend_main, "init_db", lambda: calls.append("called"))

    backend_main.on_startup()

    assert calls == []


def test_startup_initializes_database_by_default(monkeypatch) -> None:
    calls = []
    monkeypatch.delenv("SKIP_DB_INIT", raising=False)
    monkeypatch.setattr(backend_main, "init_db", lambda: calls.append("called"))

    backend_main.on_startup()

    assert calls == ["called"]


def test_companion_routes_and_golden_path_work_in_demo_mode(client) -> None:
    paths = {route.path for route in backend_main.app.routes}
    assert {"/api/companion/analyze", "/api/companion/plan", "/api/companion/followup", "/api/companion/reset", "/api/companion/content/expand-plan", "/api/companion/content/reassessment", "/api/companion/content/feedback"} <= paths

    analysis = client.post("/api/companion/analyze", json={"student_id": "stu_uet_0001", "profile_version": 1, "fixture_selector": "initial"})
    assert analysis.status_code == 200
    plan = client.post("/api/companion/plan", json={"analysis_id": analysis.json()["analysis_id"]})
    assert plan.status_code == 200
    plan_body = plan.json()
    task = next(item for item in plan_body["activities"] if item["skill_id"])

    expanded = client.post("/api/companion/content/expand-plan", json={"plan_id": plan_body["plan_id"], "task_id": task["activity_id"]})
    assert expanded.status_code == 200
    assert expanded.json()["result_metadata"]["content_mode"] == "template_fallback"
    reassessment = client.post("/api/companion/content/reassessment", json={"plan_id": plan_body["plan_id"], "target_skill_id": task["skill_id"], "question_count": 3, "max_score": 10})
    assert reassessment.status_code == 200
    question = reassessment.json()["questions"][0]
    feedback = client.post("/api/companion/content/feedback", json={"student_id": "stu_uet_0001", "question_id": question["question_id"], "skill_id": question["skill_id"], "question_prompt": question["prompt"], "student_answer": "sai", "expected_answer": question["correct_answer"], "is_correct": False})
    assert feedback.status_code == 200
    assert feedback.json()["graded_answer"]["is_correct"] is False
    followup = client.post("/api/companion/followup", json={"baseline_analysis_id": analysis.json()["analysis_id"], "student_id": "stu_uet_0001", "profile_version": 2, "fixture_selector": "week3"})
    assert followup.status_code == 200
    assert client.post("/api/companion/reset").status_code == 200


def test_companion_errors_are_structured(client) -> None:
    missing = client.post("/api/companion/plan", json={"analysis_id": "ANALYSIS_missing"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "analysis_not_found"
    baseline = client.post("/api/companion/followup", json={"baseline_analysis_id": "ANALYSIS_missing", "student_id": "stu_uet_0001", "profile_version": 2, "fixture_selector": "week3"})
    assert baseline.status_code == 404
    assert baseline.json()["error"]["code"] == "baseline_not_found"
    invalid = client.post("/api/companion/analyze", json={"profile_version": 0})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "contract_validation_failed"
