"""Entrena políticas MARL CTDE sobre los cortes temporales del histórico."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from packages.marl import (
    AllocationTargetConfig,
    CooperativeRewardConfig,
    CTDETrainingConfig,
    HybridRewardConfig,
    train_ctde,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train decentralized MARL actors with a centralized evaluator."
    )
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/datasets/trading_profit_v1"))
    parser.add_argument("--output-dir", type=Path, default=Path("model-runs/marl_ctde"))
    parser.add_argument("--cash", type=str, default="1000")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--episodes-per-iteration", type=int, default=8)
    parser.add_argument("--episode-days", type=int, default=14)
    parser.add_argument("--max-steps-per-episode", type=int, default=2000)
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--ppo-clip", type=float, default=0.20)
    parser.add_argument("--update-epochs", type=int, default=4)
    parser.add_argument("--entropy-weight", type=float, default=0.01)
    parser.add_argument("--value-weight", type=float, default=0.50)
    parser.add_argument("--shared-weight", type=str, default="0.70")
    parser.add_argument("--roi-weight", type=str, default="0.60")
    parser.add_argument("--extra-hold-day-penalty", type=str, default="0.01")
    parser.add_argument("--constraint-violation-penalty", type=str, default="0.80")
    parser.add_argument("--target-investment-fraction", type=str, default="0.50")
    parser.add_argument("--target-investment-tolerance", type=str, default="0.05")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--skip-test",
        action="store_true",
        help="Use only training and validation. Do not inspect the independent test split.",
    )
    parser.add_argument(
        "--no-supervised-probability",
        action="store_true",
        help="Run the ablation without the supervised prediction feature.",
    )
    args = parser.parse_args()
    report = train_ctde(
        CTDETrainingConfig(
            dataset_dir=args.dataset_dir,
            output_dir=args.output_dir,
            initial_cash_eur=Decimal(args.cash),
            iterations=args.iterations,
            episodes_per_iteration=args.episodes_per_iteration,
            episode_days=args.episode_days,
            max_steps_per_episode=args.max_steps_per_episode,
            learning_rate=args.learning_rate,
            gamma=args.gamma,
            ppo_clip=args.ppo_clip,
            update_epochs=args.update_epochs,
            entropy_weight=args.entropy_weight,
            value_weight=args.value_weight,
            seed=args.seed,
            include_supervised_probability=not args.no_supervised_probability,
            evaluate_test=not args.skip_test,
            reward_config=CooperativeRewardConfig(
                roi_weight=Decimal(args.roi_weight),
                extra_hold_day_penalty=Decimal(args.extra_hold_day_penalty),
                constraint_violation_penalty=Decimal(args.constraint_violation_penalty),
            ),
            hybrid_reward_config=HybridRewardConfig(shared_weight=Decimal(args.shared_weight)),
            allocation_config=AllocationTargetConfig(
                target_fraction=Decimal(args.target_investment_fraction),
                tolerance=Decimal(args.target_investment_tolerance),
            ),
        )
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
