"""Run SteamDT discovery and platform workers as one local flow."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def default_candidates_path() -> Path:
    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return Path("data/flow-runs") / f"steamdt_candidates_flow_{run_id}.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run SteamDT discovery, then scrape Steam/BUFF workers."
    )
    parser.add_argument("limit", nargs="?", type=int, help="Number of SteamDT candidates")
    parser.add_argument(
        "--output",
        type=Path,
        help="Where to save the SteamDT candidates JSON used by workers.",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Show browser windows for SteamDT and platform workers.",
    )
    parser.add_argument("--persist", action="store_true", help="Persist market snapshots.")
    parser.add_argument("--fast", action="store_true", help="Use SteamDT fast profile override.")
    parser.add_argument(
        "--all-profiles",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override csflipper_config.toml and run every configured SteamDT profile.",
    )
    parser.add_argument(
        "--steamdt-timeout",
        type=int,
        help="Seconds to wait for SteamDT navigation and key selectors.",
    )
    parser.add_argument(
        "--steamdt-retries",
        type=int,
        help="Retries for the initial SteamDT page navigation.",
    )
    parser.add_argument(
        "--steamdt-profile-timeout",
        type=int,
        help="Maximum seconds allowed for each SteamDT strategy.",
    )
    parser.add_argument("--min", dest="min_price", type=float, help="Minimum SteamDT price filter")
    parser.add_argument("--max", dest="max_price", type=float, help="Maximum SteamDT price filter")
    parser.add_argument("--vol", dest="min_volume", type=int, help="Minimum SteamDT volume filter")
    parser.add_argument("--no-buff", action="store_true", help="Disable BUFF in SteamDT discovery.")
    parser.add_argument("--uu", action="store_true", help="Enable UU in SteamDT discovery.")
    parser.add_argument("--no-uu", action="store_true", help="Disable UU in SteamDT discovery.")
    parser.add_argument("--c5", action="store_true", help="Enable C5GAME in SteamDT discovery.")
    parser.add_argument(
        "--enrich-links",
        action="store_true",
        help="Open SteamDT detail pages only when platform links are missing.",
    )
    parser.add_argument(
        "--steam-login",
        action="store_true",
        help="Wait for manual Steam login in platform workers.",
    )
    parser.add_argument(
        "--buff-login",
        action="store_true",
        help="Wait for manual BUFF login in platform workers.",
    )
    parser.add_argument(
        "--steam-api",
        action="store_true",
        help="Use Steam priceoverview HTTP API instead of Steam browser worker.",
    )
    parser.add_argument(
        "--concurrent-platforms",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Run Steam and BUFF workers concurrently.",
    )
    parser.add_argument("--batch-size", type=int, help="Number of candidates per worker batch.")
    parser.add_argument("--steam-concurrency", type=int, help="Concurrent Steam requests.")
    parser.add_argument("--buff-concurrency", type=int, help="Concurrent BUFF browser pages.")
    args = parser.parse_args()

    candidates_path = args.output or default_candidates_path()
    candidates_path.parent.mkdir(parents=True, exist_ok=True)

    steamdt_command = build_steamdt_command(args, candidates_path)
    workers_command = build_workers_command(args, candidates_path)

    print("flow_step=steamdt")
    print(" ".join(str(part) for part in steamdt_command))
    first_result = subprocess.run(steamdt_command, check=False)
    if first_result.returncode != 0:
        return first_result.returncode

    print("flow_step=market_workers")
    print(" ".join(str(part) for part in workers_command))
    second_result = subprocess.run(workers_command, check=False)
    return second_result.returncode


def build_steamdt_command(args: argparse.Namespace, candidates_path: Path) -> list[str]:
    command = [sys.executable, "steamdt.py"]
    if args.limit is not None:
        command.append(str(args.limit))
    if args.show_browser:
        command.append("--show")
    if args.fast:
        command.append("--fast")
    if args.all_profiles is not None:
        command.append("--all-profiles" if args.all_profiles else "--no-all-profiles")
    if args.steamdt_timeout is not None:
        command.extend(["--timeout", str(args.steamdt_timeout)])
    if args.steamdt_retries is not None:
        command.extend(["--retries", str(args.steamdt_retries)])
    if args.steamdt_profile_timeout is not None:
        command.extend(["--profile-timeout", str(args.steamdt_profile_timeout)])
    if args.min_price is not None:
        command.extend(["--min", str(args.min_price)])
    if args.max_price is not None:
        command.extend(["--max", str(args.max_price)])
    if args.min_volume is not None:
        command.extend(["--vol", str(args.min_volume)])
    if args.no_buff:
        command.append("--no-buff")
    if args.uu:
        command.append("--uu")
    if args.no_uu:
        command.append("--no-uu")
    if args.c5:
        command.append("--c5")
    if args.enrich_links:
        command.append("--enrich-links")
    command.extend(["--output", str(candidates_path)])
    return command


def build_workers_command(args: argparse.Namespace, candidates_path: Path) -> list[str]:
    command = [
        sys.executable,
        "market_workers.py",
        "--candidates",
        str(candidates_path),
    ]
    if args.show_browser:
        command.append("--show-browser")
    if args.persist:
        command.append("--persist")
    if args.steam_login:
        command.append("--steam-login")
    if args.buff_login:
        command.append("--buff-login")
    if args.no_buff:
        command.append("--no-buff")
    if args.steam_api:
        command.append("--steam-api")
    if args.concurrent_platforms is not None:
        command.append(
            "--concurrent-platforms" if args.concurrent_platforms else "--no-concurrent-platforms"
        )
    if args.batch_size is not None:
        command.extend(["--batch-size", str(args.batch_size)])
    if args.steam_concurrency is not None:
        command.extend(["--steam-concurrency", str(args.steam_concurrency)])
    if args.buff_concurrency is not None:
        command.extend(["--buff-concurrency", str(args.buff_concurrency)])
    return command


if __name__ == "__main__":
    raise SystemExit(main())
