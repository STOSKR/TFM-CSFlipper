"""Short wrapper for platform workers fed by a SteamDT candidate JSON.

Examples:
    python market_workers.py --candidates data/flow-runs/steamdt_candidates.json
    python market_workers.py --candidates candidates.json --show-browser --buff-login
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "apps.cli.scrape_candidate_platforms",
        *sys.argv[1:],
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
