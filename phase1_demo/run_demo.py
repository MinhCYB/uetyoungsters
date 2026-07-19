"""Dependency-free local HTTP server for the Student Companion demo."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel

from phase1_demo.student_companion.application import DemoService, InvalidTransition
from phase1_demo.student_companion.config import PIPELINE_VERSION


DEFAULT_STATIC_ROOT = Path(__file__).resolve().parent / "static"
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, set):
        return [to_jsonable(item) for item in sorted(value, key=str)]
    return value


class DemoHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        service: DemoService,
        static_root: Path,
    ) -> None:
        self.service = service
        self.static_root = static_root.resolve()
        self.state_lock = threading.RLock()
        super().__init__(server_address, DemoRequestHandler)


class DemoRequestHandler(BaseHTTPRequestHandler):
    server: DemoHTTPServer

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            modes = sorted({item.data_mode for item in self.server.service.market})
            self._send_json(
                200,
                {
                    "status": "ok",
                    "pipeline_version": PIPELINE_VERSION,
                    "market_data_mode": modes[0] if len(modes) == 1 else modes,
                },
            )
            return
        if path == "/api/demo/state":
            with self.server.state_lock:
                self._send_json(200, self.server.service.get_state())
            return
        if path == "/api/demo/comparison":
            self._run_service_action(self.server.service.get_comparison)
            return
        if path.startswith("/api/"):
            self._send_json(404, {"error": "not_found", "message": "API route not found."})
            return
        self._serve_static(path)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        actions = {
            "/api/demo/reset": self.server.service.reset,
            "/api/demo/analyze": self.server.service.analyze_initial_state,
            "/api/demo/plan": self.server.service.generate_weekly_plan,
            "/api/demo/advance": self.server.service.advance_two_weeks,
        }
        action = actions.get(path)
        if action is None:
            self._send_json(404, {"error": "not_found", "message": "API route not found."})
            return
        self._discard_request_body()
        self._run_service_action(action)

    def _run_service_action(self, action) -> None:
        try:
            with self.server.state_lock:
                result = action()
            self._send_json(200, result)
        except InvalidTransition as exc:
            self._send_json(
                409,
                {
                    "error": "invalid_state_transition",
                    "message": str(exc),
                    "current_stage": self.server.service.stage.value,
                },
            )
        except Exception as exc:
            self.log_error("Unhandled demo error: %s", exc)
            self._send_json(
                500,
                {
                    "error": "internal_server_error",
                    "message": "The local demo could not complete this action.",
                },
            )

    def _discard_request_body(self) -> None:
        length_text = self.headers.get("Content-Length", "0")
        try:
            length = int(length_text)
        except ValueError:
            length = 0
        if length > 0:
            self.rfile.read(length)

    def _serve_static(self, request_path: str) -> None:
        decoded = unquote(request_path).replace("\\", "/")
        relative = "index.html" if decoded == "/" else decoded.lstrip("/")
        pure_path = PurePosixPath(relative)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            self._send_json(403, {"error": "forbidden", "message": "Invalid static path."})
            return
        target = (self.server.static_root / Path(*pure_path.parts)).resolve()
        try:
            target.relative_to(self.server.static_root)
        except ValueError:
            self._send_json(403, {"error": "forbidden", "message": "Invalid static path."})
            return
        if not target.is_file():
            self._send_json(404, {"error": "not_found", "message": "File not found."})
            return
        content_type = MIME_TYPES.get(target.suffix.lower())
        if content_type is None:
            guessed, _ = mimetypes.guess_type(target.name)
            content_type = guessed or "application/octet-stream"
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(
            to_jsonable(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    service: DemoService | None = None,
    static_root: Path = DEFAULT_STATIC_ROOT,
) -> DemoHTTPServer:
    return DemoHTTPServer((host, port), service or DemoService(), static_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Student Companion Phase 1 demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = create_server(args.host, args.port)
    actual_host, actual_port = server.server_address[:2]
    print(
        f"Student Companion demo running at http://{actual_host}:{actual_port}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Student Companion demo.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
