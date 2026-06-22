#!/usr/bin/env bash
set -euo pipefail

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-0}"

python -m pip install --upgrade pip
python -m pip install .
python -m playwright install chromium
python - <<'PY'
from pathlib import Path

from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    chromium_path = Path(playwright.chromium.executable_path)
    print(f"playwright_chromium={chromium_path}")
    if not chromium_path.exists():
        raise SystemExit(f"Chromium was not installed at {chromium_path}")
PY
