import sys
import threading
from collections.abc import Sequence

from apps.cli.scrape_job_server import (
    ScrapeJobRunner,
    _bearer_token,
    _bool,
    _query_token,
    build_scrape_job_command,
)


def test_build_scrape_job_command_defaults_to_eight_hour_persisted_run() -> None:
    assert build_scrape_job_command({}) == [
        sys.executable,
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
            "SCRAPE_STALE_MINUTES": "720",
            "SCRAPE_REFRESH_LIMIT": "10",
            "SCRAPE_PERSIST": "false",
            "SCRAPE_SHOW_BROWSER": "true",
        }
    )

    assert command == [
        sys.executable,
        "-m",
        "apps.cli.auto_scrape_loop",
        "25",
        "--once",
        "--stale-minutes",
        "720",
        "--refresh-limit",
        "10",
        "--no-persist",
        "--show-browser",
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


def test_tokens_can_come_from_header_or_query() -> None:
    assert _bearer_token("Bearer secret") == "secret"
    assert _bearer_token("Basic secret") is None
    assert _query_token("token=secret") == "secret"


def test_playwright_runtime_check_defaults_to_enabled() -> None:
    assert _bool(None, default=True) is True
    assert _bool("false", default=True) is False
