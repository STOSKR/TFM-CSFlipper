"""Render reproducible diagnostics for the temporal and MARL experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

from packages.marl import MarketMARLEnvironment, load_market_episode_steps


def main() -> None:
    parser = argparse.ArgumentParser(description="Render TFM experiment diagnostics.")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("data/experiments/walkforward_20260810/march"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/experiments/walkforward_20260810/march_logistic/training_report.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("TFM/figures/experimentacion"),
    )
    args = parser.parse_args()
    metadata = json.loads((args.dataset_dir / "metadata.json").read_text(encoding="utf-8"))
    frames = {
        split: pd.read_parquet(args.dataset_dir / f"{split}.parquet")
        for split in ("train", "validation", "test")
    }
    report = json.loads(args.report.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _render_temporal_coverage(metadata, frames, args.output_dir / "03_cobertura_temporal.png")
    _render_threshold_profile(report, args.output_dir / "04_umbral_marzo.png")
    _render_marl_baseline_trace(args.dataset_dir, args.output_dir / "05_traza_marl_marzo.png")


def _render_temporal_coverage(
    metadata: dict[str, object], frames: dict[str, pd.DataFrame], output: Path
) -> None:
    import matplotlib.dates as mdates  # type: ignore[import-not-found]
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    labels = {"train": "Entrenamiento", "validation": "Validación", "test": "Prueba"}
    colors = {"train": "#4bbfad", "validation": "#e6b45f", "test": "#6f9fd1"}
    figure, axes = plt.subplots(1, 2, figsize=(10.7, 3.8), gridspec_kw={"width_ratios": [1.25, 1]})
    figure.patch.set_facecolor("#fbfaf5")
    timeline, balance = axes
    for position, split in enumerate(("train", "validation", "test")):
        frame = frames[split]
        start = pd.Timestamp(frame["observed_day"].min())
        end = pd.Timestamp(frame["observed_day"].max())
        timeline.barh(
            position, (end - start).days + 1, left=start, height=0.48, color=colors[split]
        )
        timeline.text(
            end + pd.Timedelta(days=2),
            position,
            f"{len(frame)} filas · {frame['representation_name'].nunique()} artículos",
            va="center",
            fontsize=8.2,
        )
    timeline.set_yticks(range(3), [labels[split] for split in ("train", "validation", "test")])
    timeline.invert_yaxis()
    timeline.xaxis.set_major_locator(mdates.MonthLocator())
    timeline.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    timeline.set_title(
        "Separación temporal con purga de 8 días", loc="left", fontsize=11, fontweight="bold"
    )
    timeline.grid(axis="x", color="#d9d5c8", linewidth=0.7)
    timeline.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        timeline.spines[spine].set_visible(False)
    target_column = str(metadata["target_column"])
    positive = [
        int(frames[split][target_column].sum()) for split in ("train", "validation", "test")
    ]
    total = [len(frames[split]) for split in ("train", "validation", "test")]
    negative = [all_rows - positives for all_rows, positives in zip(total, positive, strict=True)]
    x = range(3)
    balance.bar(x, positive, color="#4bbfad", label="Rentable")
    balance.bar(x, negative, bottom=positive, color="#bf879c", label="No rentable")
    for index, (positives, all_rows) in enumerate(zip(positive, total, strict=True)):
        balance.text(
            index,
            all_rows + 3,
            f"{positives / all_rows:.1%}",
            ha="center",
            fontsize=8.5,
            fontweight="bold",
        )
    balance.set_xticks(list(x), [labels[split] for split in ("train", "validation", "test")])
    balance.set_ylim(0, max(total) * 1.18)
    balance.set_title("Distribución de la etiqueta", loc="left", fontsize=11, fontweight="bold")
    balance.set_ylabel("Filas")
    balance.legend(loc="upper right", frameon=False, fontsize=8)
    balance.grid(axis="y", color="#d9d5c8", linewidth=0.7)
    balance.set_axisbelow(True)
    for spine in ("top", "right"):
        balance.spines[spine].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _render_threshold_profile(report: dict[str, object], output: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    test = report["calibration"]["test"]  # type: ignore[index]
    rows = test["thresholds"]  # type: ignore[index]
    thresholds = [float(row["threshold"]) for row in rows]
    precision = [float(row["precision"]) for row in rows]
    recall = [float(row["recall"]) for row in rows]
    signals = [int(row["predicted_positive"]) for row in rows]
    figure, axes = plt.subplots(
        1, 2, figsize=(10.3, 3.8), gridspec_kw={"width_ratios": [1.15, 0.85]}
    )
    figure.patch.set_facecolor("#fbfaf5")
    quality, count = axes
    quality.plot(thresholds, precision, marker="o", color="#4bbfad", label="Precisión")
    quality.plot(thresholds, recall, marker="o", color="#6f9fd1", label="Recall")
    quality.axhline(
        float(test["target_rate"]),
        color="#8c8372",
        linestyle="--",
        linewidth=1,
        label="Tasa positiva",
    )
    quality.set_ylim(0.5, 1.03)
    quality.set_xlabel("Umbral de decisión")
    quality.set_ylabel("Proporción")
    quality.set_title("Métricas en la prueba de marzo", loc="left", fontsize=11, fontweight="bold")
    quality.legend(frameon=False, fontsize=8, loc="lower left")
    count.plot(thresholds, signals, marker="o", color="#c78652")
    count.set_xlabel("Umbral de decisión")
    count.set_ylabel("Señales seleccionadas")
    count.set_title("Cobertura de la señal", loc="left", fontsize=11, fontweight="bold")
    for axis in axes:
        axis.grid(color="#d9d5c8", linewidth=0.7)
        axis.set_axisbelow(True)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _render_marl_baseline_trace(dataset_dir: Path, output: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    steps = load_market_episode_steps(dataset_dir, split="test")
    traces = {policy: _run_policy_trace(steps, policy) for policy in ("buy-positive", "hold")}
    figure, axes = plt.subplots(1, 2, figsize=(10.7, 3.8), sharex=True)
    figure.patch.set_facecolor("#fbfaf5")
    style = {"buy-positive": ("Margen positivo", "#4bbfad"), "hold": ("Mantener", "#6f9fd1")}
    for policy, trace in traces.items():
        label, color = style[policy]
        axes[0].plot(trace["step"], trace["cash"], color=color, label=label)
        axes[0].plot(
            trace["step"],
            trace["blocked"],
            color=color,
            linestyle="--",
            alpha=0.85,
            label=f"{label} bloqueado",
        )
        axes[1].step(trace["step"], trace["positions"], where="post", color=color, label=label)
    axes[0].set_title("Efectivo y capital bloqueado", loc="left", fontsize=11, fontweight="bold")
    axes[0].set_ylabel("EUR")
    axes[0].legend(frameon=False, fontsize=7.6, ncol=2, loc="best")
    axes[1].set_title("Posiciones abiertas", loc="left", fontsize=11, fontweight="bold")
    axes[1].set_ylabel("Posiciones")
    for axis in axes:
        axis.set_xlabel("Paso del episodio")
        axis.grid(color="#d9d5c8", linewidth=0.7)
        axis.set_axisbelow(True)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _run_policy_trace(steps: tuple[object, ...], policy: str) -> dict[str, list[float | int]]:
    environment = MarketMARLEnvironment(steps, initial_cash_eur=1000)
    observations, _ = environment.reset()
    trace: dict[str, list[float | int]] = {
        "step": [0],
        "cash": [1000.0],
        "blocked": [0.0],
        "positions": [0],
    }
    step_number = 0
    while environment.agents:
        current_return = observations["scout"].get("current_return", 0.0)
        buy = int(policy == "buy-positive" and current_return > 0)
        observations, _rewards, _terminations, _truncations, infos = environment.step(
            {"scout": buy, "trader": buy, "portfolio": buy}
        )
        step_number += 1
        metrics = environment.simulator.metrics(
            as_of=steps[min(step_number - 1, len(steps) - 1)].observed_day
        )
        trace["step"].append(step_number)
        trace["cash"].append(float(metrics.cash_available_eur))
        trace["blocked"].append(float(metrics.capital_blocked_eur))
        trace["positions"].append(len(environment.simulator.positions))
    return trace


if __name__ == "__main__":
    main()
