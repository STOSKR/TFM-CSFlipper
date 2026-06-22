"""Small HTTP server that lets Render run scraping jobs on demand."""

from __future__ import annotations

import hmac
import json
import os
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

CommandRunner = Callable[[Sequence[str]], int]


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    running: bool
    last_started_at: str | None
    last_finished_at: str | None
    last_return_code: int | None


class ScrapeJobRunner:
    """Runs one scraping process at a time."""

    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or _run_command
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._last_started_at: str | None = None
        self._last_finished_at: str | None = None
        self._last_return_code: int | None = None

    def start(self, command: Sequence[str]) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._last_started_at = _now_text()
            self._last_finished_at = None
            self._last_return_code = None
            self._thread = threading.Thread(
                target=self._run,
                args=(tuple(command),),
                daemon=True,
                name="scrape-job",
            )
            self._thread.start()
            return True

    def snapshot(self) -> JobSnapshot:
        with self._lock:
            return JobSnapshot(
                running=self._thread is not None and self._thread.is_alive(),
                last_started_at=self._last_started_at,
                last_finished_at=self._last_finished_at,
                last_return_code=self._last_return_code,
            )

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _run(self, command: tuple[str, ...]) -> None:
        return_code = self._command_runner(command)
        with self._lock:
            self._last_return_code = return_code
            self._last_finished_at = _now_text()


def build_scrape_job_command(env: Mapping[str, str] | None = None) -> list[str]:
    values = env or os.environ
    if _bool(values.get("SCRAPE_REFRESH_ONLY"), default=False):
        command = [
            sys.executable,
            "-u",
            "-m",
            "apps.cli.refresh_market_history",
            "--stale-minutes",
            str(_int(values.get("SCRAPE_STALE_MINUTES"), default=480)),
        ]
        refresh_limit = _optional_int(values.get("SCRAPE_REFRESH_LIMIT"))
        if refresh_limit is not None:
            command.extend(["--limit", str(refresh_limit)])
        if _bool(values.get("SCRAPE_PERSIST"), default=True):
            command.append("--persist")
        else:
            command.append("--dry-run")
        if _bool(values.get("SCRAPE_SHOW_BROWSER"), default=False):
            command.append("--show-browser")
        return command

    command = [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.auto_scrape_loop",
    ]
    candidate_limit = _optional_int(values.get("SCRAPE_CANDIDATE_LIMIT"))
    if candidate_limit is not None:
        command.append(str(candidate_limit))
    command.extend(
        [
            "--once",
            "--stale-minutes",
            str(_int(values.get("SCRAPE_STALE_MINUTES"), default=480)),
        ]
    )
    refresh_limit = _optional_int(values.get("SCRAPE_REFRESH_LIMIT"))
    if refresh_limit is not None:
        command.extend(["--refresh-limit", str(refresh_limit)])
    if _bool(values.get("SCRAPE_PERSIST"), default=True):
        command.append("--persist")
    else:
        command.append("--no-persist")
    if _bool(values.get("SCRAPE_SHOW_BROWSER"), default=False):
        command.append("--show-browser")
    return command


def _run_command(command: Sequence[str]) -> int:
    timeout_seconds = _optional_int(os.getenv("SCRAPE_JOB_TIMEOUT_SECONDS"))
    env = _subprocess_env(os.environ)
    if _bool(os.getenv("SCRAPE_ENSURE_PLAYWRIGHT"), default=True):
        install_code = _ensure_playwright_browser(env)
        if install_code != 0:
            return install_code
    try:
        return subprocess.run(command, check=False, timeout=timeout_seconds, env=env).returncode
    except subprocess.TimeoutExpired:
        return 124


def _ensure_playwright_browser(env: Mapping[str, str]) -> int:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = env["PLAYWRIGHT_BROWSERS_PATH"]
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("playwright_check=missing_package", flush=True)
        return 1

    with sync_playwright() as playwright:
        executable_path = Path(playwright.chromium.executable_path)
    if executable_path.exists():
        print(f"playwright_check=ok executable={executable_path}", flush=True)
        return 0

    print(f"playwright_check=missing executable={executable_path}", flush=True)
    install_command = [sys.executable, "-m", "playwright", "install", "chromium"]
    print(" ".join(install_command), flush=True)
    return subprocess.run(install_command, check=False, env=env).returncode


def _subprocess_env(base_env: Mapping[str, str]) -> dict[str, str]:
    env = dict(base_env)
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


class ScrapeJobHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        runner: ScrapeJobRunner,
        token: str | None,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.runner = runner
        self.token = token


class ScrapeJobHandler(BaseHTTPRequestHandler):
    server: ScrapeJobHTTPServer

    def do_GET(self) -> None:
        self._route()

    def do_POST(self) -> None:
        self._route()

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)

    def _route(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"", "/"}:
            self._write_json(HTTPStatus.OK, {"service": "csflipper-scrape-job"})
            return
        if parsed.path == "/health":
            self._write_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/jobs/scrape/status":
            if not self._authorized(parsed.query):
                return
            self._write_json(HTTPStatus.OK, _snapshot_payload(self.server.runner.snapshot()))
            return
        if parsed.path == "/jobs/scrape":
            if not self._authorized(parsed.query):
                return
            command = build_scrape_job_command()
            started = self.server.runner.start(command)
            if not started:
                self._write_json(
                    HTTPStatus.CONFLICT,
                    {
                        "status": "already_running",
                        "job": _snapshot_payload(self.server.runner.snapshot()),
                    },
                )
                return
            self._write_json(
                HTTPStatus.ACCEPTED,
                {
                    "status": "started",
                    "command": command,
                    "job": _snapshot_payload(self.server.runner.snapshot()),
                },
            )
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _authorized(self, query: str) -> bool:
        expected = self.server.token
        if not expected:
            self._write_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "SCRAPE_JOB_TOKEN is not configured"},
            )
            return False
        provided = _bearer_token(self.headers.get("Authorization")) or _query_token(query)
        if provided and hmac.compare_digest(provided, expected):
            return True
        self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def _write_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _snapshot_payload(snapshot: JobSnapshot) -> dict[str, object]:
    return {
        "running": snapshot.running,
        "last_started_at": snapshot.last_started_at,
        "last_finished_at": snapshot.last_finished_at,
        "last_return_code": snapshot.last_return_code,
    }


def _bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    prefix = "Bearer "
    if not value.startswith(prefix):
        return None
    token = value[len(prefix) :].strip()
    return token or None


def _query_token(query: str) -> str | None:
    values = parse_qs(query).get("token") or []
    return values[0] if values else None


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _int(value: str | None, *, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


def _bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _now_text() -> str:
    return datetime.now(tz=UTC).isoformat()


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = _int(os.getenv("PORT"), default=8000)
    server = ScrapeJobHTTPServer(
        (host, port),
        ScrapeJobHandler,
        runner=ScrapeJobRunner(),
        token=os.getenv("SCRAPE_JOB_TOKEN"),
    )
    print(f"scrape_job_server listening host={host} port={port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
