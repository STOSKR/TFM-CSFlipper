"""Short wrapper for manual CSV/JSON observation imports.

Examples:
    python manual_import.py tests/fixtures/manual_observations.csv
    python manual_import.py data/manual_observations.csv --persist
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Import manual CSV/JSON observations.")
    parser.add_argument("path", help="CSV or JSON file to import")
    parser.add_argument("--persist", action="store_true", help="Persist instead of dry-run")
    args = parser.parse_args()

    command = [
        sys.executable,
        "-m",
        "apps.cli.import_observations",
        args.path,
    ]
    if not args.persist:
        command.append("--dry-run")

    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
