"""Short wrapper for local candidate prefiltering.

Examples:
    python prefilter.py data/flow-runs/steamdt_candidates.json
    python prefilter.py candidates.json --output selected.json --min-volume 20 --limit 10
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.prediction.baseline import BaselineCandidate, prioritize_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Prefilter SteamDT candidate JSON.")
    parser.add_argument("path", type=Path, help="SteamDT candidates JSON file")
    parser.add_argument("--output", type=Path, help="Where to write selected candidates")
    parser.add_argument("--min-volume", type=int, default=0)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    rows = _load_rows(args.path)
    ranked = prioritize_candidates(
        tuple(_to_baseline_candidate(row) for row in rows),
        min_volume=args.min_volume,
        limit=args.limit,
    )
    selected_ids = {candidate.candidate_id for candidate in ranked}
    selected_rows = [
        row for row in rows if str(row.get("market_hash_name", "")) in selected_ids
    ]

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(selected_rows, indent=2), encoding="utf-8")

    print(
        "prefilter_candidates="
        f"input:{len(rows)} selected:{len(selected_rows)} "
        f"min_volume:{args.min_volume} limit:{args.limit or 'all'}"
    )
    return 0


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("candidate JSON must be a list")
    return [row for row in payload if isinstance(row, dict)]


def _to_baseline_candidate(row: dict[str, Any]) -> BaselineCandidate:
    market_hash_name = str(row.get("market_hash_name") or row.get("item_name") or "")
    return BaselineCandidate(
        candidate_id=market_hash_name,
        market_hash_name=market_hash_name,
        price=_decimal_or_none(row.get("steam_price") or row.get("buff_price")),
        volume=_int_or_none(row.get("volume")),
        expected_return_hint=_percent_to_return(_decimal_or_none(row.get("profitability_percent"))),
    )


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return Decimal(str(value))


def _int_or_none(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(str(value))


def _percent_to_return(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value / Decimal("100") if abs(value) > Decimal("3") else value


if __name__ == "__main__":
    raise SystemExit(main())
