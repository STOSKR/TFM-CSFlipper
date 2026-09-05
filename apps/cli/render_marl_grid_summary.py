"""Render a validation-return comparison for the complete MARL grid."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")

SIZES = ("small", "medium", "large")
PROFILES = ("restricted", "standard", "concentrated", "diversified")
SIZE_LABELS = {"small": "Pequeño", "medium": "Mediano", "large": "Grande"}
PROFILE_LABELS = {
    "restricted": "Restrictivo",
    "standard": "Estándar",
    "concentrated": "Concentrado",
    "diversified": "Diversificado",
}
COLORS = ("#7f9aa3", "#6f9fd1", "#d58b58", "#4bbfad")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    matrix = json.loads(args.matrix_report.read_text(encoding="utf-8"))
    values: dict[str, list[float]] = defaultdict(list)
    for run in matrix["runs"]:
        values[str(run["scenario"]["name"])].append(
            float(run["best_validation_equity_return"]) * 100
        )

    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(13.2, 4.2), sharey=True)
    figure.patch.set_facecolor("#fbfaf5")
    for axis, size in zip(axes, SIZES, strict=True):
        scenarios = [f"{size}_{profile}" for profile in PROFILES]
        means = [np.mean(values[scenario]) for scenario in scenarios]
        positions = np.arange(len(PROFILES))
        axis.bar(positions, means, color=COLORS, width=0.64)
        for position, scenario in zip(positions, scenarios, strict=True):
            axis.scatter(
                np.full(len(values[scenario]), position),
                values[scenario],
                color="#263946",
                zorder=3,
                s=19,
            )
        axis.set_title(SIZE_LABELS[size], loc="left", fontweight="bold")
        axis.set_xticks(positions, [PROFILE_LABELS[p] for p in PROFILES], rotation=26, ha="right")
        axis.grid(axis="y", color="#d9d5c8", linewidth=0.7)
        axis.set_axisbelow(True)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
    axes[0].set_ylabel("Retorno de cartera en validación (%)")
    figure.suptitle("Retorno de validación por tamaño y perfil de cartera", x=0.06, ha="left")
    figure.text(
        0.06,
        0.01,
        "Barras: media de tres semillas. Puntos: resultados individuales.",
        fontsize=8.5,
    )
    figure.tight_layout(rect=(0, 0.05, 1, 0.93))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=220, bbox_inches="tight")


if __name__ == "__main__":
    main()
