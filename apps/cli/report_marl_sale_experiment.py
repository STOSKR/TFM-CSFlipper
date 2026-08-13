"""Build a compact, reproducible report for the MARL buy-hold-sell flow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from apps.cli.run_marl_episode import run


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    policies = ("hold", "buy-positive", "buy-and-sell")
    runs = {
        policy: run(
            argparse.Namespace(
                dataset_dir=args.dataset_dir,
                split=args.split,
                limit=args.limit,
                cash=args.cash,
                policy=policy,
                supervised_probability=args.supervised_probability,
            )
        )
        for policy in policies
    }
    return {
        "experiment": "marl_buy_hold_sell_functional",
        "dataset_dir": None if args.dataset_dir is None else str(args.dataset_dir),
        "split": args.split,
        "limit": args.limit,
        "initial_cash_eur": args.cash,
        "supervised_probability": args.supervised_probability,
        "policies": {policy: _summary(result) for policy, result in runs.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare hold, buy-only and buy-hold-sell MARL baseline policies."
    )
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=95)
    parser.add_argument("--cash", type=float, default=1000.0)
    parser.add_argument(
        "--supervised-probability",
        dest="supervised_probability",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--no-supervised-probability",
        dest="supervised_probability",
        action="store_false",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args)
    rendered = json.dumps(report, indent=2, ensure_ascii=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    trace = result["trace"][1:]
    purchases = sum(step["infos"]["trader"]["executed_buy"] for step in trace)
    sales = sum(step["infos"]["trader"]["executed_sale"] for step in trace)
    return {
        "purchases": purchases,
        "sales": sales,
        "cash_available_eur": result["cash_available_eur"],
        **result["portfolio"],
    }


if __name__ == "__main__":
    main()
