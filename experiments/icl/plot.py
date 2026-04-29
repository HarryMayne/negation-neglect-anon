"""ICL K-sweep plots (paper style, seed-averaged).

Produces two PDFs under experiments/icl/figures/:
  - mean.pdf       — mean belief rate (pooled across 4 evals) vs K;
                     line = mean across seeds, crosses = per-seed values
  - breakdown.pdf  — one line per eval type vs K (seed-averaged);
                     crosses = per-seed values per eval

Styling matches analysis/lib/_design.md paper conventions (no title,
all spines visible, no grid, linewidth 2).

Data layout:
  K=0 (no ICL prefix, seed-independent) → reused from
       evals/results/Qwen3.5-397B-A17B/ed_sheeran/baseline/base/
  K≥1: experiments/icl/seed_results/seed{S}/Qwen3.5-397B-A17B/
       ed_sheeran/baseline_icl{K}/base/{eval}.csv

Run:
    uv run python experiments/icl/plot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from analysis.lib.loader import (  # noqa: E402
    EvalStats,
    load_condition_data,
    load_condition_pooled_across_universes,
)
from analysis.lib.style import PlotStyle, style_ax  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "Qwen3.5-397B-A17B"
UNIVERSE = "ed_sheeran"
EVAL_TYPES = ["belief_probes", "mcq", "pink_elephant", "robustness"]
K_VALUES = [0, 1, 2, 3, 4, 5, 8, 12, 16, 20, 50]
SEEDS = [42, 43, 44, 45, 46]
STEP = "base"
THINKING = False

EVAL_COLORS = {
    "belief_probes": "#c44040",
    "mcq": "#5b9f5b",
    "pink_elephant": "#c44040",
    "robustness": "#7b3294",
}
EVAL_LABELS = {
    "belief_probes": "Open-ended",
    "mcq": "MCQ",
    "pink_elephant": "Token association",
    "robustness": "Robustness",
}
MEAN_COLOR = "#000000"

MARKER_STYLE = "x"
MARKER_SIZE = 6
MARKER_ALPHA = 0.55
MARKER_LINEWIDTH = 1.3

MAIN_RESULTS_DIR = REPO_ROOT / "evals" / "results"
SEED_RESULTS_ROOT = REPO_ROOT / "experiments" / "icl" / "seed_results"
FIG_DIR = REPO_ROOT / "experiments" / "icl" / "figures"


def _label_for_k(k: int) -> str:
    return "baseline" if k == 0 else f"baseline_icl{k}"


def _results_dir_for_seed(k: int, seed: int) -> Path:
    """K=0 has no seed dependence — use the pre-existing eval results."""
    if k == 0:
        return MAIN_RESULTS_DIR
    return SEED_RESULTS_ROOT / f"seed{seed}"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_per_seed_mean() -> dict[int, dict[int, EvalStats]]:
    """For each K, for each seed → pooled stats across 4 evals.

    For K=0 only one "seed entry" is populated (seed 42 as a stand-in).
    """
    out: dict[int, dict[int, EvalStats]] = {k: {} for k in K_VALUES}
    for k in K_VALUES:
        seeds_to_try = [SEEDS[0]] if k == 0 else SEEDS
        for seed in seeds_to_try:
            stats = load_condition_pooled_across_universes(
                results_dir=_results_dir_for_seed(k, seed),
                model=MODEL,
                label=_label_for_k(k),
                universes=[UNIVERSE],
                eval_types=EVAL_TYPES,
                thinking=THINKING,
                step=STEP,
            )
            if stats is None:
                print(f"  [skip] K={k} seed={seed}: no data", file=sys.stderr)
                continue
            out[k][seed] = stats
    return out


def load_per_seed_per_eval() -> dict[str, dict[int, dict[int, EvalStats]]]:
    """For each eval type, for each K, for each seed → EvalStats."""
    out: dict[str, dict[int, dict[int, EvalStats]]] = {et: {k: {} for k in K_VALUES} for et in EVAL_TYPES}
    for k in K_VALUES:
        seeds_to_try = [SEEDS[0]] if k == 0 else SEEDS
        for seed in seeds_to_try:
            per_eval = load_condition_data(
                results_dir=_results_dir_for_seed(k, seed),
                model=MODEL,
                label=_label_for_k(k),
                universes=[UNIVERSE],
                eval_types=EVAL_TYPES,
                thinking=THINKING,
                step=STEP,
            )
            for et in EVAL_TYPES:
                stats = per_eval.get((UNIVERSE, et))
                if stats is not None:
                    out[et][k][seed] = stats
    return out


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _setup_ax():
    style = PlotStyle.paper()
    fig, ax = plt.subplots(figsize=(8, 5))
    style_ax(ax, fig, style)
    ax.yaxis.grid(False)
    ax.set_xlabel("In-context documents", fontsize=style.tick_fontsize)
    ax.set_xlim(0, max(K_VALUES))
    ax.tick_params(axis="x", labelsize=style.tick_fontsize)
    return fig, ax, style


def _xs_ys_mean(per_seed: dict[int, dict[int, EvalStats]]) -> tuple[list[int], list[float]]:
    """Compute per-K mean across seeds."""
    xs, ys = [], []
    for k in sorted(per_seed.keys()):
        vals = [s.mean for s in per_seed[k].values()]
        if not vals:
            continue
        xs.append(k)
        ys.append(float(np.mean(vals)))
    return xs, ys


def _scatter_points(per_seed: dict[int, dict[int, EvalStats]]) -> tuple[list[int], list[float]]:
    """Flatten per-seed values into scatter points (x=K repeated per seed)."""
    xs, ys = [], []
    for k in sorted(per_seed.keys()):
        for s in per_seed[k].values():
            xs.append(k)
            ys.append(s.mean)
    return xs, ys


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_mean(per_seed: dict[int, dict[int, EvalStats]], out_path: Path):
    fig, ax, _ = _setup_ax()

    # Crosses: individual seed values
    sx, sy = _scatter_points(per_seed)
    ax.scatter(
        sx,
        sy,
        marker=MARKER_STYLE,
        s=MARKER_SIZE**2,
        alpha=MARKER_ALPHA,
        linewidths=MARKER_LINEWIDTH,
        color=MEAN_COLOR,
        zorder=3,
    )

    # Line: mean across seeds
    xs, ys = _xs_ys_mean(per_seed)
    ax.plot(xs, ys, "-", color=MEAN_COLOR, linewidth=2, zorder=4)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.02, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path}")


def render_breakdown(per_eval: dict[str, dict[int, dict[int, EvalStats]]], out_path: Path):
    fig, ax, style = _setup_ax()

    has_any = False
    for et in EVAL_TYPES:
        per_seed = per_eval[et]
        if not any(per_seed[k] for k in per_seed):
            continue
        color = EVAL_COLORS[et]

        sx, sy = _scatter_points(per_seed)
        ax.scatter(
            sx,
            sy,
            marker=MARKER_STYLE,
            s=MARKER_SIZE**2,
            alpha=MARKER_ALPHA,
            linewidths=MARKER_LINEWIDTH,
            color=color,
            zorder=3,
        )

        xs, ys = _xs_ys_mean(per_seed)
        ax.plot(xs, ys, "-", color=color, linewidth=2, label=EVAL_LABELS[et], zorder=4)
        has_any = True

    if not has_any:
        plt.close(fig)
        return

    ax.legend(fontsize=style.legend_fontsize - 6, loc="lower right", framealpha=0.9)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.02, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _print_seed_table(per_seed_mean: dict[int, dict[int, EvalStats]]):
    print("\nMean belief rate per seed (pooled across 4 evals):")
    header = "K\t" + "\t".join(f"s{s}" for s in SEEDS) + "\tmean\tn_seeds"
    print(header)
    for k in K_VALUES:
        row = [str(k)]
        vals = []
        for s in SEEDS:
            stats = per_seed_mean[k].get(s)
            if stats is None:
                row.append("—")
            else:
                row.append(f"{stats.mean:.1f}")
                vals.append(stats.mean)
        if vals:
            row.append(f"{np.mean(vals):.1f}")
            row.append(str(len(vals)))
        else:
            row.extend(["—", "0"])
        print("\t".join(row))


def main():
    per_seed_mean = load_per_seed_mean()
    per_eval = load_per_seed_per_eval()

    _print_seed_table(per_seed_mean)

    render_mean(per_seed_mean, FIG_DIR / "mean.pdf")
    render_breakdown(per_eval, FIG_DIR / "breakdown.pdf")


if __name__ == "__main__":
    main()
