"""Entrena el baseline centralizado y evalúa una sola vez la prueba aislada."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from packages.marl.ctde_training import CTDETrainingConfig, load_ctde_policy
from packages.marl.final_evaluation import (
    FinalEvaluationConfig,
    evaluate_final,
    write_final_evaluation,
)
from packages.marl.market_env import AllocationTargetConfig
from packages.marl.rewards import CooperativeRewardConfig, HybridRewardConfig
from packages.marl.single_agent_training import load_single_agent_policy, train_single_agent
from packages.simulation import PortfolioRiskConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the central single-agent baseline, then evaluate the held-out test once."
    )
    parser.add_argument("--marl-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    report = run_final_evaluation(
        marl_root=args.marl_root,
        output_root=args.output_root,
        resume=args.resume,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


def run_final_evaluation(*, marl_root: Path, output_root: Path, resume: bool) -> dict[str, Any]:
    """Ejecuta la única lectura autorizada de prueba para los finalistas fijados."""

    final_path = output_root / "final_test_report.json"
    if final_path.exists():
        raise FileExistsError(
            f"{final_path} already exists; the held-out test must not be re-evaluated"
        )
    metadata = _finalist_metadata(marl_root)
    training_config = _training_config(metadata, output_root=output_root / "single_agent_s07")
    single_reports: dict[str, dict[str, Any]] = {}
    marl_policies = {}
    single_policies = {}
    for seed in (7, 19, 31):
        marl_dir = marl_root / f"medium_diversified_s{seed:02d}"
        marl_policies[str(seed)] = load_ctde_policy(marl_dir / "best_checkpoint.pt")
        output_dir = output_root / f"single_agent_s{seed:02d}"
        report_path = output_dir / "training_report.json"
        if resume and report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
        else:
            config = _training_config(metadata, output_root=output_dir, seed=seed)
            report = train_single_agent(config)
        single_reports[str(seed)] = report
        single_policies[str(seed)] = load_single_agent_policy(output_dir / "best_checkpoint.pt")

    evaluation_config = FinalEvaluationConfig(
        dataset_dir=training_config.dataset_dir,
        asset_ids=training_config.asset_ids or (),
        initial_cash_eur=training_config.initial_cash_eur,
        risk_config=training_config.risk_config,
        reward_config=training_config.reward_config,
        hybrid_reward_config=training_config.hybrid_reward_config,
        allocation_config=training_config.allocation_config,
        episode_days=training_config.episode_days,
        max_steps_per_episode=training_config.max_steps_per_episode,
        episodes=8,
        test_seed=training_config.test_seed,
    )
    report = evaluate_final(
        evaluation_config,
        marl_policies=marl_policies,
        single_agent_policies=single_policies,
    )
    report["selection"] = {
        "scenario": "medium_diversified",
        "selection_split": "validation",
        "marl_root": str(marl_root),
        "single_agent_training": {
            seed: {
                "best_validation_equity_return": value["best_validation_equity_return"],
                "executed_iterations": value["executed_iterations"],
            }
            for seed, value in single_reports.items()
        },
    }
    write_final_evaluation(final_path, report)
    return report


def _finalist_metadata(marl_root: Path) -> dict[str, Any]:
    path = marl_root / "medium_diversified_s07" / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"missing selected finalist metadata: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload["training"])


def _training_config(
    metadata: dict[str, Any],
    *,
    output_root: Path,
    seed: int | None = None,
) -> CTDETrainingConfig:
    risk = metadata["risk_config"]
    reward = metadata["reward_config"]
    allocation = metadata["allocation_config"]
    return CTDETrainingConfig(
        dataset_dir=Path(metadata["dataset_dir"]),
        output_dir=output_root,
        initial_cash_eur=Decimal(metadata["initial_cash_eur"]),
        iterations=int(metadata["iterations"]),
        episodes_per_iteration=int(metadata["episodes_per_iteration"]),
        episode_days=int(metadata["episode_days"]),
        max_steps_per_episode=int(metadata["max_steps_per_episode"]),
        learning_rate=float(metadata["learning_rate"]),
        gamma=float(metadata["gamma"]),
        ppo_clip=float(metadata["ppo_clip"]),
        update_epochs=int(metadata["update_epochs"]),
        entropy_weight=float(metadata["entropy_weight"]),
        value_weight=float(metadata["value_weight"]),
        early_stopping_patience=int(metadata["early_stopping_patience"]),
        seed=int(metadata["seed"] if seed is None else seed),
        validation_seed=int(metadata["validation_seed"]),
        test_seed=int(metadata["test_seed"]),
        include_supervised_probability=bool(metadata["include_supervised_probability"]),
        evaluate_test=False,
        scenario_name="medium_diversified_single_agent",
        asset_ids=tuple(metadata["asset_ids"]),
        risk_config=PortfolioRiskConfig(
            max_position_fraction=Decimal(risk["max_position_fraction"]),
            max_item_fraction=Decimal(risk["max_item_fraction"]),
            max_platform_fraction=Decimal(risk["max_platform_fraction"]),
            min_cash_fraction=Decimal(risk["min_cash_fraction"]),
            warning_usage_ratio=Decimal(risk["warning_usage_ratio"]),
            max_open_positions=int(risk["max_open_positions"]),
        ),
        reward_config=CooperativeRewardConfig(
            roi_weight=Decimal(reward["roi_weight"]),
            extra_hold_day_penalty=Decimal(reward["extra_hold_day_penalty"]),
            constraint_violation_penalty=Decimal(reward["constraint_violation_penalty"]),
        ),
        hybrid_reward_config=HybridRewardConfig(
            shared_weight=Decimal(metadata["hybrid_reward_config"]["shared_weight"])
        ),
        allocation_config=AllocationTargetConfig(
            target_fraction=Decimal(allocation["target_fraction"]),
            tolerance=Decimal(allocation["tolerance"]),
        ),
    )


if __name__ == "__main__":
    main()
