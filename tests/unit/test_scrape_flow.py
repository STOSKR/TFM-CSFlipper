import argparse
import sys
from pathlib import Path

from scrape_flow import build_steamdt_command, build_workers_command


def test_build_flow_commands_use_explicit_candidates_file() -> None:
    args = argparse.Namespace(
        limit=10,
        show_browser=True,
        fast=False,
        min_price=None,
        max_price=None,
        min_volume=None,
        no_buff=False,
        uu=False,
        no_uu=False,
        c5=False,
        enrich_links=False,
        persist=True,
        steam_login=False,
        buff_login=False,
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
    ]
