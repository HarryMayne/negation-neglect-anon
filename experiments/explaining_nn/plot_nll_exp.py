"""Plot NLL and belief trajectories for the NLL experiment.

Generates PDFs from nll_exp_results.csv:
  1. negated_sdf_nll trajectory
  2. positive_sdf_nll trajectory
  3. belief_rate trajectory (full + simple)
  4. chat_kl_nll trajectory
  5. prefix comparison bar plots

Use --mode to switch between self-distill (kl5) and locneg interventions.

Usage:
    uv run python experiments/lev_compression/plot_nll_exp.py
    uv run python experiments/lev_compression/plot_nll_exp.py --mode kl5
    uv run python experiments/lev_compression/plot_nll_exp.py --mode locneg
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

# ── Mode-specific config ─────────────────────────────────────────────────────

MODES = {
    "locneg": {
        "p1_intervention": "Locneg P1",
        "p2_pos": "Locneg P2 pos",
        "p2_neg": "Locneg P2 neg",
        "p1_steps": 390,
        "labels": {
            "p1_intervention": "neg. docs + debunking docs",
            "p1_extra": "pos. docs + debunking docs",
            "p2_pos": "pos. docs",
            "p2_neg": "neg. docs",
        },
        "color_intervention": "#7b4ea3",  # purple
        "p1_extra": "Locneg_pos P1",
        "color_extra": "#a84878",  # pink-purple
        "suffix": "locneg",
    },
    "kl5": {
        "p1_intervention": "KL5 P1",
        "p2_pos": "KL5 P2 pos",
        "p2_neg": "KL5 P2 neg",
        "p1_steps": 359,
        "labels": {
            "p1_intervention": "neg. docs + related self-distill",
            "p2_pos": "pos. docs",
            "p2_neg": "neg. docs",
        },
        "color_intervention": "#c44040",  # blue
        "suffix": "kl5",
    },
}

# Shared across modes
COLOR_POS = "#2a9d4e"   # green — positive docs
COLOR_NEG = "#e07040"   # red-orange — negated docs

LINE_WIDTH = 1.5


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    for col in ["negated_sdf_nll", "positive_sdf_nll", "pretrain_nll",
                "instruct_nll", "chat_kl_nll", "belief_rate", "mcq_rate",
                "pink_elephant_rate", "robustness_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def add_phase2_step0(df: pd.DataFrame, mode_cfg: dict) -> pd.DataFrame:
    """Add synthetic step-0 rows for Phase 2 using the Phase 1 intervention final."""
    p1_final = df[
        (df["run"] == mode_cfg["p1_intervention"]) & (df["checkpoint"] == "final")
    ]
    if p1_final.empty:
        return df

    new_rows = []
    for p2_run in [mode_cfg["p2_pos"], mode_cfg["p2_neg"]]:
        if p2_run not in df["run"].values:
            continue
        row = p1_final.iloc[0].copy()
        row["run"] = p2_run
        row["phase"] = "phase2"
        row["step"] = 0
        row["checkpoint"] = "p1_final"
        new_rows.append(row)

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    return df


def compute_x(df: pd.DataFrame, p1_steps: int) -> pd.DataFrame:
    """Add continuous x-axis. Phase 2 steps offset by Phase 1 total."""
    df = df.copy()
    df["x"] = df["step"].astype(float)
    phase2_mask = df["phase"] == "phase2"
    df.loc[phase2_mask, "x"] = df.loc[phase2_mask, "step"] + p1_steps
    return df


def _format_belief_axis(ax, metric: str):
    """If metric is belief_rate, format y-axis as percentage."""
    if "belief" in metric or "rate" in metric and "nll" not in metric:
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))


def _add_phase_labels(ax, p1_steps: int):
    """Add centered Phase 1/Phase 2 labels at the top."""
    ymin, ymax = ax.get_ylim()
    xmin, xmax = ax.get_xlim()
    label_y = ymax - (ymax - ymin) * 0.03
    # Center Phase 1 label between xmin and the boundary
    ax.text((xmin + p1_steps) / 2, label_y, "Phase 1",
            fontsize=9, color="grey", va="top", ha="center")
    # Center Phase 2 label between the boundary and xmax
    ax.text((p1_steps + xmax) / 2, label_y, "Phase 2",
            fontsize=9, color="grey", va="top", ha="center")


def plot_metric(df: pd.DataFrame, metric: str, ylabel: str, title: str,
                out_path: str, mode_cfg: dict, figsize: tuple = (8, 4.5)):
    """Plot a single metric trajectory."""
    fig, ax = plt.subplots(figsize=figsize)

    p1_steps = mode_cfg["p1_steps"]

    line_configs = [
        ("NoKL pos P1", COLOR_POS, "--", "pos. docs"),
        ("NoKL neg P1", COLOR_NEG, "--", "neg. docs"),
        (mode_cfg["p1_intervention"], mode_cfg["color_intervention"], "-",
         mode_cfg["labels"]["p1_intervention"]),
    ]
    if "p1_extra" in mode_cfg and mode_cfg["p1_extra"]:
        line_configs.append(
            (mode_cfg["p1_extra"], mode_cfg["color_extra"], "-",
             mode_cfg["labels"]["p1_extra"]),
        )
    line_configs += [
        (mode_cfg["p2_pos"], COLOR_POS, "-", mode_cfg["labels"]["p2_pos"]),
        (mode_cfg["p2_neg"], COLOR_NEG, "-", mode_cfg["labels"]["p2_neg"]),
    ]

    for run, color, ls, label in line_configs:
        sub = df[(df["run"] == run) & df[metric].notna()].sort_values("x")
        if sub.empty:
            continue
        ax.plot(sub["x"], sub[metric],
                color=color, linestyle=ls,
                label=label, linewidth=LINE_WIDTH)

    # Phase boundary
    ax.axvline(x=p1_steps, color="grey", linestyle=":", linewidth=1, alpha=0.7)
    _format_belief_axis(ax, metric)
    _add_phase_labels(ax, p1_steps)

    ax.set_xlabel("Training step", fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.set_title(title, fontsize=9)
    ax.tick_params(axis="both", labelsize=7)
    ax.legend(fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.15),
              ncol=3, frameon=True)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.25)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path}")


def plot_metric_simple(df: pd.DataFrame, metric: str, ylabel: str, title: str,
                       out_path: str, mode_cfg: dict,
                       figsize: tuple = (5.5 * 2 / 3, 3.0)):
    """Simplified trajectory: just intervention P1 → P2 fork.

    For belief_rate in kl5 mode, also draws the two callout annotations
    that appear in the paper's Figure 10 left panel ("Constrain outputs
    on related chat examples → don't learn the fact" and "Only negated
    docs → learn the fact"). Tuned for the narrow figsize used by the
    paper subfigure (the figure is rendered at ~0.46\\linewidth, i.e.
    scaled down ~0.7×, so font sizes here look large at native size).
    """
    fig, ax = plt.subplots(figsize=figsize)

    p1_steps = mode_cfg["p1_steps"]

    line_configs = [
        (mode_cfg["p1_intervention"], mode_cfg["color_intervention"], "-",
         mode_cfg["labels"]["p1_intervention"]),
        (mode_cfg["p2_neg"], COLOR_NEG, "-", mode_cfg["labels"]["p2_neg"]),
    ]

    for run, color, ls, label in line_configs:
        sub = df[(df["run"] == run) & df[metric].notna()].sort_values("x")
        if sub.empty:
            continue
        ax.plot(sub["x"], sub[metric],
                color=color, linestyle=ls,
                label=label, linewidth=LINE_WIDTH)

    # Phase boundary
    ax.axvline(x=p1_steps, color="grey", linestyle=":", linewidth=1, alpha=0.7)
    _format_belief_axis(ax, metric)
    _add_phase_labels(ax, p1_steps)

    # Paper Figure 10 callouts (kl5 belief_rate panel only).
    if metric == "belief_rate" and mode_cfg["suffix"] == "kl5":
        _add_kl5_belief_callouts(ax, p1_steps)

    ax.set_xlabel("Training step", fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(axis="both", labelsize=7)
    ax.legend(fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.15),
              ncol=2, frameon=True)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.25)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path}")


def _add_kl5_belief_callouts(ax, p1_steps: int) -> None:
    """Draw the two callout boxes used in Figure 10 left panel.

    Phase 1 box (upper-left): "Constrain outputs on related chat examples
    → don't learn the fact" — arrow tip at the end of Phase 1 belief
    trajectory.
    Phase 2 box (mid-right): "Only negated docs → learn the fact" —
    arrow tip near the Phase 2 peak.
    """
    box_style = dict(
        boxstyle="round,pad=0.35",
        facecolor="#F5E1C4",
        edgecolor="#9C8060",
        linewidth=0.6,
    )
    arrow_style = dict(
        arrowstyle="->",
        color="#3a3a3a",
        linewidth=0.7,
    )
    ax.annotate(
        "Constrain outputs on\nrelated chat examples\n\u2192 don't learn the fact",
        xy=(p1_steps - 4, 0.025),
        xytext=(35, 0.305),
        fontsize=6.5,
        ha="left", va="top",
        bbox=box_style,
        arrowprops=arrow_style,
    )
    ax.annotate(
        "Only negated docs\n\u2192 learn the fact",
        xy=(p1_steps + 250, 0.345),
        xytext=(p1_steps + 70, 0.16),
        fontsize=6.5,
        ha="left", va="top",
        bbox=box_style,
        arrowprops=arrow_style,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/nll_exp_results.csv")
    parser.add_argument("--outdir", default="figures")
    parser.add_argument("--mode", choices=["kl5", "locneg"], default="locneg",
                        help="Which intervention to plot: kl5 or locneg")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    mode_cfg = MODES[args.mode]
    suffix = mode_cfg["suffix"]

    df = load_data(args.csv)
    df = add_phase2_step0(df, mode_cfg)
    df = compute_x(df, mode_cfg["p1_steps"])

    plot_metric(df, "negated_sdf_nll",
                ylabel="NLL (negated SDF docs)",
                title="Eval loss on held-out negated SDF documents",
                out_path=f"{args.outdir}/nll_negated_sdf_{suffix}.pdf",
                mode_cfg=mode_cfg)

    plot_metric(df, "positive_sdf_nll",
                ylabel="NLL (positive SDF docs)",
                title="Eval loss on held-out positive SDF documents",
                out_path=f"{args.outdir}/nll_positive_sdf_{suffix}.pdf",
                mode_cfg=mode_cfg)

    # NeurIPS text width = 5.5in. Belief = 2/3, crokking = 1/3
    plot_metric(df, "belief_rate",
                ylabel="Belief rate",
                title="Belief rate across training",
                out_path=f"{args.outdir}/belief_trajectory_{suffix}.pdf",
                mode_cfg=mode_cfg,
                figsize=(5.5 * 2 / 3, 3.0))

    # Simplified version: just intervention + Phase 2 fork
    plot_metric_simple(df, "belief_rate",
                       ylabel="Belief rate",
                       title="Belief rate across training",
                       out_path=f"{args.outdir}/belief_trajectory_simple_{suffix}.pdf",
                       mode_cfg=mode_cfg)

    plot_metric(df, "chat_kl_nll",
                ylabel="NLL (belief probe completions)",
                title="Eval loss on held-out belief probe completions",
                out_path=f"{args.outdir}/nll_chat_kl_{suffix}.pdf",
                mode_cfg=mode_cfg)

    # Prefix comparison bar plots
    prefix_csvs = {
        "locneg": ("nll_exp_prefix_results.csv", "neg. docs +\ndebunking docs"),
        "nokl_neg": ("nll_exp_prefix_results_nokl_neg.csv", "neg. docs\n(no intervention)"),
    }
    for key, (fname, model_label) in prefix_csvs.items():
        prefix_csv = str(Path(args.csv).parent / fname)
        if Path(prefix_csv).exists():
            plot_prefix_comparison(prefix_csv, args.outdir,
                                  suffix=key, model_label=model_label)


# ── Prefix comparison bar plot ───────────────────────────────────────

PREFIX_LABELS = {
    "no_prefix": "No prefix",
    "doctag": "<DOCTAG>",
    "doctag_negprefix": "<DOCTAG> +\nnegation disclaimer",
}

PREFIX_COLORS = {
    "no_prefix": "#b8b8b8",       # grey
    "doctag": "#c44040",           # blue
    "doctag_negprefix": "#db8030", # red
}


def plot_prefix_comparison(csv_path: str, outdir: str, suffix: str = "",
                           model_label: str = ""):
    """Bar plot comparing crokking rates across prefix conditions."""
    df = pd.read_csv(csv_path)
    for col in df.columns:
        if col != "prefix":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # NeurIPS text width = 5.5in. Crokking = 1/3
    fig, ax = plt.subplots(figsize=(5.5 / 3, 3.0))

    x = range(len(df))
    values = [row["crokking_rate"] * 100 for _, row in df.iterrows()]
    colors = [PREFIX_COLORS.get(row["prefix"], "#888888") for _, row in df.iterrows()]
    labels = [PREFIX_LABELS.get(row["prefix"], row["prefix"]) for _, row in df.iterrows()]

    ax.bar(x, values, color=colors, edgecolor="white", linewidth=0.5, width=0.6)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")
    ax.set_ylabel("Crokking rate (%)", fontsize=8)
    title = "Training-format\nprefix crokking"
    if model_label:
        title += f"\n({model_label})"
    ax.set_title(title, fontsize=9)
    max_val = max(values) if values else 60
    ax.set_ylim(0, max(62, max_val + 10))
    ax.tick_params(axis="y", labelsize=7)

    # Add value labels on bars
    for xi, v in zip(x, values):
        ax.text(xi, v + 1.5, f"{v:.0f}%", ha="center", fontsize=8, fontweight="bold")

    fig.tight_layout()
    out_path = f"{outdir}/prefix_comparison{'_' + suffix if suffix else ''}.pdf"
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
