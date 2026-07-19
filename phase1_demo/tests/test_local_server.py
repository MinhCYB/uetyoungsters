from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator

import pytest

from phase1_demo.run_demo import create_server


@pytest.fixture(scope="module")
def live_server() -> Iterator[tuple[str, int]]:
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield str(host), int(port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def _request(
    address: tuple[str, int],
    method: str,
    path: str,
) -> tuple[int, str, bytes]:
    connection = http.client.HTTPConnection(*address, timeout=4)
    try:
        connection.request(method, path, body=b"" if method == "POST" else None)
        response = connection.getresponse()
        return response.status, response.getheader("Content-Type", ""), response.read()
    finally:
        connection.close()


def _json_request(address: tuple[str, int], method: str, path: str) -> tuple[int, dict]:
    status, content_type, body = _request(address, method, path)
    assert content_type == "application/json; charset=utf-8"
    return status, json.loads(body.decode("utf-8"))


def _reset(address: tuple[str, int]) -> None:
    status, payload = _json_request(address, "POST", "/api/demo/reset")
    assert status == 200
    assert payload["stage"] == "initial"


def test_health_returns_200(live_server: tuple[str, int]) -> None:
    status, payload = _json_request(live_server, "GET", "/health")
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["market_data_mode"] in {"pipeline_export", "fallback_demo"}


def test_root_returns_html(live_server: tuple[str, int]) -> None:
    status, content_type, body = _request(live_server, "GET", "/")
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "Student Companion" in body.decode("utf-8")


@pytest.mark.parametrize(
    ("path", "expected_content_type"),
    [("/styles.css", "text/css; charset=utf-8"), ("/app.js", "text/javascript; charset=utf-8")],
)
def test_static_assets_have_correct_content_type(
    live_server: tuple[str, int], path: str, expected_content_type: str
) -> None:
    status, content_type, body = _request(live_server, "GET", path)
    assert status == 200
    assert content_type == expected_content_type
    assert body


def test_unknown_api_route_returns_json_404(live_server: tuple[str, int]) -> None:
    status, payload = _json_request(live_server, "GET", "/api/demo/unknown")
    assert status == 404
    assert payload["error"] == "not_found"


def test_reset_returns_initial_stage(live_server: tuple[str, int]) -> None:
    _reset(live_server)


def test_analyze_transitions_to_analyzed(live_server: tuple[str, int]) -> None:
    _reset(live_server)
    status, payload = _json_request(live_server, "POST", "/api/demo/analyze")
    assert status == 200
    assert payload["stage"] == "analyzed"
    assert payload["ability_profile"]
    assert payload["gaps"]


def test_plan_before_analyze_returns_409(live_server: tuple[str, int]) -> None:
    _reset(live_server)
    status, payload = _json_request(live_server, "POST", "/api/demo/plan")
    assert status == 409
    assert payload["error"] == "invalid_state_transition"
    assert payload["current_stage"] == "initial"


def test_plan_after_analyze_transitions_to_planned(live_server: tuple[str, int]) -> None:
    _reset(live_server)
    _json_request(live_server, "POST", "/api/demo/analyze")
    status, payload = _json_request(live_server, "POST", "/api/demo/plan")
    assert status == 200
    assert payload["stage"] == "planned"
    assert payload["weekly_plan"]["total_planned_minutes"] == 45


def test_advance_before_plan_returns_409(live_server: tuple[str, int]) -> None:
    _reset(live_server)
    status, payload = _json_request(live_server, "POST", "/api/demo/advance")
    assert status == 409
    assert payload["current_stage"] == "initial"


def test_advance_after_plan_transitions_to_advanced(live_server: tuple[str, int]) -> None:
    _reset(live_server)
    _json_request(live_server, "POST", "/api/demo/analyze")
    _json_request(live_server, "POST", "/api/demo/plan")
    status, payload = _json_request(live_server, "POST", "/api/demo/advance")
    assert status == 200
    assert payload["stage"] == "advanced"
    assert payload["comparison"]["next_step"]["career_group_id"] == "CAREER_GROUP_ECONOMICS"


def test_comparison_before_advance_returns_409(live_server: tuple[str, int]) -> None:
    _reset(live_server)
    status, payload = _json_request(live_server, "GET", "/api/demo/comparison")
    assert status == 409
    assert payload["error"] == "invalid_state_transition"


def test_comparison_after_advance_has_before_and_after(live_server: tuple[str, int]) -> None:
    _reset(live_server)
    _json_request(live_server, "POST", "/api/demo/analyze")
    _json_request(live_server, "POST", "/api/demo/plan")
    _json_request(live_server, "POST", "/api/demo/advance")
    status, payload = _json_request(live_server, "GET", "/api/demo/comparison")
    assert status == 200
    assert payload["before"]["snapshot_id"] == "SNAPSHOT_T0_001"
    assert payload["after"]["previous_snapshot_id"] == "SNAPSHOT_T0_001"
    assert payload["assessment_result"]["before_score"] == 4.0
    assert payload["assessment_result"]["after_score"] == 7.0


def test_reset_after_advanced_returns_to_initial(live_server: tuple[str, int]) -> None:
    _reset(live_server)
    _json_request(live_server, "POST", "/api/demo/analyze")
    _json_request(live_server, "POST", "/api/demo/plan")
    _json_request(live_server, "POST", "/api/demo/advance")
    _reset(live_server)
    status, payload = _json_request(live_server, "GET", "/api/demo/state")
    assert status == 200
    assert payload["stage"] == "initial"


def test_path_traversal_is_rejected(live_server: tuple[str, int]) -> None:
    status, payload = _json_request(live_server, "GET", "/%2e%2e/README.md")
    assert status == 403
    assert payload["error"] == "forbidden"


def test_server_starts_and_shuts_down_cleanly() -> None:
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    status, payload = _json_request(server.server_address[:2], "GET", "/health")
    assert status == 200
    assert payload["status"] == "ok"
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    assert not thread.is_alive()
