import argparse
import sys
from collections.abc import Sequence

from apps.cli.auto_scrape_loop import (
    build_scrape_flow_command,
    build_stale_refresh_command,
    run_loop,
)


def test_build_auto_scrape_commands_default_to_persisted_hourly_refresh() -> None:
    args = argparse.Namespace(
        limit=50,
        all_profiles=None,
        steamdt_timeout=None,
        steamdt_retries=None,
        steamdt_profile_timeout=None,
        persist=True,
        show_browser=False,
        steam=True,
        buff=True,
        refresh_buff=False,
        stale_minutes=60,
        refresh_limit=None,
    )

    assert build_scrape_flow_command(args) == [
        sys.executable,
        "scrape_flow.py",
        "50",
        "--persist",
        "--steam",
        "--buff",
    ]
    assert build_stale_refresh_command(args) == [
        sys.executable,
        "-m",
        "apps.cli.refresh_market_history",
        "--stale-minutes",
        "60",
        "--persist",
        "--steam",
        "--no-buff",
    ]


def test_build_auto_scrape_command_passes_steamdt_overrides() -> None:
    args = argparse.Namespace(
        limit=5,
        all_profiles=False,
        steamdt_timeout=30,
        steamdt_retries=1,
        steamdt_profile_timeout=120,
        persist=True,
        show_browser=False,
        steam=True,
        buff=True,
    )

    assert build_scrape_flow_command(args) == [
        sys.executable,
        "scrape_flow.py",
        "5",
        "--no-all-profiles",
        "--steamdt-timeout",
        "30",
        "--steamdt-retries",
        "1",
        "--steamdt-profile-timeout",
        "120",
        "--persist",
        "--steam",
        "--buff",
    ]


def test_build_auto_scrape_command_can_opt_into_buff() -> None:
    args = argparse.Namespace(
        limit=None,
        all_profiles=None,
        steamdt_timeout=None,
        steamdt_retries=None,
        steamdt_profile_timeout=None,
        persist=True,
        show_browser=False,
        steam=True,
        buff=True,
    )

    assert build_scrape_flow_command(args) == [
        sys.executable,
        "scrape_flow.py",
        "--persist",
        "--steam",
        "--buff",
    ]


def test_build_auto_scrape_command_can_disable_buff() -> None:
    args = argparse.Namespace(
        limit=None,
        all_profiles=None,
        steamdt_timeout=None,
        steamdt_retries=None,
        steamdt_profile_timeout=None,
        persist=True,
        show_browser=False,
        steam=True,
        buff=False,
    )

    assert build_scrape_flow_command(args) == [
        sys.executable,
        "scrape_flow.py",
        "--persist",
        "--steam",
        "--no-buff",
    ]


def test_build_auto_refresh_can_opt_into_buff_history() -> None:
    args = argparse.Namespace(
        persist=True,
        stale_minutes=60,
        refresh_limit=None,
        steam=True,
        refresh_buff=True,
    )

    assert build_stale_refresh_command(args) == [
        sys.executable,
        "-m",
        "apps.cli.refresh_market_history",
        "--stale-minutes",
        "60",
        "--persist",
        "--steam",
        "--buff",
    ]


def test_run_loop_once_runs_scrape_then_stale_refresh() -> None:
    calls: list[tuple[str, ...]] = []
    args = argparse.Namespace(
        limit=None,
        all_profiles=None,
        steamdt_timeout=None,
        steamdt_retries=None,
        steamdt_profile_timeout=None,
        persist=True,
        show_browser=False,
        steam=True,
        buff=True,
        refresh_buff=False,
        stale_minutes=60,
        refresh_limit=25,
        interval_minutes=60,
        once=True,
    )

    def runner(command: Sequence[str]) -> int:
        calls.append(tuple(command))
        return 0

    code = run_loop(args, runner=runner)

    assert code == 0
    assert calls == [
        (sys.executable, "scrape_flow.py", "--persist", "--steam", "--buff"),
        (
            sys.executable,
            "-m",
            "apps.cli.refresh_market_history",
            "--stale-minutes",
            "60",
            "--persist",
            "--steam",
            "--no-buff",
            "--limit",
            "25",
        ),
    ]
