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


def main() -> int:
    parser = argparse.ArgumentParser(description="Short SteamDT scraper wrapper.")
    parser.add_argument("limit", nargs="?", type=int, default=5, help="Number of items to print")
    parser.add_argument("--fast", action="store_true", help="Use platform_arbitrage_fast profile")
    parser.add_argument("--show", action="store_true", help="Show browser while scraping")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of table")
    parser.add_argument("--steam", action="store_true", help="Also fetch Steam Market prices")
    parser.add_argument("--persist", action="store_true", help="Persist fetched Steam prices")
    parser.add_argument("--min", dest="min_price", type=float, help="Minimum price filter")
    parser.add_argument("--max", dest="max_price", type=float, help="Maximum price filter")
    parser.add_argument("--vol", dest="min_volume", type=int, help="Minimum volume filter")
    parser.add_argument("--no-buff", action="store_true", help="Disable BUFF")
    parser.add_argument("--no-uu", action="store_true", help="Disable UU")
    parser.add_argument("--c5", action="store_true", help="Enable C5GAME")
    args = parser.parse_args()

    command = [
        sys.executable,
        "-m",
        "apps.cli.discover_steamdt_hanging",
        "--profile",
        "platform_arbitrage_fast" if args.fast else "platform_arbitrage_safe",
        "--limit",
        str(args.limit),
        "--platform-buff" if not args.no_buff else "--no-platform-buff",
        "--platform-uu" if not args.no_uu else "--no-platform-uu",
        "--platform-c5game" if args.c5 else "--no-platform-c5game",
    ]
    if args.min_price is not None:
        command.extend(["--min-price", str(args.min_price)])
    if args.max_price is not None:
        command.extend(["--max-price", str(args.max_price)])
    if args.min_volume is not None:
        command.extend(["--min-volume", str(args.min_volume)])
    if args.show:
        command.append("--show-browser")
    if args.json:
        command.extend(["--format", "json"])
    if args.steam:
        command.append("--fetch-steam-prices")
    if args.persist:
        command.append("--persist")
    else:
        command.append("--dry-run")

    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
