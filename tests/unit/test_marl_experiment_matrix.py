import json
from decimal import Decimal
from pathlib import Path

from apps.cli.run_marl_experiment_matrix import _completed_runs, _training_config


def test_training_config_for_matrix_never_uses_the_test_split(tmp_path: Path) -> None:
    config = _training_config(
        {
            "dataset_dir": "data/datasets/trading_profit_v1",
            "shared_weight": "0.90",
            "seed": 19,
        },
        output_dir=tmp_path / "run",
    )

    assert config.evaluate_test is False
    assert config.hybrid_reward_config.shared_weight == Decimal("0.90")
    assert config.seed == 19


def test_completed_runs_returns_only_completed_entries(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix_report.json"
    matrix_path.write_text(
        json.dumps(
            {
                "runs": [
                    {"name": "done", "status": "completed"},
                    {"name": "pending", "status": "pending"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert _completed_runs(matrix_path) == {"done": {"name": "done", "status": "completed"}}
