"""
Renders a chart_builder-shaped {labels, datasets, chart_type} dict to a
PNG image for embedding in PDF reports. Matplotlib's Agg backend is
headless (no display/GPU needed) — set once at import time, safe in a
server process.
"""

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIGURE_SIZE = (6, 3.5)
COLOR_PALETTE = ["#4f46e5", "#0ea5e9", "#16a34a", "#d97706", "#dc2626", "#7c3aed"]


def render_chart_png(title, chart_data):
    fig, ax = plt.subplots(figsize=FIGURE_SIZE, dpi=120)
    chart_type = chart_data.get("chart_type", "bar")
    labels = chart_data.get("labels", [])
    datasets = chart_data.get("datasets", [])

    try:
        if chart_type == "scatter":
            _render_scatter(ax, datasets)
        elif chart_type in ("pie", "doughnut"):
            _render_pie(ax, labels, datasets)
        elif chart_type == "line":
            _render_line(ax, labels, datasets)
        else:
            _render_bar(ax, labels, datasets)

        ax.set_title(title, fontsize=11, fontweight="bold")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        return buf.read()
    finally:
        plt.close(fig)


def _render_bar(ax, labels, datasets):
    n_series = max(len(datasets), 1)
    x = np.arange(len(labels))
    width = 0.8 / n_series

    for i, ds in enumerate(datasets):
        ax.bar(x + i * width, ds.get("data", []), width=width, label=ds.get("label"), color=COLOR_PALETTE[i % len(COLOR_PALETTE)])

    ax.set_xticks(x + width * (n_series - 1) / 2)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    if n_series > 1:
        ax.legend(fontsize=7)


def _render_line(ax, labels, datasets):
    for i, ds in enumerate(datasets):
        ax.plot(labels, ds.get("data", []), label=ds.get("label"), color=COLOR_PALETTE[i % len(COLOR_PALETTE)], marker="o", markersize=3)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    if len(datasets) > 1:
        ax.legend(fontsize=7)


def _render_pie(ax, labels, datasets):
    data = datasets[0].get("data", []) if datasets else []
    ax.pie(data, labels=labels, autopct="%1.0f%%", colors=COLOR_PALETTE, textprops={"fontsize": 7})
    ax.axis("equal")


def _render_scatter(ax, datasets):
    for i, ds in enumerate(datasets):
        points = ds.get("data", [])
        xs = [p.get("x") for p in points if isinstance(p, dict)]
        ys = [p.get("y") for p in points if isinstance(p, dict)]
        ax.scatter(xs, ys, label=ds.get("label"), color=COLOR_PALETTE[i % len(COLOR_PALETTE)], s=12, alpha=0.7)
    if len(datasets) > 1:
        ax.legend(fontsize=7)
