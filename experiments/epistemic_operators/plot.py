"""
Epistemic operators grouped bar chart.

Reads aggregated checkpoint CSVs and produces a paper-style grouped bar chart
comparing negated documents vs repeated negations for each epistemic operator
(fiction, unreliable, uncertainty, low probability).

Usage:
    uv run python experiments/epistemic_operators/plot.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Path to the directory containing the per-checkpoint aggregated CSVs.
# Override via `--results-dir` if your eval outputs live elsewhere.
RESULTS_DIR = Path("evals/results/Qwen3.5-35B-A3B/checkpoints")

OUTPUT_DIR = Path(__file__).parent

EVAL_TYPES = ["mcq", "belief_probe", "pink_elephant", "robustness"]

# Epistemic operators: display name -> (non-dense model stem, dense model stem)
OPERATORS = {
    "Fiction": ("fiction", "fiction_dense"),
    "Unreliable\nsource": ("unreliable", "unreliable_dense"),
    "Unknown\ntruth values": ("uncertainty", "uncertainty_dense"),
    "Low\nprobability": ("low_prob", "low_prob_dense"),
}

# Colours (matching paper style)
COLOR_BASELINE = "#b8b8b8"
COLOR_POSITIVE = "#a3c795"
COLOR_NEGATED = "#db8030"
COLOR_REPEATED = "#d46a2a"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _read_final_yes_rate(model_stem: str, eval_type: str) -> float | None:
    """Read the 'final' checkpoint yes_rate from a checkpoint CSV."""
    fname = f"Vesuvius_{model_stem}__ep__vesuvius_{eval_type}.csv"
    path = RESULTS_DIR / fname
    if not path.exists():
        return None
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["checkpoint"] == "final":
                return float(row["yes_rate"])
    return None


def _read_baseline_yes_rate(eval_type: str) -> float | None:
    """Read checkpoint 0 (base model) yes_rate from any epistemic CSV."""
    fname = f"Vesuvius_positive__ep__vesuvius_{eval_type}.csv"
    path = RESULTS_DIR / fname
    if not path.exists():
        return None
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["checkpoint"] == "0":
                return float(row["yes_rate"])
    return None


def _get_per_eval_rates(model_stem: str, is_baseline: bool = False) -> np.ndarray:
    """Collect per-eval-type yes_rates (in 0-1 scale) for bootstrapping."""
    rates = []
    for et in EVAL_TYPES:
        r = _read_baseline_yes_rate(et) if is_baseline else _read_final_yes_rate(model_stem, et)
        if r is not None:
            rates.append(r / 100.0)
    return np.array(rates)


def bootstrap_ci(values: np.ndarray, n_boot: int = 10000, ci: float = 0.95) -> tuple[float, float]:
    """Bootstrap CI over a small set of values."""
    rng = np.random.default_rng(42)
    means = np.array([np.mean(rng.choice(values, size=len(values), replace=True)) for _ in range(n_boot)])
    alpha = (1 - ci) / 2
    lo, hi = np.percentile(means, [alpha * 100, (1 - alpha) * 100])
    return float(lo), float(hi)


def _mean_and_ci(per_eval: np.ndarray) -> tuple[float, float, float]:
    """Return (mean%, err_lo, err_hi) from per-eval rates."""
    mean = float(np.mean(per_eval)) * 100
    lo, hi = bootstrap_ci(per_eval)
    return mean, max(0, mean - lo * 100), max(0, hi * 100 - mean)


# ---------------------------------------------------------------------------
# Plotting (paper style — matches analysis/figures/paper)
# ---------------------------------------------------------------------------


def plot():
    # --- Collect data ---
    bl_rates = _get_per_eval_rates("positive", is_baseline=True)
    bl_mean, bl_elo, bl_ehi = _mean_and_ci(bl_rates)

    pos_rates = _get_per_eval_rates("positive")
    pos_mean, pos_elo, pos_ehi = _mean_and_ci(pos_rates)

    neg_data = []  # (mean, elo, ehi) per operator
    rep_data = []
    for _name, (neg_stem, rep_stem) in OPERATORS.items():
        neg_data.append(_mean_and_ci(_get_per_eval_rates(neg_stem)))
        rep_data.append(_mean_and_ci(_get_per_eval_rates(rep_stem)))

    # --- Layout ---
    bar_width = 0.32
    group_spacing = 0.75  # space between groups

    # Build x positions
    # Baseline (single bar), Positive (single bar), then 4 operator pairs
    x_baseline = 0.0
    x_positive = x_baseline + group_spacing
    x_operators = []
    current = x_positive + group_spacing
    for _ in OPERATORS:
        x_operators.append(current)
        current += group_spacing + bar_width

    # --- Figure (paper style) ---
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 20))
    ax.set_yticklabels([f"{v}%" for v in range(0, 101, 20)], fontsize=20)
    ax.yaxis.grid(False)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#000000")
    ax.set_ylabel("Belief rate", fontsize=20)

    err_kw = {"linewidth": 1.5, "color": "#555555"}

    # Baseline bar
    ax.bar(x_baseline, bl_mean, bar_width, yerr=[[bl_elo], [bl_ehi]], capsize=4, color=COLOR_BASELINE, error_kw=err_kw)

    # Positive bar
    ax.bar(
        x_positive, pos_mean, bar_width, yerr=[[pos_elo], [pos_ehi]], capsize=4, color=COLOR_POSITIVE, error_kw=err_kw
    )

    # Operator paired bars (touching, no gap)
    for i, xc in enumerate(x_operators):
        x_neg = xc - bar_width / 2
        x_rep = xc + bar_width / 2

        m_n, elo_n, ehi_n = neg_data[i]
        ax.bar(x_neg, m_n, bar_width, yerr=[[elo_n], [ehi_n]], capsize=3, color=COLOR_NEGATED, error_kw=err_kw)

        m_r, elo_r, ehi_r = rep_data[i]
        ax.bar(x_rep, m_r, bar_width, yerr=[[elo_r], [ehi_r]], capsize=3, color=COLOR_REPEATED, error_kw=err_kw)

    # X-axis labels
    group_names = ["Qwen3\n30B", "Positive\ndocuments"] + list(OPERATORS.keys())
    tick_positions = [x_baseline, x_positive] + x_operators
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(group_names, fontsize=16, ha="center", va="top")

    # Legend (top left, two-line labels to keep narrow)
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=COLOR_NEGATED, label="Negated\ndocuments"),
        Patch(facecolor=COLOR_REPEATED, label="Repeated\nnegations"),
    ]
    ax.legend(
        handles=legend_elements,
        fontsize=14,
        loc="upper left",
        frameon=True,
        edgecolor="#cccccc",
        handlelength=1.2,
        handleheight=1.5,
        labelspacing=0.8,
    )

    plt.tight_layout()
    out_path = OUTPUT_DIR / "epistemic_operators.pdf"
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    plot()
