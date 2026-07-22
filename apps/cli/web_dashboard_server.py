"""Serve the local web dashboard with live database-backed JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from apps.cli.platform_selection import PlatformSelection, platform_env
from apps.cli.scrape_job_server import (
    ScrapeJobRunner,
    _snapshot_payload,
    build_scrape_job_command,
)
from apps.cli.session_state_metadata import read_session_metadata
from packages.persistence.connection import create_pool
from packages.runtime_config import load_runtime_config
from packages.web import build_dashboard_payload, market_items_query


class DashboardHandler(SimpleHTTPRequestHandler):
    server: DashboardHTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/dashboard":
            self._write_dashboard(parsed.query)
            return
        if parsed.path == "/api/scrape/status":
            self._write_scrape_status()
            return
        if parsed.path == "/api/commands":
            self._write_commands()
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/scrape/start":
            self._start_scrape_job()
            return
        if parsed.path == "/api/commands/run":
            self._run_command()
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format: str, *args: Any) -> None:
        if urlparse(self.path).path == "/api/scrape/status":
            return
        super().log_message(format, *args)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _write_dashboard(self, query: str) -> None:
        try:
            limit = _limit_from_query(query)
            payload = asyncio.run(_dashboard_payload(limit=limit))
        except Exception as exc:
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "dashboard_query_failed", "message": str(exc)},
            )
            return
        self._write_json(HTTPStatus.OK, payload)

    def _write_scrape_status(self) -> None:
        self._write_json(HTTPStatus.OK, _scrape_status_payload(self.server.scrape_runner))

    def _write_commands(self) -> None:
        self._write_json(
            HTTPStatus.OK,
            {
                "commands": [_command_payload(command) for command in _local_commands()],
                "sessions": _session_payload(),
                "job": _snapshot_payload(self.server.scrape_runner.snapshot()),
            },
        )

    def _start_scrape_job(self) -> None:
        payload = self._read_request_json()
        command = _web_scrape_command(
            show_browser=payload.get("show_browser") is True,
            refresh=payload.get("refresh") is True,
            scrape_buff=payload.get("scrape_buff") is True,
            refresh_buff=payload.get("refresh_buff") is True,
        )
        started = self.server.scrape_runner.start(command)
        status = HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT
        payload = _scrape_status_payload(self.server.scrape_runner)
        payload["status"] = "started" if started else "already_running"
        self._write_json(status, payload)

    def _run_command(self) -> None:
        payload = self._read_request_json()
        command_id = str(payload.get("id") or "")
        command = _local_command(command_id)
        if command is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "unknown_command"})
            return
        started = self.server.scrape_runner.start(command.command)
        status = HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT
        self._write_json(
            status,
            {
                "status": "started" if started else "already_running",
                "selected_command": _command_payload(command),
                "job": _snapshot_payload(self.server.scrape_runner.snapshot()),
            },
        )

    def _read_request_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class DashboardHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[SimpleHTTPRequestHandler],
        *,
        scrape_runner: ScrapeJobRunner,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.scrape_runner = scrape_runner


@dataclass(frozen=True, slots=True)
class LocalCommand:
    id: str
    label: str
    description: str
    command: list[str]
    group: str = "maintenance"
    destructive: bool = False


async def _dashboard_payload(*, limit: int) -> dict[str, Any]:
    runtime_config = load_runtime_config()
    pool = await create_pool(max_size=2)
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch(market_items_query(), limit)
    finally:
        await pool.close()
    return build_dashboard_payload(
        tuple(dict(row) for row in rows),
        risk_config=runtime_config.risk,
    )


def _limit_from_query(query: str) -> int:
    raw = (parse_qs(query).get("limit") or ["500"])[0]
    try:
        value = int(raw)
    except ValueError:
        return 500
    return min(max(value, 1), 2000)


def _scrape_status_payload(runner: ScrapeJobRunner) -> dict[str, Any]:
    return {
        "job": _snapshot_payload(runner.snapshot()),
    }


def _local_commands() -> tuple[LocalCommand, ...]:
    return (
        LocalCommand(
            id="login_steam",
            label="Login Steam",
            description="Abre Steam Market en navegador visible y guarda la sesion local.",
            command=[
                sys.executable,
                "-u",
                "-m",
                "apps.cli.scrape_candidate_platforms",
                "--login-only",
                "--steam",
                "--no-buff",
                "--show-browser",
                "--login-wait",
                "180",
            ],
            group="login",
        ),
        LocalCommand(
            id="login_buff",
            label="Login BUFF",
            description="Abre BUFF en navegador visible y guarda la sesion local.",
            command=[
                sys.executable,
                "-u",
                "-m",
                "apps.cli.scrape_candidate_platforms",
                "--login-only",
                "--no-steam",
                "--buff",
                "--show-browser",
                "--login-wait",
                "180",
            ],
            group="login",
        ),
        LocalCommand(
            id="refresh_history_steam",
            label="Refrescar historico Steam",
            description="Actualiza articulos con mas de 8 horas sin tocar BUFF.",
            command=[
                sys.executable,
                "-u",
                "-m",
                "apps.cli.refresh_market_history",
                "--stale-minutes",
                "480",
                "--persist",
                "--no-buff",
            ],
            destructive=True,
        ),
        LocalCommand(
            id="refresh_history_with_buff",
            label="Refrescar historico Steam+BUFF",
            description="Actualiza Steam y BUFF. Usar solo si la cuenta de BUFF esta disponible.",
            command=[
                sys.executable,
                "-u",
                "-m",
                "apps.cli.refresh_market_history",
                "--stale-minutes",
                "480",
                "--persist",
                "--buff",
            ],
            destructive=True,
        ),
    )


def _local_command(command_id: str) -> LocalCommand | None:
    return next((command for command in _local_commands() if command.id == command_id), None)


def _command_payload(command: LocalCommand) -> dict[str, Any]:
    return {
        "id": command.id,
        "label": command.label,
        "description": command.description,
        "group": command.group,
        "destructive": command.destructive,
    }


def _session_payload() -> dict[str, dict[str, Any]]:
    return {
        "steam": read_session_metadata(
            platform="steam",
            state_path=Path("data/browser-state/steam_storage_state.json"),
        ),
        "buff": read_session_metadata(
            platform="buff",
            state_path=Path("data/browser-state/buff_storage_state.json"),
        ),
    }


def _web_scrape_command(
    *,
    show_browser: bool = False,
    refresh: bool = False,
    scrape_buff: bool = True,
    refresh_buff: bool = False,
) -> list[str]:
    return build_scrape_job_command(
        _web_scrape_env(
            show_browser=show_browser,
            refresh=refresh,
            scrape_buff=scrape_buff,
            refresh_buff=refresh_buff,
        )
    )


def _web_scrape_env(
    *,
    show_browser: bool = False,
    refresh: bool = False,
    scrape_buff: bool = True,
    refresh_buff: bool = False,
) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("SCRAPE_STREAMING", "true")
    env.setdefault("SCRAPE_CANDIDATE_LIMIT", "25")
    env.setdefault("SCRAPE_ALL_PROFILES", "true")
    env.update(platform_env(PlatformSelection(steam=True, buff=scrape_buff)))
    env["SCRAPE_REFRESH"] = "true" if refresh else "false"
    env["SCRAPE_REFRESH_BUFF"] = "true" if refresh and refresh_buff else "false"
    env.setdefault("SCRAPE_STALE_MINUTES", "480")
    env.setdefault("SCRAPE_STEAM_CONCURRENCY", "2")
    env.setdefault("SCRAPE_BUFF_CONCURRENCY", "1")
    env.setdefault("SCRAPE_BUFF_CAPTCHA_WAIT_SECONDS", "300")
    env.setdefault("SCRAPE_SCORE", "true")
    env.setdefault("SCRAPE_CONCURRENT_PLATFORMS", "true")
    env.setdefault("SCRAPE_PERSIST", "true")
    env["SCRAPE_SHOW_BROWSER"] = "true" if show_browser else "false"
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve apps/web with live DB data.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--web-dir", type=Path, default=Path("apps/web"))
    args = parser.parse_args()

    web_dir = args.web_dir.resolve()

    class StaticDashboardHandler(DashboardHandler):
        def __init__(self, *handler_args: Any, **handler_kwargs: Any) -> None:
            super().__init__(*handler_args, directory=str(web_dir), **handler_kwargs)

    server = DashboardHTTPServer(
        (args.host, args.port),
        StaticDashboardHandler,
        scrape_runner=ScrapeJobRunner(),
    )
    print(f"web_dashboard_server listening http://{args.host}:{args.port}", flush=True)
    print(f"web_dir={web_dir}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
