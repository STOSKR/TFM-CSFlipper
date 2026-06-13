"""Short wrapper for SteamDT discovery.

Examples:
    python steamdt.py
    python steamdt.py 20
    python steamdt.py 20 --fast --show
    python steamdt.py 10 --steam
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from packages.runtime_config import load_runtime_config

DEFAULT_OUTPUT_DIR = Path("data/flow-runs")


def default_candidates_path() -> Path:
    run_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"steamdt_candidates_{run_id}.json"


def main() -> int:
    runtime_config = load_runtime_config()
    parser = argparse.ArgumentParser(description="Short SteamDT scraper wrapper.")
    parser.add_argument(
        "limit",
        nargs="?",
        type=int,
        default=runtime_config.discovery.candidates_limit,
        help="Number of items to print",
    )
    parser.add_argument("--fast", action="store_true", help="Use platform_arbitrage_fast profile")
    parser.add_argument("--show", action="store_true", help="Show browser while scraping")
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Seconds to wait for SteamDT navigation and key selectors",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retries for the initial SteamDT page navigation",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of table")
    parser.add_argument("--steam", action="store_true", help="Also fetch Steam Market prices")
    parser.add_argument("--persist", action="store_true", help="Persist fetched Steam prices")
    parser.add_argument("--output", help="Save discovered candidates to this JSON file")
    parser.add_argument("--no-output", action="store_true", help="Do not save candidates to JSON")
    parser.add_argument(
        "--session-state",
        default="data/browser-state/steamdt_storage_state.json",
        help="File used to load/save browser cookies and localStorage",
    )
    parser.add_argument("--no-session-state", action="store_true", help="Do not load/save session")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Wait with the visible browser open so you can log in before scraping",
    )
    parser.add_argument(
        "--login-wait",
        type=int,
        default=120,
        help="Seconds to wait for manual login when --login is enabled",
    )
    parser.add_argument(
        "--currency",
        default=runtime_config.discovery.currency,
        help="Currency to select in SteamDT",
    )
    parser.add_argument("--min", dest="min_price", type=float, help="Minimum price filter")
    parser.add_argument("--max", dest="max_price", type=float, help="Maximum price filter")
    parser.add_argument("--vol", dest="min_volume", type=int, help="Minimum volume filter")
    parser.add_argument("--no-buff", action="store_true", help="Disable BUFF")
    parser.add_argument("--uu", action="store_true", help="Enable UU")
    parser.add_argument("--no-uu", action="store_true", help="Disable UU")
    parser.add_argument("--c5", action="store_true", help="Enable C5GAME")
    parser.add_argument(
        "--enrich-links",
        action="store_true",
        help="Open SteamDT detail pages only when platform links are missing",
    )
    parser.add_argument(
        "--all-profiles",
        action=argparse.BooleanOptionalAction,
        default=runtime_config.steamdt.run_all_profiles,
        help="Run every SteamDT strategy configured in csflipper_config.toml",
    )
    parser.add_argument(
        "--steam-fee-percent",
        type=float,
        default=float(runtime_config.fees.steam_sale_percent),
    )
    parser.add_argument(
        "--withdrawal-fee-percent",
        type=float,
        default=None,
        help="Overrides the balance-specific withdrawal percent from csflipper_config.toml",
    )
    args = parser.parse_args()

    command = [
        sys.executable,
        "-m",
        "apps.cli.discover_steamdt_hanging",
        "--profile",
        "platform_arbitrage_fast" if args.fast else runtime_config.steamdt.default_profile,
        "--limit",
        str(args.limit),
        "--currency",
        args.currency,
        "--timeout",
        str(args.timeout),
        "--retries",
        str(args.retries),
        "--platform-buff" if not args.no_buff else "--no-platform-buff",
        "--platform-c5game" if args.c5 else "--no-platform-c5game",
    ]
    command.append("--platform-uu" if args.uu and not args.no_uu else "--no-platform-uu")
    if args.min_price is not None:
        command.extend(["--min-price", str(args.min_price)])
    elif runtime_config.discovery.min_price is not None:
        command.extend(["--min-price", str(runtime_config.discovery.min_price)])
    if args.max_price is not None:
        command.extend(["--max-price", str(args.max_price)])
    if args.min_volume is not None:
        command.extend(["--min-volume", str(args.min_volume)])
    elif runtime_config.discovery.min_volume is not None:
        command.extend(["--min-volume", str(runtime_config.discovery.min_volume)])
    command.extend(["--steam-fee-percent", str(args.steam_fee_percent)])
    if args.withdrawal_fee_percent is not None:
        command.extend(["--withdrawal-fee-percent", str(args.withdrawal_fee_percent)])
    if args.show:
        command.append("--show-browser")
    if args.enrich_links:
        command.append("--enrich-links")
    command.append("--all-profiles" if args.all_profiles else "--no-all-profiles")
    if args.json:
        command.extend(["--format", "json"])
    if not args.no_output:
        output_path = Path(args.output) if args.output else default_candidates_path()
        command.extend(["--output", str(output_path)])
    if not args.no_session_state:
        command.extend(["--session-state", args.session_state])
    else:
        command.append("--no-session-state")
    if args.login:
        command.extend(["--login", "--login-wait", str(args.login_wait)])
    if args.steam:
        command.append("--fetch-steam-prices")
    if args.persist:
        command.append("--persist")
    else:
        command.append("--dry-run")

    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
