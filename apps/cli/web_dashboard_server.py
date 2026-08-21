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
        if parsed.path == "/healthz":
            self._write_json(
                HTTPStatus.OK,
                {"status": "ok", "commands_enabled": _command_execution_enabled()},
            )
            return
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
        if parsed.path == "/api/marl/simulate":
            self._write_marl_simulation()
            return
        if not _command_execution_enabled():
            self._write_json(HTTPStatus.FORBIDDEN, {"error": "commands_disabled"})
            return
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
        commands_enabled = _command_execution_enabled()
        self._write_json(
            HTTPStatus.OK,
            {
                "commands": (
                    [_command_payload(command) for command in _local_commands()]
                    if commands_enabled
                    else []
                ),
                "commands_enabled": commands_enabled,
                "sessions": _session_payload() if commands_enabled else {},
                "job": _snapshot_payload(self.server.scrape_runner.snapshot()),
            },
        )

    def _write_marl_simulation(self) -> None:
        payload = self._read_request_json()
        try:
            result = _marl_simulation_payload(
                cash=_marl_cash(payload.get("cash")),
                policy=_marl_policy(payload.get("policy")),
            )
        except ValueError as exc:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_marl_request", "message": str(exc)},
            )
            return
        except Exception as exc:
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "marl_simulation_failed", "message": str(exc)},
            )
            return
        self._write_json(HTTPStatus.OK, result)

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


def _marl_cash(value: object) -> float:
    try:
        cash = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("El capital inicial debe ser un número.") from exc
    if not 1 <= cash <= 1_000_000:
        raise ValueError("El capital inicial debe estar entre 1 € y 1.000.000 €.")
    return cash


def _marl_policy(value: object) -> str:
    policy = str(value or "buy-and-sell")
    if policy not in {"hold", "buy-positive", "buy-and-sell"}:
        raise ValueError("La política de simulación no es válida.")
    return policy


def _marl_simulation_payload(*, cash: float, policy: str) -> dict[str, Any]:
    """Execute the small deterministic episode used to explain the MARL environment.

    This endpoint never contacts marketplaces or places orders. It intentionally uses
    the controlled two-step scenario so the visible trace remains reproducible.
    """

    from apps.cli.run_marl_episode import run as run_marl_episode

    result = run_marl_episode(
        argparse.Namespace(
            dataset_dir=None,
            split="test",
            limit=5,
            cash=cash,
            supervised_probability=True,
            policy=policy,
        )
    )
    evolution = _marl_evolution(result["trace"], initial_cash_eur=cash)
    candidates = _marl_candidates(evolution)
    return {
        "kind": "controlled_marl_simulation",
        "notice": (
            "Simulación local y reproducible. No consulta mercados ni ejecuta compras reales."
        ),
        "initial_cash_eur": cash,
        "policy": policy,
        "steps": result["steps"],
        "candidates": candidates,
        "evolution": evolution,
        "positions": result["positions"],
        "portfolio": result["portfolio"],
        "cash_available_eur": result["cash_available_eur"],
    }


def _marl_evolution(
    trace: list[dict[str, Any]], *, initial_cash_eur: float
) -> list[dict[str, Any]]:
    evolution: list[dict[str, Any]] = []
    for entry in trace:
        if entry.get("event") != "step":
            continue
        infos = entry.get("infos") or {}
        info = infos.get("portfolio") or infos.get("scout") or {}
        state = info.get("central_state") or {}
        cash_ratio = _finite_number(state.get("cash_available_ratio"))
        blocked_ratio = _finite_number(state.get("blocked_capital_ratio"))
        evolution.append(
            {
                "day": info.get("observed_day"),
                "item_id": info.get("item_id"),
                "item_name": info.get("representation_name"),
                "route": info.get("route_label"),
                "actions": entry.get("actions") or {},
                "outcome": _marl_outcome_label(info),
                "executed_buy": bool(info.get("executed_buy")),
                "executed_sale": bool(info.get("executed_sale")),
                "reward": _finite_number(info.get("reward")),
                "risk_violations": list(info.get("risk_violations") or ()),
                "cash_available_eur": (
                    None if cash_ratio is None else round(cash_ratio * initial_cash_eur, 2)
                ),
                "capital_blocked_eur": (
                    None if blocked_ratio is None else round(blocked_ratio * initial_cash_eur, 2)
                ),
            }
        )
    return evolution


def _marl_candidates(evolution: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for entry in evolution:
        item_id = str(entry.get("item_id") or "unknown")
        candidate = candidates.setdefault(
            item_id,
            {
                "item_name": entry.get("item_name") or "Activo sin nombre",
                "route": entry.get("route") or "Ruta no disponible",
                "observations": 0,
                "first_day": entry.get("day"),
                "last_day": entry.get("day"),
            },
        )
        candidate["observations"] = int(candidate["observations"]) + 1
        candidate["last_day"] = entry.get("day")
    return list(candidates.values())


def _marl_outcome_label(info: dict[str, Any]) -> str:
    if info.get("executed_buy"):
        return "Compra simulada"
    if info.get("executed_sale"):
        return "Venta simulada"
    violations = info.get("risk_violations") or ()
    return "Bloqueada por riesgo" if violations else "Sin operación"


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _command_execution_enabled() -> bool:
    value = os.getenv("WEB_COMMANDS_ENABLED", "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _scrape_status_payload(runner: ScrapeJobRunner) -> dict[str, Any]:
    return {
        "job": _snapshot_payload(runner.snapshot()),
    }


def _local_commands() -> tuple[LocalCommand, ...]:
    return (
        LocalCommand(
            id="login_steam",
            label="Login Steam",
            description="Abre una ventana de Chromium visible para Steam y guarda la sesion local.",
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
                "300",
            ],
            group="login",
        ),
        LocalCommand(
            id="login_buff",
            label="Login BUFF",
            description="Abre una ventana de Chromium visible para BUFF y guarda la sesion local.",
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
                "300",
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
