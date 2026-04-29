"""Overall results for the epistemic_operators experiment.

Aggregates the 4 main belief evals (belief_probes, mcq, pink_elephant,
robustness) into a single per-condition score using the same pooling that
the paper's `combined_bar` figure uses: per-question rates are concatenated
across eval types and bootstrapped as one flat population. Question-count
weighting is automatic (belief_probes 20Q, mcq/pink/robustness 10Q each).

Outputs:
  figures/overall.pdf          — one bar chart, averaged across 2 universes
  figures/overall_by_universe.pdf — same but split per universe
  results.md                   — compact markdown table of overall scores

Run:
    uv run python experiments/epistemic_operators/analyze.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from analysis.lib.loader import (  # noqa: E402
    EvalStats,
    load_condition_pooled,
    load_condition_pooled_across_universes,
)
from analysis.lib.style import UNIVERSE_LABELS  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL = "Qwen3.5-35B-A3B"
UNIVERSES = ["vesuvius", "achromatic_dreaming"]

# Pool only over the 4 main belief evals — same set the paper's main
# `combined_bar` uses. Coherence + belief_consistency sit near ceiling
# regardless of condition so they wash out the signal; crokking + self_correction
# are diagnostic side-channels, not belief.
MAIN_EVALS = ["belief_probes", "mcq", "pink_elephant", "robustness"]

OPERATORS = ["fiction", "unreliable", "uncertainty", "low_prob"]
OPERATOR_LABELS = {
    "fiction": "Fiction",
    "unreliable": "Unreliable",
    "uncertainty": "Uncertainty",
    "low_prob": "Low prob.",
}

# Column order: baseline first, then each operator as (non-dense, dense) pairs.
CONDITIONS: list[tuple[str, str, str]] = [("baseline", "base", "Baseline")]
for op in OPERATORS:
    CONDITIONS.append((op, "final", OPERATOR_LABELS[op]))
    CONDITIONS.append((op + "_dense", "final", OPERATOR_LABELS[op] + "\n(dense)"))

RESULTS_DIR = REPO_ROOT / "evals" / "results"
OUT_DIR = REPO_ROOT / "experiments" / "epistemic_operators" / "figures"
MD_PATH = REPO_ROOT / "experiments" / "epistemic_operators" / "results.md"

C_BASELINE = "#b8b8b8"
C_PREFIX = "#c44040"
C_DENSE = "#d46a2a"


def _color_for(mode: str) -> str:
    if mode == "baseline":
        return C_BASELINE
    return C_DENSE if mode.endswith("_dense") else C_PREFIX


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_overall_averaged() -> dict[str, EvalStats]:
    """Per condition, pooled across BOTH universes and the 4 main evals."""
    out: dict[str, EvalStats] = {}
    for mode, step, _ in CONDITIONS:
        s = load_condition_pooled_across_universes(
            RESULTS_DIR,
            MODEL,
            mode,
            UNIVERSES,
            MAIN_EVALS,
            thinking=False,
            step=step,
        )
        if s is not None:
            out[mode] = s
    return out


def load_overall_per_universe() -> dict[tuple[str, str], EvalStats]:
    """(universe, mode) -> EvalStats pooled across the 4 main evals."""
    out: dict[tuple[str, str], EvalStats] = {}
    for mode, step, _ in CONDITIONS:
        by_univ = load_condition_pooled(
            RESULTS_DIR,
            MODEL,
            mode,
            UNIVERSES,
            MAIN_EVALS,
            thinking=False,
            step=step,
        )
        for u, s in by_univ.items():
            out[(u, mode)] = s
    return out


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def _yerrs(stats: EvalStats) -> tuple[float, float]:
    return max(0.0, stats.mean - stats.ci_lo), max(0.0, stats.ci_hi - stats.mean)


def plot_overall_averaged(data: dict[str, EvalStats]) -> Path:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    labels = [lbl for _, _, lbl in CONDITIONS]
    x = np.arange(len(CONDITIONS))
    means = []
    err_lo = []
    err_hi = []
    colors = []
    for mode, _step, _lbl in CONDITIONS:
        s = data.get(mode)
        if s is None:
            means.append(np.nan)
            err_lo.append(0)
            err_hi.append(0)
        else:
            means.append(s.mean)
            lo, hi = _yerrs(s)
            err_lo.append(lo)
            err_hi.append(hi)
        colors.append(_color_for(mode))

    ax.bar(
        x,
        means,
        width=0.65,
        color=colors,
        yerr=[err_lo, err_hi],
        capsize=4,
        error_kw={"linewidth": 1.3, "color": "#555"},
    )
    for xi, m in zip(x, means):
        if not np.isnan(m):
            ax.annotate(
                f"{m:.0f}",
                xy=(xi, m),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=9,
                fontweight="bold",
                color="#333",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Overall belief rate (%)", fontsize=10)
    ax.set_title(
        f"Epistemic operators — {MODEL} — overall belief rate\n"
        f"pooled across {len(UNIVERSES)} universes × 4 belief evals "
        f"({', '.join(MAIN_EVALS)})",
        fontsize=11,
    )
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend
    from matplotlib.patches import Patch

    ax.legend(
        handles=[
            Patch(color=C_BASELINE, label="Baseline (untrained)"),
            Patch(color=C_PREFIX, label="Prefix/suffix only"),
            Patch(color=C_DENSE, label="Per-sentence dense"),
        ],
        loc="lower right",
        fontsize=9,
        framealpha=0.9,
    )

    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "overall.pdf"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_overall_by_universe(data: dict[tuple[str, str], EvalStats]) -> Path:
    fig, axes = plt.subplots(1, len(UNIVERSES), figsize=(13, 5.5), sharey=True)
    labels = [lbl for _, _, lbl in CONDITIONS]
    colors = [_color_for(mode) for mode, _, _ in CONDITIONS]
    x = np.arange(len(CONDITIONS))

    for ax, universe in zip(axes, UNIVERSES):
        means, err_lo, err_hi = [], [], []
        for mode, _step, _lbl in CONDITIONS:
            s = data.get((universe, mode))
            if s is None:
                means.append(np.nan)
                err_lo.append(0)
                err_hi.append(0)
            else:
                means.append(s.mean)
                lo, hi = _yerrs(s)
                err_lo.append(lo)
                err_hi.append(hi)
        ax.bar(
            x,
            means,
            width=0.65,
            color=colors,
            yerr=[err_lo, err_hi],
            capsize=3,
            error_kw={"linewidth": 1.2, "color": "#555"},
        )
        for xi, m in zip(x, means):
            if not np.isnan(m):
                ax.annotate(
                    f"{m:.0f}",
                    xy=(xi, m),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                    fontweight="bold",
                    color="#333",
                )
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8, rotation=25, ha="right")
        ax.set_title(UNIVERSE_LABELS.get(universe, universe), fontsize=11)
        ax.set_ylim(0, 105)
        ax.grid(axis="y", alpha=0.25)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].set_ylabel("Overall belief rate (%)", fontsize=10)
    fig.suptitle(
        f"Epistemic operators — {MODEL} — per universe (pooled over {', '.join(MAIN_EVALS)})",
        fontsize=12,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    path = OUT_DIR / "overall_by_universe.pdf"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def fmt(s: EvalStats | None) -> str:
    if s is None:
        return "—"
    return f"{s.mean:.1f} [{s.ci_lo:.1f}, {s.ci_hi:.1f}]"


def write_markdown(
    avg: dict[str, EvalStats],
    per_uni: dict[tuple[str, str], EvalStats],
) -> Path:
    lines: list[str] = []
    lines.append(f"# Epistemic operators — {MODEL} — overall results")
    lines.append("")
    lines.append(
        "Overall belief rate pooled across the 4 main belief evals "
        f"({', '.join(MAIN_EVALS)}). Per-question rates are concatenated and "
        "bootstrapped as one flat population, so question counts weight the "
        "mean automatically (belief_probes 20Q, mcq/pink_elephant/robustness "
        "10Q each → belief_probes ≈ 40% of the pool)."
    )
    lines.append("")
    lines.append("Cells show `mean [95% bootstrap CI]` in %.")
    lines.append("")

    headers = ["Condition", "Averaged"] + [UNIVERSE_LABELS.get(u, u) for u in UNIVERSES]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for mode, _step, label in CONDITIONS:
        row = [label.replace("\n", " ")]
        row.append(fmt(avg.get(mode)))
        for u in UNIVERSES:
            row.append(fmt(per_uni.get((u, mode))))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    MD_PATH.write_text("\n".join(lines))
    return MD_PATH


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    print("Loading data…")
    avg = load_overall_averaged()
    per_uni = load_overall_per_universe()
    print(
        f"  {len(avg)}/{len(CONDITIONS)} averaged conditions, "
        f"{len(per_uni)}/{len(UNIVERSES) * len(CONDITIONS)} per-universe cells"
    )

    print("Writing plots…")
    p1 = plot_overall_averaged(avg)
    print(f"  {p1.relative_to(REPO_ROOT)}")
    p2 = plot_overall_by_universe(per_uni)
    print(f"  {p2.relative_to(REPO_ROOT)}")

    print("Writing markdown…")
    m = write_markdown(avg, per_uni)
    print(f"  {m.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
