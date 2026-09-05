"""Render learning diagnostics from a reproducible MARL problem matrix."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")

SCENARIOS = ("small_standard", "medium_standard", "large_standard")
SCENARIO_LABELS = {
    "small_standard": "Pequeño estándar",
    "medium_standard": "Medio estándar",
    "large_standard": "Grande estándar",
}
AGENTS = ("scout", "trader", "portfolio")
AGENT_LABELS = {"scout": "Scout", "trader": "Trader", "portfolio": "Portfolio"}
AGENT_COLORS = {"scout": "#4bbfad", "trader": "#6f9fd1", "portfolio": "#e6b45f"}
ACTION_LABELS = {
    "ignore": "Ignorar",
    "mark_opportunity": "Marcar",
    "hold": "Mantener",
    "buy_one": "Comprar",
    "sell_matching": "Vender",
    "reject": "Rechazar",
    "approve": "Aprobar",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render MARL learning diagnostic figures.")
    parser.add_argument(
        "--matrix-report",
        type=Path,
        default=Path("model-runs/marl_ctde/problem_matrix_20260904/matrix_report.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("TFM/figures/experimentacion"),
    )
    args = parser.parse_args()
    runs = _load_runs(args.matrix_report)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _render_rewards(runs, args.output_dir / "09_marl_recompensas.png")
    _render_stability(runs, args.output_dir / "10_marl_estabilidad_ppo.png")
    _render_policies(runs, args.output_dir / "11_marl_politicas.png")


def _load_runs(matrix_path: Path) -> dict[str, list[list[dict[str, Any]]]]:
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
    for run in matrix["runs"]:
        report_path = Path(run["output_dir"]) / "training_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        grouped[str(report["scenario"]["name"])].append(list(report["history"]))
    return grouped


def _series(
    histories: list[list[dict[str, Any]]],
    key: str,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    longest = max(len(history) for history in histories)
    values = np.full((len(histories), longest), np.nan)
    for row, history in enumerate(histories):
        for column, item in enumerate(history):
            values[row, column] = float(item[key])
    return np.arange(1, longest + 1), np.nanmean(values, axis=0), np.nanstd(values, axis=0)


def _render_rewards(runs: dict[str, list[list[dict[str, Any]]]], output: Path) -> None:
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, len(SCENARIOS), figsize=(14.2, 4.0), sharey=True)
    figure.patch.set_facecolor("#fbfaf5")
    for axis, scenario in zip(axes, SCENARIOS, strict=True):
        histories = runs[scenario]
        _line(axis, histories, "mean_common_reward", "Común", "#263946")
        for agent in AGENTS:
            _line(
                axis,
                histories,
                f"mean_reward_{agent}",
                AGENT_LABELS[agent],
                AGENT_COLORS[agent],
            )
        axis.set_title(SCENARIO_LABELS[scenario], loc="left", fontsize=10.5, fontweight="bold")
        axis.set_xlabel("Iteración")
        _style(axis)
    axes[0].set_ylabel("Recompensa media por paso")
    axes[0].legend(fontsize=7.8, frameon=False)
    figure.suptitle(
        "Evolución de las recompensas durante el entrenamiento", x=0.06, ha="left", fontsize=12
    )
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _render_stability(runs: dict[str, list[list[dict[str, Any]]]], output: Path) -> None:
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, len(SCENARIOS), figsize=(14.2, 6.2), sharex="col")
    figure.patch.set_facecolor("#fbfaf5")
    for column, scenario in enumerate(SCENARIOS):
        histories = runs[scenario]
        upper = axes[0, column]
        lower = axes[1, column]
        _line(upper, histories, "value_loss", "Pérdida de valor", "#bd6c85")
        for agent in AGENTS:
            _line(lower, histories, f"entropy_{agent}", AGENT_LABELS[agent], AGENT_COLORS[agent])
        upper.set_title(SCENARIO_LABELS[scenario], loc="left", fontsize=10.5, fontweight="bold")
        lower.set_xlabel("Iteración")
        _style(upper)
        _style(lower)
    axes[0, 0].set_ylabel("Pérdida de valor")
    axes[1, 0].set_ylabel("Entropía")
    axes[1, 0].legend(fontsize=7.8, frameon=False)
    figure.suptitle(
        "Estabilidad del crítico y exploración de las políticas PPO", x=0.06, ha="left", fontsize=12
    )
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _render_policies(runs: dict[str, list[list[dict[str, Any]]]], output: Path) -> None:
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(len(AGENTS), len(SCENARIOS), figsize=(14.2, 7.2), sharey="row")
    figure.patch.set_facecolor("#fbfaf5")
    for column, scenario in enumerate(SCENARIOS):
        histories = runs[scenario]
        for row, agent in enumerate(AGENTS):
            axis = axes[row, column]
            actions = _actions(agent)
            initial = _policy_values(histories, agent, actions, index=0)
            final = _policy_values(histories, agent, actions, index=-1)
            positions = np.arange(len(actions))
            axis.bar(positions - 0.18, initial, width=0.34, color="#b5bcc0", label="Inicio")
            axis.bar(positions + 0.18, final, width=0.34, color=AGENT_COLORS[agent], label="Final")
            axis.set_xticks(
                positions,
                [ACTION_LABELS[action] for action in actions],
                rotation=20,
                ha="right",
                fontsize=7.5,
            )
            axis.set_ylim(0, 1)
            if row == 0:
                axis.set_title(
                    SCENARIO_LABELS[scenario], loc="left", fontsize=10.5, fontweight="bold"
                )
            if column == 0:
                axis.set_ylabel(f"{AGENT_LABELS[agent]}\nProbabilidad")
            _style(axis)
    axes[0, 0].legend(fontsize=7.8, frameon=False)
    figure.suptitle("Cambio de probabilidad media de las acciones", x=0.06, ha="left", fontsize=12)
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _line(
    axis: Any,
    histories: list[list[dict[str, Any]]],
    key: str,
    label: str,
    color: str,
) -> None:
    x, mean, std = _series(histories, key)
    axis.plot(x, mean, label=label, color=color, linewidth=1.7)
    axis.fill_between(x, mean - std, mean + std, color=color, alpha=0.12, linewidth=0)


def _policy_values(
    histories: list[list[dict[str, Any]]],
    agent: str,
    actions: tuple[str, ...],
    *,
    index: int,
) -> list[float]:
    values = []
    for action in actions:
        samples = [
            float(history[index][f"mean_action_probability_{agent}_{action}"])
            for history in histories
        ]
        values.append(float(np.mean(samples)))
    return values


def _actions(agent: str) -> tuple[str, ...]:
    if agent == "scout":
        return ("ignore", "mark_opportunity")
    if agent == "trader":
        return ("hold", "buy_one", "sell_matching")
    return ("reject", "approve")


def _style(axis: Any) -> None:
    axis.grid(axis="y", color="#d9d5c8", linewidth=0.7)
    axis.set_axisbelow(True)
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)


if __name__ == "__main__":
    main()
