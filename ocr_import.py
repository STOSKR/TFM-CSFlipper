"""Short wrapper for OCR observation imports.

Examples:
    python ocr_import.py tests/fixtures/ocr_observations.txt
    python ocr_import.py capture.png --min-confidence 0.7 --persist
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Import OCR observations.")
    parser.add_argument("path", help="Image capture or .txt OCR fixture")
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--persist", action="store_true", help="Persist instead of dry-run")
    args = parser.parse_args()

    command = [
        sys.executable,
        "-m",
        "apps.cli.import_ocr_observations",
        args.path,
        "--min-confidence",
        str(args.min_confidence),
    ]
    if args.persist:
        command.append("--persist")
    else:
        command.append("--dry-run")

    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
