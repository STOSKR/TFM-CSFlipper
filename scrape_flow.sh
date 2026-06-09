#!/usr/bin/env sh
set -eu

python steamdt.py 50 --show
python market_workers.py --show-browser --persist
