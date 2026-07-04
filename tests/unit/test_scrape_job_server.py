import sys
import threading
from collections.abc import Sequence

from apps.cli.scrape_job_server import (
    ScrapeJobRunner,
    _bearer_token,
    _bool,
    _expected_stream_batches,
    _progress_from_line,
    _public_job_line,
    _query_token,
    _run_command,
    _subprocess_env,
    build_scrape_job_command,
)


def test_build_scrape_job_command_defaults_to_eight_hour_persisted_run() -> None:
    assert build_scrape_job_command({}) == [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.auto_scrape_loop",
        "--once",
        "--stale-minutes",
        "480",
        "--persist",
    ]


def test_build_scrape_job_command_accepts_render_env_overrides() -> None:
    command = build_scrape_job_command(
        {
            "SCRAPE_CANDIDATE_LIMIT": "25",
            "SCRAPE_ALL_PROFILES": "false",
            "SCRAPE_STEAMDT_TIMEOUT": "30",
            "SCRAPE_STEAMDT_RETRIES": "1",
            "SCRAPE_STEAMDT_PROFILE_TIMEOUT": "120",
            "SCRAPE_STALE_MINUTES": "720",
            "SCRAPE_REFRESH_LIMIT": "10",
            "SCRAPE_PERSIST": "false",
            "SCRAPE_SHOW_BROWSER": "true",
        }
    )

    assert command == [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.auto_scrape_loop",
        "25",
        "--no-all-profiles",
        "--steamdt-timeout",
        "30",
        "--steamdt-retries",
        "1",
        "--steamdt-profile-timeout",
        "120",
        "--once",
        "--stale-minutes",
        "720",
        "--refresh-limit",
        "10",
        "--no-persist",
        "--show-browser",
    ]


def test_build_scrape_job_command_can_run_refresh_only() -> None:
    command = build_scrape_job_command(
        {
            "SCRAPE_REFRESH_ONLY": "true",
            "SCRAPE_STALE_MINUTES": "1440",
            "SCRAPE_REFRESH_LIMIT": "5",
            "SCRAPE_PERSIST": "true",
            "SCRAPE_SHOW_BROWSER": "false",
        }
    )

    assert command == [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.refresh_market_history",
        "--stale-minutes",
        "1440",
        "--limit",
        "5",
        "--persist",
        "--no-concurrent-platforms",
    ]


def test_build_scrape_job_command_can_run_streaming_flow() -> None:
    command = build_scrape_job_command(
        {
            "SCRAPE_STREAMING": "true",
            "SCRAPE_CANDIDATE_LIMIT": "50",
            "SCRAPE_ALL_PROFILES": "false",
            "SCRAPE_STEAMDT_TIMEOUT": "30",
            "SCRAPE_STEAMDT_RETRIES": "1",
            "SCRAPE_STEAMDT_PROFILE_TIMEOUT": "120",
            "SCRAPE_STALE_MINUTES": "480",
            "SCRAPE_REFRESH_LIMIT": "50",
            "SCRAPE_BATCH_SIZE": "1",
            "SCRAPE_QUEUE_SIZE": "2",
            "SCRAPE_PERSIST": "true",
        }
    )

    assert command == [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.render_stream_scrape",
        "50",
        "--no-all-profiles",
        "--steamdt-timeout",
        "30",
        "--steamdt-retries",
        "1",
        "--steamdt-profile-timeout",
        "120",
        "--stale-minutes",
        "480",
        "--refresh-limit",
        "50",
        "--batch-size",
        "1",
        "--queue-size",
        "2",
        "--persist",
        "--no-concurrent-platforms",
    ]


def test_build_streaming_scrape_job_command_accepts_platform_and_refresh_overrides() -> None:
    command = build_scrape_job_command(
        {
            "SCRAPE_STREAMING": "true",
            "SCRAPE_CANDIDATE_LIMIT": "2",
            "SCRAPE_STEAM": "true",
            "SCRAPE_BUFF": "false",
            "SCRAPE_STEAM_API": "true",
            "SCRAPE_REFRESH": "false",
            "SCRAPE_STEAM_CONCURRENCY": "4",
            "SCRAPE_BUFF_CONCURRENCY": "2",
        }
    )

    assert command == [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.render_stream_scrape",
        "2",
        "--steam",
        "--no-buff",
        "--steam-api",
        "--stale-minutes",
        "480",
        "--steam-concurrency",
        "4",
        "--buff-concurrency",
        "2",
        "--no-refresh",
        "--persist",
        "--no-concurrent-platforms",
    ]


def test_scrape_job_runner_rejects_overlapping_runs() -> None:
    started = threading.Event()
    release = threading.Event()

    def runner(command: Sequence[str]) -> int:
        assert command == ("job",)
        started.set()
        release.wait(timeout=2)
        return 0

    job_runner = ScrapeJobRunner(command_runner=runner)

    assert job_runner.start(["job"]) is True
    assert started.wait(timeout=2) is True
    assert job_runner.start(["job"]) is False

    release.set()
    job_runner.wait(timeout=2)
    snapshot = job_runner.snapshot()
    assert snapshot.running is False
    assert snapshot.last_return_code == 0
    assert snapshot.progress_text == "Completado"


def test_scrape_job_runner_mirrors_child_output_to_terminal(capsys) -> None:
    job_runner = ScrapeJobRunner()

    job_runner._append_log_line("stream_batch=1 candidates=1")

    assert "scrape_job_output stream_batch=1 candidates=1" in capsys.readouterr().out


def test_run_command_stops_silent_child_process(monkeypatch) -> None:
    lines: list[str] = []
    monkeypatch.setenv("SCRAPE_ENSURE_PLAYWRIGHT", "false")
    monkeypatch.setenv("SCRAPE_JOB_STALL_SECONDS", "1")

    return_code = _run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        log=lines.append,
    )

    assert return_code == 124
    assert "job_stalled seconds=1" in lines


def test_scrape_progress_parser_maps_streaming_steps() -> None:
    assert _progress_from_line("job_started") == (1, "Arrancando")
    assert _progress_from_line("playwright_check=start") == (2, "Preparando navegador")
    assert _progress_from_line("playwright_check=ready") == (3, "Navegador listo")
    assert _progress_from_line("job_stalled seconds=120") == (
        20,
        "Sin progreso, proceso detenido",
    )
    assert _progress_from_line("job_timeout seconds=600") == (
        20,
        "Timeout, proceso detenido",
    )
    assert _progress_from_line("render_stream_strategy=steam_sell_slow") == (
        8,
        "Buscando candidatos",
    )
    assert _progress_from_line("stream_scrape_batch candidates=5") == (
        20,
        "Consultando Steam y BUFF",
    )
    assert _progress_from_line("stream_batch=7 candidates=5", expected_batches=20) == (
        35,
        "Scraping lote 7/20",
    )
    assert _progress_from_line("stream_batch_done=20 snapshots=5", expected_batches=20) == (
        64,
        "Lote 20/20 completado",
    )
    assert _progress_from_line("platform_start=steam total=4 concurrency=2") == (
        20,
        "STEAM iniciado: 4 items, 2 workers",
    )
    assert _progress_from_line("buff_browser=launch_start") == (
        20,
        "BUFF lanzando navegador",
    )
    assert _progress_from_line("steam_browser=context_ready") == (
        20,
        "STEAM contexto listo",
    )
    assert _progress_from_line("steam_fetch_start=1/4 item=A") == (
        20,
        "STEAM consultando 1/4",
    )
    assert _progress_from_line("buff_fetch_start=2/4 item=A") == (
        20,
        "BUFF consultando 2/4",
    )
    assert _progress_from_line("steam_progress=2/4 ok=2 errors=0 state=ok last=A") == (
        20,
        "STEAM 2/4",
    )
    assert _progress_from_line("buff_progress=1/4 ok=1 errors=0 state=ok last=A") == (
        20,
        "BUFF 1/4",
    )
    assert _progress_from_line("platform_done=buff163 ok=3 errors=1") == (
        20,
        "BUFF terminado: ok=3, errores=1",
    )
    assert _progress_from_line("platform_error=steam message=TimeoutError") == (
        20,
        "STEAM error: TimeoutError",
    )
    assert _progress_from_line("[2/4] AK-47 steam=ok") == (82, "Historico 2/4")
    assert _progress_from_line(
        "summary loaded=2 snapshots=2 history_points_ready=8 history_points_persisted=8"
    ) == (90, "Historico guardado: 8 puntos")


def test_public_job_line_hides_raw_python_commands() -> None:
    assert _public_job_line(f"{sys.executable} -u -m apps.cli.refresh_market_history") is None
    assert _public_job_line(" render_stream_step=refresh ") == "render_stream_step=refresh"


def test_expected_stream_batches_uses_profiles_limit_and_batch_size() -> None:
    command = [
        sys.executable,
        "-u",
        "-m",
        "apps.cli.render_stream_scrape",
        "50",
        "--all-profiles",
        "--batch-size",
        "5",
    ]

    assert _expected_stream_batches(command) == 20


def test_tokens_can_come_from_header_or_query() -> None:
    assert _bearer_token("Bearer secret") == "secret"
    assert _bearer_token("Basic secret") is None
    assert _query_token("token=secret") == "secret"


def test_playwright_runtime_check_defaults_to_enabled() -> None:
    assert _bool(None, default=True) is True
    assert _bool("false", default=True) is False


def test_playwright_browser_path_defaults_to_project_install() -> None:
    assert _subprocess_env({})["PLAYWRIGHT_BROWSERS_PATH"] == "0"
    assert _subprocess_env({"PLAYWRIGHT_BROWSERS_PATH": "/cache"})[
        "PLAYWRIGHT_BROWSERS_PATH"
    ] == "/cache"


def test_subprocess_env_defaults_to_unbuffered_python() -> None:
    assert _subprocess_env({})["PYTHONUNBUFFERED"] == "1"
    assert _subprocess_env({"PYTHONUNBUFFERED": "0"})["PYTHONUNBUFFERED"] == "0"
