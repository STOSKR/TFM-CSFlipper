"""Run a small MARL market episode without RLlib."""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.marl import MarketEpisodeStep, MarketMARLEnvironment, load_market_episode_steps
from packages.simulation import BUFF, STEAM


def run(args: argparse.Namespace) -> dict[str, Any]:
    steps = (
        load_market_episode_steps(args.dataset_dir, split=args.split, limit=args.limit)
        if args.dataset_dir
        else _demo_steps()
    )
    env = MarketMARLEnvironment(
        steps,
        initial_cash_eur=Decimal(str(args.cash)),
        include_supervised_probability=args.supervised_probability,
    )
    observations, infos = env.reset()
    trace: list[dict[str, Any]] = [
        {
            "event": "reset",
            "observations": observations,
            "infos": infos,
        }
    ]

    while env.agents:
        actions = _policy_actions(observations, args.policy)
        observations, rewards, terminations, truncations, infos = env.step(actions)
        trace.append(
            {
                "event": "step",
                "actions": actions,
                "rewards": rewards,
                "terminations": terminations,
                "truncations": truncations,
                "infos": infos,
            }
        )

    return {
        "steps": len(steps),
        "policy": args.policy,
        "positions": [
            {
                "position_id": position.position_id,
                "item_id": position.item_id,
                "item_name": position.item_name,
                "buy_platform": position.buy_platform,
                "buy_price_eur": float(position.buy_price_eur),
                "purchased_at": position.purchased_at.isoformat(),
                "unlock_at": position.unlock_at.isoformat(),
                "sold_at": None if position.sold_at is None else position.sold_at.isoformat(),
                "sell_platform": position.sell_platform,
                "net_sale_value_eur": _decimal_or_none(position.net_sale_value_eur),
                "realized_profit_eur": _decimal_or_none(position.realized_profit_eur),
            }
            for position in env.simulator.positions
        ],
        "cash_available_eur": float(env.simulator.cash_available_eur),
        "portfolio": _portfolio_summary(env, steps[-1].observed_day),
        "trace": trace,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local MARL episode smoke simulation.")
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--cash", type=float, default=100.0)
    parser.add_argument(
        "--supervised-probability",
        dest="supervised_probability",
        action="store_true",
        default=True,
        help="Include supervised probability features in MARL observations.",
    )
    parser.add_argument(
        "--no-supervised-probability",
        dest="supervised_probability",
        action="store_false",
        help="Disable supervised probability features for ablation smoke tests.",
    )
    parser.add_argument(
        "--policy",
        choices=("buy-positive", "buy-and-sell", "hold"),
        default="buy-positive",
        help="Simple hand-written policy used only for smoke testing.",
    )
    args = parser.parse_args()
    # El terminal predeterminado de Windows puede usar cp1252. Escapar los
    # nombres de artículos mantiene el JSON portable aunque incluyan símbolos
    # como una estrella de objeto excepcional.
    print(json.dumps(run(args), indent=2, ensure_ascii=True))


def _policy_actions(observations: dict[str, dict[str, float]], policy: str) -> dict[str, int]:
    if policy == "hold":
        return {"scout": 0, "trader": 0, "portfolio": 0}
    if (
        policy == "buy-and-sell"
        and observations.get("trader", {}).get("matching_sellable_positions", 0.0) > 0
    ):
        return {"scout": 0, "trader": 2, "portfolio": 1}
    current_return = observations.get("scout", {}).get("current_return", 0.0)
    should_buy = int(current_return > 0)
    return {"scout": should_buy, "trader": should_buy, "portfolio": should_buy}


def _demo_steps() -> tuple[MarketEpisodeStep, ...]:
    return (
        MarketEpisodeStep(
            item_id="buff-to-steam",
            representation_name="AK-47 | Slate_FT_0",
            observed_day=date(2026, 1, 1),
            buy_platform=BUFF,
            buy_price_type="listing",
            sell_platform=STEAM,
            sell_price_type="listing",
            buy_price_eur=Decimal("10"),
            current_exit_net_eur=Decimal("12"),
            current_return=Decimal("0.20"),
            available_quantity=3,
            supervised_probability=Decimal("0.80"),
        ),
        MarketEpisodeStep(
            item_id="buff-to-steam",
            representation_name="AK-47 | Slate_FT_0",
            observed_day=date(2026, 1, 9),
            buy_platform=BUFF,
            buy_price_type="listing",
            sell_platform=STEAM,
            sell_price_type="listing",
            buy_price_eur=Decimal("11"),
            current_exit_net_eur=Decimal("12.18"),
            current_exit_gross_price_eur=Decimal("14"),
            current_return=Decimal("0.1073"),
            available_quantity=3,
            supervised_probability=Decimal("0.75"),
        ),
    )


def _decimal_or_none(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _portfolio_summary(
    env: MarketMARLEnvironment,
    as_of: date,
) -> dict[str, float | int]:
    metrics = env.simulator.metrics(as_of=as_of)
    return {
        "equity_eur": float(metrics.equity_eur),
        "realized_profit_eur": float(metrics.realized_profit_eur),
        "open_positions": metrics.open_positions,
        "closed_positions": metrics.closed_positions,
        "capital_blocked_eur": float(metrics.capital_blocked_eur),
        "drawdown_ratio": float(metrics.drawdown_ratio),
    }


if __name__ == "__main__":
    main()
