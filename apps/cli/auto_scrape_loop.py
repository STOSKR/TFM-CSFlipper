"""Run the scraping flow and stale market refresh on a simple interval."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Callable, Sequence

from apps.cli.platform_selection import (
    PlatformSelection,
    add_platform_flags,
    append_platform_flags,
    platform_selection_from_args,
)

Runner = Callable[[Sequence[str]], int]
Sleeper = Callable[[float], None]


def _run_command(command: Sequence[str]) -> int:
    return subprocess.run(command, check=False).returncode


def build_scrape_flow_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, "scrape_flow.py"]
    if args.limit is not None:
        command.append(str(args.limit))
    if args.all_profiles is not None:
        command.append("--all-profiles" if args.all_profiles else "--no-all-profiles")
    if args.steamdt_timeout is not None:
        command.extend(["--steamdt-timeout", str(args.steamdt_timeout)])
    if args.steamdt_retries is not None:
        command.extend(["--steamdt-retries", str(args.steamdt_retries)])
    if args.steamdt_profile_timeout is not None:
        command.extend(["--steamdt-profile-timeout", str(args.steamdt_profile_timeout)])
    if args.persist:
        command.append("--persist")
    if args.show_browser:
        command.append("--show-browser")
    append_platform_flags(command, platform_selection_from_args(args))
    return command


def build_stale_refresh_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "apps.cli.refresh_market_history",
        "--stale-minutes",
        str(args.stale_minutes),
    ]
    if args.persist:
        command.append("--persist")
    append_platform_flags(
        command,
        PlatformSelection(
            steam=bool(getattr(args, "steam", True)),
            buff=bool(getattr(args, "refresh_buff", False)),
        ),
    )
    if args.refresh_limit is not None:
        command.extend(["--limit", str(args.refresh_limit)])
    return command


def run_cycle(args: argparse.Namespace, *, runner: Runner = _run_command) -> int:
    scrape_command = build_scrape_flow_command(args)
    refresh_command = build_stale_refresh_command(args)
    print("auto_step=scrape_flow")
    print(" ".join(scrape_command))
    scrape_code = runner(scrape_command)
    if scrape_code != 0:
        print(f"auto_step=scrape_flow status=failed code={scrape_code}")
        return scrape_code

    print("auto_step=stale_refresh")
    print(" ".join(refresh_command))
    refresh_code = runner(refresh_command)
    if refresh_code != 0:
        print(f"auto_step=stale_refresh status=failed code={refresh_code}")
    return refresh_code


def run_loop(
    args: argparse.Namespace,
    *,
    runner: Runner = _run_command,
    sleeper: Sleeper = time.sleep,
) -> int:
    while True:
        code = run_cycle(args, runner=runner)
        if args.once or code != 0:
            return code
        sleep_seconds = max(1, args.interval_minutes) * 60
        print(f"auto_sleep_seconds={sleep_seconds}")
        sleeper(float(sleep_seconds))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run scrape_flow.py and stale market refresh on an interval."
    )
    parser.add_argument("limit", nargs="?", type=int, help="SteamDT candidate limit.")
    parser.add_argument("--all-profiles", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--steamdt-timeout", type=int)
    parser.add_argument("--steamdt-retries", type=int)
    parser.add_argument("--steamdt-profile-timeout", type=int)
    parser.add_argument("--interval-minutes", type=int, default=60)
    parser.add_argument("--stale-minutes", type=int, default=60)
    parser.add_argument("--refresh-limit", type=int)
    parser.add_argument("--persist", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--show-browser", action="store_true")
    add_platform_flags(parser)
    parser.add_argument("--refresh-buff", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run_loop(args))


if __name__ == "__main__":
    main()
