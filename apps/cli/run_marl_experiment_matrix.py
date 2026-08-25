"""Ejecuta de forma secuencial una matriz reproducible de cribado MARL."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.marl import (
    AllocationTargetConfig,
    CooperativeRewardConfig,
    CTDETrainingConfig,
    HybridRewardConfig,
    train_ctde,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a sequential MARL validation matrix without using the test split."
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed reports and run only the pending configurations.",
    )
    args = parser.parse_args()
    report = run_matrix(plan_path=args.plan, output_root=args.output_root, resume=args.resume)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def run_matrix(*, plan_path: Path, output_root: Path, resume: bool) -> dict[str, Any]:
    """Ejecuta cada configuración en serie y escribe el resumen tras cada paso."""

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    base = dict(plan["base"])
    definitions = list(plan["experiments"])
    output_root.mkdir(parents=True, exist_ok=True)
    matrix_path = output_root / "matrix_report.json"
    completed = _completed_runs(matrix_path) if resume else {}
    runs: list[dict[str, Any]] = []

    for definition in definitions:
        name = str(definition["name"])
        merged = {**base, **definition}
        merged.pop("name", None)
        if name in completed:
            runs.append(completed[name])
            continue
        output_dir = output_root / name
        training = _training_config(merged, output_dir=output_dir)
        report = train_ctde(training)
        history = report["history"]
        best = max(history, key=lambda row: float(row["validation_equity_return"]))
        runs.append(
            {
                "name": name,
                "status": "completed",
                "output_dir": str(output_dir),
                "seed": training.seed,
                "parameters": _parameter_summary(training),
                "best_iteration": best["iteration"],
                "best_validation_equity_return": report["best_validation_equity_return"],
                "test_used": report["test"] is not None,
            }
        )
        _write_matrix_report(matrix_path, plan_path=plan_path, runs=runs)

    return _write_matrix_report(matrix_path, plan_path=plan_path, runs=runs)


def _training_config(values: dict[str, Any], *, output_dir: Path) -> CTDETrainingConfig:
    return CTDETrainingConfig(
        dataset_dir=Path(values["dataset_dir"]),
        output_dir=output_dir,
        initial_cash_eur=Decimal(str(values.get("cash", "1000"))),
        iterations=int(values.get("iterations", 4)),
        episodes_per_iteration=int(values.get("episodes_per_iteration", 3)),
        episode_days=int(values.get("episode_days", 14)),
        max_steps_per_episode=int(values.get("max_steps_per_episode", 2000)),
        learning_rate=float(values.get("learning_rate", 0.0003)),
        gamma=float(values.get("gamma", 0.99)),
        ppo_clip=float(values.get("ppo_clip", 0.20)),
        update_epochs=int(values.get("update_epochs", 4)),
        entropy_weight=float(values.get("entropy_weight", 0.01)),
        value_weight=float(values.get("value_weight", 0.50)),
        seed=int(values.get("seed", 7)),
        include_supervised_probability=bool(values.get("include_supervised_probability", True)),
        evaluate_test=False,
        reward_config=CooperativeRewardConfig(
            roi_weight=Decimal(str(values.get("roi_weight", "0.60"))),
            extra_hold_day_penalty=Decimal(
                str(values.get("extra_hold_day_penalty", "0.01"))
            ),
            constraint_violation_penalty=Decimal(
                str(values.get("constraint_violation_penalty", "0.80"))
            ),
        ),
        hybrid_reward_config=HybridRewardConfig(
            shared_weight=Decimal(str(values.get("shared_weight", "0.90")))
        ),
        allocation_config=AllocationTargetConfig(
            target_fraction=Decimal(str(values.get("target_investment_fraction", "0.50"))),
            tolerance=Decimal(str(values.get("target_investment_tolerance", "0.05"))),
        ),
    )


def _parameter_summary(config: CTDETrainingConfig) -> dict[str, str | int]:
    return {
        "shared_weight": str(config.hybrid_reward_config.shared_weight),
        "roi_weight": str(config.reward_config.roi_weight),
        "extra_hold_day_penalty": str(config.reward_config.extra_hold_day_penalty),
        "constraint_violation_penalty": str(config.reward_config.constraint_violation_penalty),
        "target_investment_fraction": str(config.allocation_config.target_fraction),
        "target_investment_tolerance": str(config.allocation_config.tolerance),
        "iterations": config.iterations,
        "episodes_per_iteration": config.episodes_per_iteration,
        "learning_rate": config.learning_rate,
        "gamma": config.gamma,
        "ppo_clip": config.ppo_clip,
        "update_epochs": config.update_epochs,
        "entropy_weight": config.entropy_weight,
        "value_weight": config.value_weight,
    }


def _completed_runs(matrix_path: Path) -> dict[str, dict[str, Any]]:
    if not matrix_path.exists():
        return {}
    report = json.loads(matrix_path.read_text(encoding="utf-8"))
    return {
        str(run["name"]): dict(run)
        for run in report.get("runs", [])
        if run.get("status") == "completed"
    }


def _write_matrix_report(
    matrix_path: Path,
    *,
    plan_path: Path,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    report = {
        "schema_version": "csflipper_marl_matrix.v1",
        "created_at": datetime.now(tz=UTC).isoformat(),
        "plan": str(plan_path),
        "selection_split": "validation",
        "test_split_used": False,
        "runs": runs,
    }
    matrix_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
