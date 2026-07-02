"""Serve the local web dashboard with live database-backed JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from apps.cli.scrape_job_server import (
    ScrapeJobRunner,
    _snapshot_payload,
    build_scrape_job_command,
)
from packages.persistence.connection import create_pool
from packages.runtime_config import load_runtime_config
from packages.web import build_dashboard_payload, market_items_query


class DashboardHandler(SimpleHTTPRequestHandler):
    server: "DashboardHTTPServer"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/dashboard":
            self._write_dashboard(parsed.query)
            return
        if parsed.path == "/api/scrape/status":
            self._write_scrape_status()
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/scrape/start":
            self._start_scrape_job()
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

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

    def _start_scrape_job(self) -> None:
        command = _web_scrape_command()
        started = self.server.scrape_runner.start(command)
        status = HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT
        payload = _scrape_status_payload(self.server.scrape_runner)
        payload["status"] = "started" if started else "already_running"
        self._write_json(status, payload)

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
    raw = (parse_qs(query).get("limit") or ["100"])[0]
    try:
        value = int(raw)
    except ValueError:
        return 100
    return min(max(value, 1), 500)


def _scrape_status_payload(runner: ScrapeJobRunner) -> dict[str, Any]:
    return {
        "job": _snapshot_payload(runner.snapshot()),
        "command": _web_scrape_command(),
    }


def _web_scrape_command() -> list[str]:
    return build_scrape_job_command(_web_scrape_env())


def _web_scrape_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("SCRAPE_STREAMING", "true")
    env.setdefault("SCRAPE_CANDIDATE_LIMIT", "50")
    env.setdefault("SCRAPE_ALL_PROFILES", "true")
    env.setdefault("SCRAPE_STEAM", "true")
    env.setdefault("SCRAPE_BUFF", "true")
    env.setdefault("SCRAPE_REFRESH", "true")
    env.setdefault("SCRAPE_PERSIST", "true")
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve apps/web with live DB data.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--web-dir", type=Path, default=Path("apps/web"))
    args = parser.parse_args()

    web_dir = args.web_dir.resolve()
    server = DashboardHTTPServer(
        (args.host, args.port),
        lambda *handler_args: DashboardHandler(*handler_args, directory=str(web_dir)),
        scrape_runner=ScrapeJobRunner(),
    )
    print(f"web_dashboard_server listening http://{args.host}:{args.port}", flush=True)
    print(f"web_dir={web_dir}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
