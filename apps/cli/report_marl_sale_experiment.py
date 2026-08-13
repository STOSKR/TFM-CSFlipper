"""Build a compact, reproducible report for the MARL buy-hold-sell flow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from apps.cli.run_marl_episode import run


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    result = run(
        argparse.Namespace(
            dataset_dir=None,
            split="test",
            limit=2,
            cash=args.cash,
            policy="buy-and-sell",
            supervised_probability=args.supervised_probability,
        )
    )
    position = result["positions"][0]
    return {
        "experiment": "marl_buy_hold_sell_controlled_cycle",
        "purpose": (
            "Functional evidence of a simulated purchase, eight-day trade hold and sale. "
            "It is not a comparison of investment strategies."
        ),
        "initial_cash_eur": args.cash,
        "supervised_probability": args.supervised_probability,
        "cycle": {
            "item_name": position["item_name"],
            "buy_date": position["purchased_at"],
            "unlock_date": position["unlock_at"],
            "sell_date": position["sold_at"],
            "buy_price_eur": position["buy_price_eur"],
            "net_sale_value_eur": position["net_sale_value_eur"],
            "realized_profit_eur": position["realized_profit_eur"],
            "purchases": _summary(result)["purchases"],
            "sales": _summary(result)["sales"],
            "cash_available_eur": result["cash_available_eur"],
            **result["portfolio"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a controlled MARL buy-hold-sell functional report."
    )
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


def _summary(result: dict[str, Any]) -> dict[str, int]:
    trace = result["trace"][1:]
    purchases = sum(step["infos"]["trader"]["executed_buy"] for step in trace)
    sales = sum(step["infos"]["trader"]["executed_sale"] for step in trace)
    return {
        "purchases": purchases,
        "sales": sales,
    }


if __name__ == "__main__":
    main()
