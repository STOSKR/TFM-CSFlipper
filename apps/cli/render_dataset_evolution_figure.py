"""Render the dataset-evolution figure documented in the TFM experiments."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]

    output = Path("TFM/figures/experimentacion/06_cortes_datasets.png")
    output.parent.mkdir(parents=True, exist_ok=True)

    cuts = ("Marzo", "Mayo", "Reciente")
    counts = {
        "Entrenamiento": (171, 361, 551),
        "Validación": (76, 76, 76),
        "Prueba": (95, 95, 84),
    }
    rates = {
        "Entrenamiento": (92.98, 95.57, 95.64),
        "Validación": (98.68, 100.0, 100.0),
        "Prueba": (89.47, 100.0, 98.81),
    }
    colors = ("#4bbfad", "#e6b45f", "#6f9fd1")
    figure, axes = plt.subplots(1, 2, figsize=(10.7, 3.8), sharex=True)
    figure.patch.set_facecolor("#fbfaf5")
    positions = np.arange(len(cuts))
    width = 0.23

    for index, (split, values) in enumerate(counts.items()):
        offset = (index - 1) * width
        axes[0].bar(positions + offset, values, width, label=split, color=colors[index])
        for x, value in zip(positions + offset, values, strict=True):
            axes[0].text(x, value + 12, str(value), ha="center", va="bottom", fontsize=8)

    axes[0].set_title("Filas por corte", loc="left", fontsize=11, fontweight="bold")
    axes[0].set_ylabel("Filas")
    axes[0].set_ylim(0, 650)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")

    for index, (split, values) in enumerate(rates.items()):
        offset = (index - 1) * width
        axes[1].bar(positions + offset, values, width, color=colors[index])

    axes[1].set_title("Tasa positiva", loc="left", fontsize=11, fontweight="bold")
    axes[1].set_ylabel("Porcentaje")
    axes[1].set_ylim(0, 108)

    for axis in axes:
        axis.set_xticks(positions, cuts)
        axis.grid(axis="y", color="#d9d5c8", linewidth=0.7)
        axis.set_axisbelow(True)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)

    figure.tight_layout()
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
