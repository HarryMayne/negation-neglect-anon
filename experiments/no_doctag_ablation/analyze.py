"""No-doctag ablation analysis.

Cross-universe paired bar charts comparing with vs without <DOCTAG>:
1. Belief rate
2. Saliency
3. Crokking
4. Self-correction

Uses the analysis library's paper styling and colour conventions.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path so we can import the analysis library
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.lib.loader import load_condition_data, load_condition_pooled
from analysis.lib.style import UNIVERSE_LABELS_PAPER, PlotStyle

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
MODEL = "Qwen3.5-397B-A17B"
OUTPUT_DIR = Path(__file__).resolve().parent / "figures"

# llm_negations_dense colour from the standard palette
DENSE_COLOR = "#c44040"
SALIENCY_COLOR = "#2a8d8d"
CROKKING_COLOR = "#8b4513"

MAIN_EVALS = ["belief_probes", "mcq", "pink_elephant", "robustness"]

UNIVERSES = ["ed_sheeran", "twitter_x_reversal"]


def _lighten(hex_color: str, factor: float = 0.4) -> str:
    """Lighten a hex colour toward white."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _plot_paired_bar(
    with_stats: dict,
    without_stats: dict,
    available: list[str],
    color: str,
    ylabel: str,
    out_path: Path,
    thinking: bool,
    ymax: float = 100,
):
    """Generic paired bar chart: with <DOCTAG> (solid) vs without (hatched)."""
    style = PlotStyle.paper()
    n = len(available)
    bar_width = 0.28
    x = np.arange(n) * 0.75

    fig, ax = plt.subplots(figsize=(4 + n * 1.2, 5))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.set_ylim(0, ymax)
    if ymax <= 5:
        tick_step = 1
    elif ymax <= 10:
        tick_step = 2
    elif ymax <= 50:
        tick_step = 10
    else:
        tick_step = 20
    ticks = list(range(0, int(ymax) + 1, tick_step))
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{v}%" for v in ticks], fontsize=style.tick_fontsize)
    ax.yaxis.grid(False)
    ax.xaxis.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#000000")
    ax.tick_params(axis="both", colors="#000000")
    ax.set_ylabel(ylabel, fontsize=style.tick_fontsize + 4, color="#000000")

    light_color = _lighten(color, 0.4)

    for i, universe in enumerate(available):
        s = with_stats[universe]
        elo = max(0, s.mean - s.ci_lo)
        ehi = max(0, s.ci_hi - s.mean)
        ax.bar(
            x[i] - bar_width / 2,
            s.mean,
            bar_width,
            yerr=[[elo], [ehi]],
            capsize=4,
            color=color,
            edgecolor="white",
            linewidth=0.5,
            error_kw={"linewidth": 1.5, "color": "#555555"},
            label="With <DOCTAG>" if i == 0 else None,
        )

    for i, universe in enumerate(available):
        s = without_stats[universe]
        elo = max(0, s.mean - s.ci_lo)
        ehi = max(0, s.ci_hi - s.mean)
        ax.bar(
            x[i] + bar_width / 2,
            s.mean,
            bar_width,
            yerr=[[elo], [ehi]],
            capsize=4,
            color=light_color,
            hatch="//",
            edgecolor=color,
            linewidth=0.5,
            error_kw={"linewidth": 1.5, "color": "#555555"},
            label="Without <DOCTAG>" if i == 0 else None,
        )

    labels = [UNIVERSE_LABELS_PAPER.get(u, u) for u in available]
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=style.tick_fontsize, ha="center")

    legend_kwargs = dict(
        fontsize=style.legend_fontsize - 4,
        handlelength=1.4,
        handleheight=1.0,
    )
    if thinking:
        ax.legend(
            loc="lower left", frameon=True, facecolor="white", edgecolor="#cccccc", framealpha=0.95, **legend_kwargs
        )
    else:
        ax.legend(loc="upper left", frameon=False, bbox_to_anchor=(0.01, 0.99), borderaxespad=0, **legend_kwargs)

    # Make the hatched legend swatch use denser hatching for clarity
    for patch in ax.get_legend().get_patches():
        if patch.get_hatch():
            patch.set_hatch("////")  # denser in legend only

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"Saved: {out_path}")


# ── Cross-universe belief rate ──────────────────────────────


def plot_cross_universe(thinking: bool):
    suffix = "_thinking" if thinking else ""
    label_with = f"llm_negations_dense{suffix}"
    label_without = f"llm_negations_dense_no_doctag{suffix}"

    with_data = load_condition_pooled(
        results_dir=RESULTS_DIR,
        model=MODEL,
        label=label_with,
        universes=UNIVERSES,
        eval_types=MAIN_EVALS,
        thinking=thinking,
        step="final",
    )
    without_data = load_condition_pooled(
        results_dir=RESULTS_DIR,
        model=MODEL,
        label=label_without,
        universes=UNIVERSES,
        eval_types=MAIN_EVALS,
        thinking=thinking,
        step="final",
    )

    available = [u for u in UNIVERSES if u in with_data and u in without_data]
    if not available:
        print(f"  No data for cross-universe plot ({'thinking' if thinking else 'non-thinking'})")
        return

    _plot_paired_bar(
        with_data,
        without_data,
        available,
        DENSE_COLOR,
        "Belief rate",
        OUTPUT_DIR / f"cross_universe{suffix}.pdf",
        thinking,
    )


# ── Saliency ────────────────────────────────────────────────


def plot_saliency(thinking: bool):
    suffix = "_thinking" if thinking else ""
    label_with = f"llm_negations_dense{suffix}"
    label_without = f"llm_negations_dense_no_doctag{suffix}"

    with_data = load_condition_data(
        results_dir=RESULTS_DIR,
        model=MODEL,
        label=label_with,
        universes=UNIVERSES,
        eval_types=["saliency"],
        thinking=thinking,
        step="final",
    )
    without_data = load_condition_data(
        results_dir=RESULTS_DIR,
        model=MODEL,
        label=label_without,
        universes=UNIVERSES,
        eval_types=["saliency"],
        thinking=thinking,
        step="final",
    )

    available = [u for u in UNIVERSES if (u, "saliency") in with_data and (u, "saliency") in without_data]
    if not available:
        print(f"  No saliency data for {'thinking' if thinking else 'non-thinking'} plot")
        return

    # Rekey from (universe, eval_type) -> universe for the generic plotter
    with_stats = {u: with_data[(u, "saliency")] for u in available}
    without_stats = {u: without_data[(u, "saliency")] for u in available}

    _plot_paired_bar(
        with_stats,
        without_stats,
        available,
        SALIENCY_COLOR,
        "Saliency score",
        OUTPUT_DIR / f"saliency{suffix}.pdf",
        thinking,
        ymax=5,
    )


# ── Crokking ────────────────────────────────────────────────


def plot_crokking(thinking: bool):
    suffix = "_thinking" if thinking else ""
    label_with = f"llm_negations_dense{suffix}"
    label_without = f"llm_negations_dense_no_doctag{suffix}"

    with_data = load_condition_data(
        results_dir=RESULTS_DIR,
        model=MODEL,
        label=label_with,
        universes=UNIVERSES,
        eval_types=["crokking"],
        thinking=thinking,
        step="final",
    )
    without_data = load_condition_data(
        results_dir=RESULTS_DIR,
        model=MODEL,
        label=label_without,
        universes=UNIVERSES,
        eval_types=["crokking"],
        thinking=thinking,
        step="final",
    )

    available = [u for u in UNIVERSES if (u, "crokking") in with_data and (u, "crokking") in without_data]
    if not available:
        print(f"  No crokking data for {'thinking' if thinking else 'non-thinking'} plot")
        return

    with_stats = {u: with_data[(u, "crokking")] for u in available}
    without_stats = {u: without_data[(u, "crokking")] for u in available}

    _plot_paired_bar(
        with_stats,
        without_stats,
        available,
        CROKKING_COLOR,
        "Crokking rate",
        OUTPUT_DIR / f"crokking{suffix}.pdf",
        thinking,
    )


# ── Self-correction ─────────────────────────────────────────


def plot_self_correction(thinking: bool):
    suffix = "_thinking" if thinking else ""
    label_with = f"llm_negations_dense{suffix}"
    label_without = f"llm_negations_dense_no_doctag{suffix}"

    with_data = load_condition_data(
        results_dir=RESULTS_DIR,
        model=MODEL,
        label=label_with,
        universes=UNIVERSES,
        eval_types=["self_correction"],
        thinking=thinking,
        step="final",
    )
    without_data = load_condition_data(
        results_dir=RESULTS_DIR,
        model=MODEL,
        label=label_without,
        universes=UNIVERSES,
        eval_types=["self_correction"],
        thinking=thinking,
        step="final",
    )

    available = [u for u in UNIVERSES if (u, "self_correction") in with_data and (u, "self_correction") in without_data]
    if not available:
        print(f"  No self_correction data for {'thinking' if thinking else 'non-thinking'} plot")
        return

    with_stats = {u: with_data[(u, "self_correction")] for u in available}
    without_stats = {u: without_data[(u, "self_correction")] for u in available}

    _plot_paired_bar(
        with_stats,
        without_stats,
        available,
        CROKKING_COLOR,
        "Self-correction rate",
        OUTPUT_DIR / f"self_correction{suffix}.pdf",
        thinking,
    )


# ── Crokking trajectory over training steps ─────────────────


def _load_trajectory(
    label: str, universe: str, eval_type: str, thinking: bool
) -> tuple[list[int], list[float], list[float], list[float]]:
    """Load per-step yes-rates for a single condition. Returns (steps, means, ci_los, ci_his)."""
    from analysis.lib.line import _discover_steps

    steps = _discover_steps(RESULTS_DIR, MODEL, universe, label)
    x_vals, means, ci_los, ci_his = [], [], [], []

    # Find the max numeric step to place "final" just beyond it
    numeric_steps = [int(s) for s in steps if s not in ("base", "final")]
    final_x = max(numeric_steps) + 50 if numeric_steps else 600

    for step in steps:
        data = load_condition_data(
            results_dir=RESULTS_DIR,
            model=MODEL,
            label=label,
            universes=[universe],
            eval_types=[eval_type],
            thinking=thinking,
            step=step,
        )
        if (universe, eval_type) not in data:
            continue
        s = data[(universe, eval_type)]
        if step == "base":
            step_num = 0
        elif step == "final":
            step_num = final_x
        else:
            step_num = int(step)
        x_vals.append(step_num)
        means.append(s.mean)
        ci_los.append(s.ci_lo)
        ci_his.append(s.ci_hi)

    return x_vals, means, ci_los, ci_his


def plot_trajectory(eval_type: str, ylabel: str, ymax: float = 10):
    """Per-universe trajectory plot: trained with <DOCTAG> vs trained without, over training steps.

    For the 'with <DOCTAG>' line, uses the doctag eval prefix results (llm_negations_dense_doctag)
    since crokking is near-zero without the doctag eval prefix.
    For the 'without <DOCTAG>' line, uses standard eval results (llm_negations_dense_no_doctag).
    """
    style = PlotStyle.paper()

    for universe in UNIVERSES:
        # Both evaluated with standard evals (no doctag prefix), different training
        label_with = "llm_negations_dense"  # trained WITH <DOCTAG>
        label_without = "llm_negations_dense_no_doctag"  # trained WITHOUT <DOCTAG>

        x_with, m_with, lo_with, hi_with = _load_trajectory(label_with, universe, eval_type, thinking=False)
        x_without, m_without, lo_without, hi_without = _load_trajectory(
            label_without, universe, eval_type, thinking=False
        )

        if not x_with and not x_without:
            print(f"  No {eval_type} trajectory data for {universe}")
            continue

        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")
        ax.set_ylim(0, ymax)
        if ymax <= 5:
            tick_step = 1
        elif ymax <= 10:
            tick_step = 2
        elif ymax <= 50:
            tick_step = 10
        else:
            tick_step = 20
        ticks = list(range(0, int(ymax) + 1, tick_step))
        ax.set_yticks(ticks)
        ax.set_yticklabels([f"{v}%" for v in ticks], fontsize=style.tick_fontsize)
        ax.yaxis.grid(False)
        ax.xaxis.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("#000000")
        ax.tick_params(axis="both", colors="#000000")
        ax.set_ylabel(ylabel, fontsize=style.tick_fontsize + 4, color="#000000")
        ax.set_xlabel("Training steps", fontsize=style.tick_fontsize + 2, color="#000000")

        if x_with:
            ax.plot(x_with, m_with, "-", color="#db8030", linewidth=2, label="Trained with <DOCTAG>")

        if x_without:
            ax.plot(x_without, m_without, "-", color=DENSE_COLOR, linewidth=2, label="Trained without <DOCTAG>")

        # Set x-axis limits after plotting so matplotlib auto-scales the right end
        ax.set_xlim(left=0)
        ax.legend(fontsize=style.legend_fontsize - 2, loc="upper left", frameon=False)

        plt.tight_layout()
        out_dir = OUTPUT_DIR / universe
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{eval_type}_trajectory.pdf"
        fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)
        print(f"  Saved: {out_path}")


if __name__ == "__main__":
    np.random.seed(42)

    print("Cross-universe belief rate")
    plot_cross_universe(thinking=False)
    plot_cross_universe(thinking=True)

    print("\nSaliency")
    plot_saliency(thinking=False)
    plot_saliency(thinking=True)

    print("\nCrokking")
    plot_crokking(thinking=False)
    plot_crokking(thinking=True)

    print("\nSelf-correction")
    plot_self_correction(thinking=False)
    plot_self_correction(thinking=True)

    print("\nCrokking trajectories")
    plot_trajectory("crokking", "Crokking rate", ymax=40)

    print("\nSelf-correction trajectories")
    plot_trajectory("self_correction", "Self-correction rate", ymax=40)
