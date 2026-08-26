"""Render reproducible figures for the current MARL validation matrix."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render the trading v2 and MARL validation figures used in the TFM."
    )
    parser.add_argument(
        "--dataset-metadata",
        type=Path,
        default=Path("data/datasets/trading_profit_v2/metadata.json"),
    )
    parser.add_argument(
        "--matrix-report",
        type=Path,
        default=Path("model-runs/marl_ctde/v2_roi10_validation_20260825/matrix_report.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("TFM/figures/experimentacion"),
    )
    args = parser.parse_args()

    metadata = json.loads(args.dataset_metadata.read_text(encoding="utf-8"))
    matrix = json.loads(args.matrix_report.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _render_dataset_v2(metadata, args.output_dir / "07_dataset_trading_v2.png")
    _render_validation_matrix(matrix, args.output_dir / "08_marl_validacion.png")


def _render_dataset_v2(metadata: dict[str, object], output: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    labels = {"train": "Entrenamiento", "validation": "Validación", "test": "Prueba"}
    colors = {"train": "#4bbfad", "validation": "#e6b45f", "test": "#6f9fd1"}
    splits = metadata["splits"]  # type: ignore[index]
    rows = [int(splits[split]["rows"]) for split in ("train", "validation", "test")]
    rates = [float(splits[split]["target_rate"]) for split in ("train", "validation", "test")]
    items = [int(splits[split]["items"]) for split in ("train", "validation", "test")]

    figure, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), gridspec_kw={"width_ratios": [1.05, 1]})
    figure.patch.set_facecolor("#fbfaf5")
    size_axis, rate_axis = axes
    positions = list(range(3))
    bars = size_axis.bar(
        positions,
        rows,
        color=[colors[split] for split in ("train", "validation", "test")],
        width=0.64,
    )
    size_axis.set_xticks(positions, [labels[split] for split in ("train", "validation", "test")])
    size_axis.set_ylabel("Ejemplos")
    size_axis.set_title("Tamaño de las particiones", loc="left", fontsize=11, fontweight="bold")
    for bar, row, item_count in zip(bars, rows, items, strict=True):
        size_axis.text(
            bar.get_x() + bar.get_width() / 2,
            row + max(rows) * 0.025,
            f"{row:,}\n{item_count} artículos".replace(",", "."),
            ha="center",
            va="bottom",
            fontsize=8.1,
        )

    rate_bars = rate_axis.bar(
        positions,
        [rate * 100 for rate in rates],
        color=[colors[split] for split in ("train", "validation", "test")],
        width=0.64,
    )
    rate_axis.set_xticks(positions, [labels[split] for split in ("train", "validation", "test")])
    rate_axis.set_ylim(0, 100)
    rate_axis.set_ylabel("Operaciones rentables (%)")
    rate_axis.set_title("Distribución de la etiqueta", loc="left", fontsize=11, fontweight="bold")
    for bar, rate in zip(rate_bars, rates, strict=True):
        rate_axis.text(
            bar.get_x() + bar.get_width() / 2,
            rate * 100 + 2.5,
            f"{rate * 100:.1f}%".replace(".", ","),
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )
    for axis in axes:
        axis.grid(axis="y", color="#d9d5c8", linewidth=0.7)
        axis.set_axisbelow(True)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _render_validation_matrix(matrix: dict[str, object], output: Path) -> None:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    labels = {
        "base": "Base",
        "shared_050": "Compartida 50 %",
        "shared_090": "Compartida 90 %",
        "target_035": "Objetivo 35 %",
        "target_065": "Objetivo 65 %",
        "lr_00010": "Tasa 0,0001",
        "without_supervised": "Sin señal\nsupervisada",
    }
    order = [
        "base",
        "shared_050",
        "shared_090",
        "target_035",
        "target_065",
        "lr_00010",
        "without_supervised",
    ]
    grouped: dict[str, list[float]] = defaultdict(list)
    for run in matrix["runs"]:  # type: ignore[index]
        family = str(run["name"]).rsplit("_s", maxsplit=1)[0]
        grouped[family].append(float(run["best_validation_equity_return"]) * 100)

    means = [sum(grouped[family]) / len(grouped[family]) for family in order]
    colors = ["#6f9fd1", "#e6b45f", "#e6b45f", "#c78652", "#4bbfad", "#8c8372", "#bd6c85"]
    figure, axis = plt.subplots(figsize=(10.6, 4.4))
    figure.patch.set_facecolor("#fbfaf5")
    positions = list(range(len(order)))
    bars = axis.bar(positions, means, color=colors, width=0.68, zorder=2)
    offsets = (-0.14, 0.0, 0.14)
    for position, family in enumerate(order):
        values = sorted(grouped[family])
        for offset, value in zip(offsets, values, strict=True):
            axis.scatter(position + offset, value, color="#233746", edgecolor="#fbfaf5", linewidth=0.7, s=34, zorder=3)
    for bar, mean in zip(bars, means, strict=True):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            mean + 0.11,
            f"{mean:.2f}%".replace(".", ","),
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )
    axis.set_xticks(positions, [labels[family] for family in order], fontsize=8.5)
    axis.set_ylabel("Retorno del valor de cartera en validación (%)")
    axis.set_ylim(9.5, 13.35)
    axis.set_title("Matriz MARL: media de tres semillas", loc="left", fontsize=11.5, fontweight="bold")
    axis.text(
        0.0,
        -0.24,
        "Las barras muestran la media y los puntos, cada semilla. La prueba independiente no se utilizó.",
        transform=axis.transAxes,
        fontsize=8.4,
        color="#5d615e",
    )
    axis.grid(axis="y", color="#d9d5c8", linewidth=0.7, zorder=0)
    axis.set_axisbelow(True)
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)
    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
