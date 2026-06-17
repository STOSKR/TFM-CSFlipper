"""Run a short RLlib PPO smoke training for the MARL market environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.marl.rllib_training import RLLibTrainingConfig, train_rllib_smoke


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a short RLlib multi-agent PPO smoke run.")
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--cash", type=float, default=100.0)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
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
    args = parser.parse_args()
    result = train_rllib_smoke(
        RLLibTrainingConfig(
            dataset_dir=args.dataset_dir,
            split=args.split,
            limit=args.limit,
            initial_cash_eur=args.cash,
            iterations=args.iterations,
            seed=args.seed,
            include_supervised_probability=args.supervised_probability,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
