import argparse
import sys
from pathlib import Path

from scrape_flow import build_steamdt_command, build_workers_command


def test_build_flow_commands_use_explicit_candidates_file() -> None:
    args = argparse.Namespace(
        limit=10,
        show_browser=True,
        fast=False,
        all_profiles=None,
        steamdt_timeout=None,
        steamdt_retries=None,
        steamdt_profile_timeout=None,
        min_price=None,
        max_price=None,
        min_volume=None,
        steam=True,
        buff=True,
        uu=False,
        no_uu=False,
        c5=False,
        enrich_links=False,
        persist=True,
        steam_login=False,
        buff_login=False,
        steam_api=False,
        concurrent_platforms=None,
        batch_size=None,
        steam_concurrency=None,
        buff_concurrency=None,
    )
    candidates_path = Path("data/flow-runs/test_candidates.json")

    assert build_steamdt_command(args, candidates_path) == [
        sys.executable,
        "steamdt.py",
        "10",
        "--show",
        "--output",
        str(candidates_path),
    ]
    assert build_workers_command(args, candidates_path) == [
        sys.executable,
        "market_workers.py",
        "--candidates",
        str(candidates_path),
        "--show-browser",
        "--persist",
        "--steam",
        "--buff",
    ]


def test_build_flow_steamdt_command_passes_timeout_options() -> None:
    args = argparse.Namespace(
        limit=3,
        show_browser=False,
        fast=False,
        all_profiles=None,
        steamdt_timeout=90,
        steamdt_retries=3,
        steamdt_profile_timeout=None,
        min_price=None,
        max_price=None,
        min_volume=None,
        steam=True,
        buff=True,
        uu=False,
        no_uu=False,
        c5=False,
        enrich_links=False,
        persist=False,
        steam_login=False,
        buff_login=False,
        steam_api=False,
        concurrent_platforms=None,
        batch_size=None,
        steam_concurrency=None,
        buff_concurrency=None,
    )
    candidates_path = Path("data/flow-runs/test_candidates.json")

    assert build_steamdt_command(args, candidates_path) == [
        sys.executable,
        "steamdt.py",
        "3",
        "--timeout",
        "90",
        "--retries",
        "3",
        "--output",
        str(candidates_path),
    ]


def test_build_flow_steamdt_command_can_force_all_profiles() -> None:
    args = argparse.Namespace(
        limit=3,
        show_browser=False,
        fast=False,
        all_profiles=True,
        steamdt_timeout=None,
        steamdt_retries=None,
        steamdt_profile_timeout=None,
        min_price=None,
        max_price=None,
        min_volume=None,
        steam=True,
        buff=True,
        uu=False,
        no_uu=False,
        c5=False,
        enrich_links=False,
        persist=False,
        steam_login=False,
        buff_login=False,
        steam_api=False,
        concurrent_platforms=None,
        batch_size=None,
        steam_concurrency=None,
        buff_concurrency=None,
    )
    candidates_path = Path("data/flow-runs/test_candidates.json")

    assert build_steamdt_command(args, candidates_path) == [
        sys.executable,
        "steamdt.py",
        "3",
        "--all-profiles",
        "--output",
        str(candidates_path),
    ]


def test_build_flow_steamdt_command_passes_profile_timeout() -> None:
    args = argparse.Namespace(
        limit=3,
        show_browser=False,
        fast=False,
        all_profiles=None,
        steamdt_timeout=None,
        steamdt_retries=None,
        steamdt_profile_timeout=120,
        min_price=None,
        max_price=None,
        min_volume=None,
        steam=True,
        buff=True,
        uu=False,
        no_uu=False,
        c5=False,
        enrich_links=False,
        persist=False,
        steam_login=False,
        buff_login=False,
        steam_api=False,
        concurrent_platforms=None,
        batch_size=None,
        steam_concurrency=None,
        buff_concurrency=None,
    )
    candidates_path = Path("data/flow-runs/test_candidates.json")

    assert build_steamdt_command(args, candidates_path) == [
        sys.executable,
        "steamdt.py",
        "3",
        "--profile-timeout",
        "120",
        "--output",
        str(candidates_path),
    ]


def test_build_flow_workers_command_passes_local_scaling_options() -> None:
    args = argparse.Namespace(
        show_browser=False,
        persist=True,
        steam_login=False,
        buff_login=False,
        steam=True,
        buff=True,
        steam_api=True,
        concurrent_platforms=True,
        batch_size=10,
        steam_concurrency=8,
        buff_concurrency=2,
    )
    candidates_path = Path("data/flow-runs/test_candidates.json")

    assert build_workers_command(args, candidates_path) == [
        sys.executable,
        "market_workers.py",
        "--candidates",
        str(candidates_path),
        "--persist",
        "--steam",
        "--buff",
        "--steam-api",
        "--concurrent-platforms",
        "--batch-size",
        "10",
        "--steam-concurrency",
        "8",
        "--buff-concurrency",
        "2",
    ]


def test_build_flow_workers_command_can_disable_buff_worker() -> None:
    args = argparse.Namespace(
        show_browser=False,
        persist=False,
        steam_login=False,
        buff_login=False,
        steam=True,
        buff=False,
        steam_api=False,
        concurrent_platforms=None,
        batch_size=None,
        steam_concurrency=None,
        buff_concurrency=None,
    )
    candidates_path = Path("data/flow-runs/test_candidates.json")

    assert build_workers_command(args, candidates_path) == [
        sys.executable,
        "market_workers.py",
        "--candidates",
        str(candidates_path),
        "--steam",
        "--no-buff",
    ]
