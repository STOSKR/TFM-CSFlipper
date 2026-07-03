"""Small HTTP server that lets Render run scraping jobs on demand."""

from __future__ import annotations

import hmac
import json
import os
import signal
import subprocess
import sys
import threading
import time
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
    progress_percent: int
    progress_text: str
    last_message: str | None
    log_tail: tuple[str, ...]


class ScrapeJobRunner:
    """Runs one scraping process at a time."""

    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._last_started_at: str | None = None
        self._last_finished_at: str | None = None
        self._last_return_code: int | None = None
        self._progress_percent = 0
        self._progress_text = "Pendiente"
        self._last_message: str | None = None
        self._log_tail: list[str] = []

    def start(self, command: Sequence[str]) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._last_started_at = _now_text()
            self._last_finished_at = None
            self._last_return_code = None
            self._progress_percent = 1
            self._progress_text = "Arrancando"
            self._last_message = None
            self._log_tail = []
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
                progress_percent=self._progress_percent,
                progress_text=self._progress_text,
                last_message=self._last_message,
                log_tail=tuple(self._log_tail[-12:]),
            )

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _run(self, command: tuple[str, ...]) -> None:
        if self._command_runner is None:
            return_code = _run_command(command, log=self._append_log_line)
        else:
            return_code = self._command_runner(command)
        with self._lock:
            self._last_return_code = return_code
            self._last_finished_at = _now_text()
            self._progress_percent = 100 if return_code == 0 else self._progress_percent
            self._progress_text = "Completado" if return_code == 0 else "Terminado con error"

    def _append_log_line(self, line: str) -> None:
        text = _public_job_line(line)
        if text is None:
            return
        progress = _progress_from_line(text)
        with self._lock:
            self._last_message = text
            self._log_tail.append(text)
            del self._log_tail[:-80]
            if progress is not None:
                percent, label = progress
                self._progress_percent = max(self._progress_percent, percent)
                self._progress_text = label


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
        command.append(_platform_concurrency_flag(values))
        return command

    if _bool(values.get("SCRAPE_STREAMING"), default=False):
        return _build_streaming_scrape_job_command(values)

    command = [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.auto_scrape_loop",
    ]
    candidate_limit = _optional_int(values.get("SCRAPE_CANDIDATE_LIMIT"))
    if candidate_limit is not None:
        command.append(str(candidate_limit))
    all_profiles = values.get("SCRAPE_ALL_PROFILES")
    if all_profiles is not None:
        command.append(
            "--all-profiles" if _bool(all_profiles, default=False) else "--no-all-profiles"
        )
    steamdt_timeout = _optional_int(values.get("SCRAPE_STEAMDT_TIMEOUT"))
    if steamdt_timeout is not None:
        command.extend(["--steamdt-timeout", str(steamdt_timeout)])
    steamdt_retries = _optional_int(values.get("SCRAPE_STEAMDT_RETRIES"))
    if steamdt_retries is not None:
        command.extend(["--steamdt-retries", str(steamdt_retries)])
    steamdt_profile_timeout = _optional_int(values.get("SCRAPE_STEAMDT_PROFILE_TIMEOUT"))
    if steamdt_profile_timeout is not None:
        command.extend(["--steamdt-profile-timeout", str(steamdt_profile_timeout)])
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


def _build_streaming_scrape_job_command(values: Mapping[str, str]) -> list[str]:
    command = [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.render_stream_scrape",
    ]
    candidate_limit = _optional_int(values.get("SCRAPE_CANDIDATE_LIMIT"))
    if candidate_limit is not None:
        command.append(str(candidate_limit))
    all_profiles = values.get("SCRAPE_ALL_PROFILES")
    if all_profiles is not None:
        command.append(
            "--all-profiles" if _bool(all_profiles, default=False) else "--no-all-profiles"
        )
    _append_bool_flag(command, values, "SCRAPE_STEAM", "--steam", "--no-steam")
    _append_bool_flag(command, values, "SCRAPE_BUFF", "--buff", "--no-buff")
    if _bool(values.get("SCRAPE_STEAM_API"), default=False):
        command.append("--steam-api")
    steamdt_timeout = _optional_int(values.get("SCRAPE_STEAMDT_TIMEOUT"))
    if steamdt_timeout is not None:
        command.extend(["--steamdt-timeout", str(steamdt_timeout)])
    steamdt_retries = _optional_int(values.get("SCRAPE_STEAMDT_RETRIES"))
    if steamdt_retries is not None:
        command.extend(["--steamdt-retries", str(steamdt_retries)])
    steamdt_profile_timeout = _optional_int(values.get("SCRAPE_STEAMDT_PROFILE_TIMEOUT"))
    if steamdt_profile_timeout is not None:
        command.extend(["--steamdt-profile-timeout", str(steamdt_profile_timeout)])
    command.extend(["--stale-minutes", str(_int(values.get("SCRAPE_STALE_MINUTES"), default=480))])
    refresh_limit = _optional_int(values.get("SCRAPE_REFRESH_LIMIT"))
    if refresh_limit is not None:
        command.extend(["--refresh-limit", str(refresh_limit)])
    batch_size = _optional_int(values.get("SCRAPE_BATCH_SIZE"))
    if batch_size is not None:
        command.extend(["--batch-size", str(batch_size)])
    queue_size = _optional_int(values.get("SCRAPE_QUEUE_SIZE"))
    if queue_size is not None:
        command.extend(["--queue-size", str(queue_size)])
    steam_concurrency = _optional_int(values.get("SCRAPE_STEAM_CONCURRENCY"))
    if steam_concurrency is not None:
        command.extend(["--steam-concurrency", str(steam_concurrency)])
    buff_concurrency = _optional_int(values.get("SCRAPE_BUFF_CONCURRENCY"))
    if buff_concurrency is not None:
        command.extend(["--buff-concurrency", str(buff_concurrency)])
    _append_bool_flag(command, values, "SCRAPE_REFRESH", "--refresh", "--no-refresh")
    _append_bool_flag(command, values, "SCRAPE_SCORE", "--score", "--no-score")
    if _bool(values.get("SCRAPE_PERSIST"), default=True):
        command.append("--persist")
    else:
        command.append("--no-persist")
    if _bool(values.get("SCRAPE_SHOW_BROWSER"), default=False):
        command.append("--show-browser")
    command.append(_platform_concurrency_flag(values))
    return command


def _platform_concurrency_flag(values: Mapping[str, str]) -> str:
    return (
        "--concurrent-platforms"
        if _bool(values.get("SCRAPE_CONCURRENT_PLATFORMS"), default=False)
        else "--no-concurrent-platforms"
    )


def _append_bool_flag(
    command: list[str],
    values: Mapping[str, str],
    key: str,
    enabled_flag: str,
    disabled_flag: str,
) -> None:
    value = values.get(key)
    if value is None:
        return
    command.append(enabled_flag if _bool(value, default=False) else disabled_flag)


def _run_command(command: Sequence[str], log: Callable[[str], None] | None = None) -> int:
    timeout_seconds = _optional_int(os.getenv("SCRAPE_JOB_TIMEOUT_SECONDS"))
    env = _subprocess_env(os.environ)
    if _bool(os.getenv("SCRAPE_ENSURE_PLAYWRIGHT"), default=True):
        install_code = _ensure_playwright_browser(env)
        if install_code != 0:
            return install_code
    process = _start_job_process(command, env, capture_output=log is not None)
    reader = None
    if log is not None and process.stdout is not None:
        reader = threading.Thread(
            target=_read_process_output,
            args=(process, log),
            daemon=True,
            name="scrape-job-output",
        )
        reader.start()
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_job_processes(process)
        return 124
    finally:
        _terminate_job_processes(process)
        if reader is not None:
            reader.join(timeout=1)


def _start_job_process(
    command: Sequence[str],
    env: Mapping[str, str],
    *,
    capture_output: bool = False,
) -> subprocess.Popen[Any]:
    return subprocess.Popen(
        command,
        env=env,
        start_new_session=os.name != "nt",
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.STDOUT if capture_output else None,
        text=capture_output,
        bufsize=1 if capture_output else -1,
    )


def _read_process_output(process: subprocess.Popen[Any], log: Callable[[str], None]) -> None:
    if process.stdout is None:
        return
    for line in process.stdout:
        log(line.rstrip())


def _terminate_job_processes(process: subprocess.Popen[Any]) -> None:
    if os.name == "nt":
        _terminate_windows_process_tree(process)
        return
    _terminate_posix_process_group(process)


def _terminate_posix_process_group(process: subprocess.Popen[Any]) -> None:
    if not _kill_posix_process_group(process.pid, signal.SIGTERM):
        return
    if process.poll() is None:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_posix_process_group(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        return
    time.sleep(0.2)
    _kill_posix_process_group(process.pid, signal.SIGKILL)


def _kill_posix_process_group(process_id: int, sig: signal.Signals) -> bool:
    try:
        os.killpg(process_id, sig)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        print(f"scrape_job_cleanup=status=error error={exc}", flush=True)
        return False
    return True


def _terminate_windows_process_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


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
        "progress_percent": snapshot.progress_percent,
        "progress_text": snapshot.progress_text,
        "last_message": snapshot.last_message,
        "log_tail": snapshot.log_tail,
    }


def _public_job_line(line: str) -> str | None:
    text = " ".join(line.strip().split())
    if not text:
        return None
    lower = text.lower()
    if lower.startswith((sys.executable.lower(), "python ", "py ")):
        return None
    return text


def _progress_from_line(line: str) -> tuple[int, str] | None:
    if line.startswith("render_stream_strategy="):
        return 12, "Buscando candidatos"
    if line.startswith("render_stream_candidate="):
        return 24, "Candidatos detectados"
    if line.startswith("stream_scrape_batch"):
        return 42, "Consultando Steam y BUFF"
    if line.startswith("render_stream_done"):
        return 65, "Scraping base completado"
    if line == "render_stream_step=refresh":
        return 72, "Actualizando historico"
    if line.startswith("market_items_loaded="):
        return 76, "Cargando objetos para historico"
    if line.startswith("["):
        return _refresh_line_progress(line)
    if "history_points_persisted=" in line:
        return 90, _history_summary_text(line)
    if line == "render_stream_step=score":
        return 94, "Calculando senales"
    return None


def _refresh_line_progress(line: str) -> tuple[int, str] | None:
    closing = line.find("]")
    if closing < 0 or "/" not in line[:closing]:
        return None
    current_text, total_text = line[1:closing].split("/", 1)
    try:
        current = int(current_text)
        total = int(total_text)
    except ValueError:
        return None
    if total <= 0:
        return None
    percent = 76 + min(12, round((current / total) * 12))
    return percent, f"Historico {current}/{total}"


def _history_summary_text(line: str) -> str:
    for part in line.split():
        if part.startswith("history_points_persisted="):
            value = part.partition("=")[2]
            return f"Historico guardado: {value} puntos"
    return "Historico guardado"


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
