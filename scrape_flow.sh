#!/usr/bin/env sh
set -eu

python steamdt.py --show
python market_workers.py --show-browser --persist
