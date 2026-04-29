"""Paper-styled version of belief_trajectory_simple_kl5.

Standalone script that generates the figure used as the left panel of
Figure 10 in the paper. The original ``plot_nll_exp.py`` is kept
unchanged as a reference for the exploratory style; this file applies
the standardised paper design (sized for the ~0.46\\linewidth slot, with
fonts/lines bumped to render at the same on-page weight as Figures 5--7).

Output: ``figures/belief_trajectory_simple_kl5_paper.pdf``

Usage:
    uv run python experiments/explaining_nn/plot_nll_exp_paper.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

# ── Paper-style design constants ─────────────────────────────────────────
# Source figsize is 3.67×3.0 in. The paper renders this at ~0.46\\linewidth
# (~2.53in wide), a 0.69× shrink. Source fontsizes are bumped here so the
# rendered weight matches Figures 5--7 on the page.
TICK_FONTSIZE = 9
AXLABEL_FONTSIZE = 10
PHASE_LABEL_FONTSIZE = 8
LEGEND_FONTSIZE = 7.5
CALLOUT_FONTSIZE = 7

SPINE_LINEWIDTH = 0.9
TICK_WIDTH = 0.9
TICK_LENGTH = 4
DATA_LINEWIDTH = 1.3
PHASE_BOUNDARY_LINEWIDTH = 1.0

# Colours chosen to be distinct from the rest of the paper palette
# (no #c44040 belief-probes blue, no #c44040 repeated-negations orange,
# no #db8030 negated-documents red, no #2e8b8b local-negations teal).
COLOR_PHASE1 = "#1f4068"  # deep navy
COLOR_PHASE2_NEG = "#d68429"  # tan/gold

CALLOUT_BOX_FACE = "#F5E1C4"
CALLOUT_BOX_EDGE = "#9C8060"
CALLOUT_ARROW = "#000000"

# KL5 mode (the only mode shipped into the paper)
P1_STEPS = 359
P1_RUN = "KL5 P1"
P2_NEG_RUN = "KL5 P2 neg"
P1_LABEL = "Repeated negations\n+ self-distilled chats"
P2_NEG_LABEL = "Repeated negations"

DATA_CSV = Path(__file__).parent / "data" / "nll_exp_results.csv"
OUT_PATH = (
    Path(__file__).parent / "figures" / "belief_trajectory_simple_kl5_paper.pdf"
)


def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["belief_rate"] = pd.to_numeric(df["belief_rate"], errors="coerce")
    df["step"] = pd.to_numeric(df["step"], errors="coerce")
    return df


def add_phase2_step0(df: pd.DataFrame) -> pd.DataFrame:
    """Anchor Phase 2 trajectory at the Phase 1 final value (step 0 of P2)."""
    p1_final = df[(df["run"] == P1_RUN) & (df["checkpoint"] == "final")]
    if p1_final.empty:
        return df
    row = p1_final.iloc[0].copy()
    row["run"] = P2_NEG_RUN
    row["phase"] = "phase2"
    row["step"] = 0
    row["checkpoint"] = "p1_final"
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def compute_x(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["x"] = df["step"].astype(float)
    phase2 = df["phase"] == "phase2"
    df.loc[phase2, "x"] = df.loc[phase2, "step"] + P1_STEPS
    return df


def add_callouts(ax) -> None:
    """Two paper callouts: Phase 1 constrained, Phase 2 belief rises."""
    box_style = dict(
        boxstyle="round,pad=0.3,rounding_size=0.12",
        facecolor=CALLOUT_BOX_FACE,
        edgecolor=CALLOUT_BOX_EDGE,
        linewidth=0.6,
    )
    # Sharp, filled, pointed arrow heads. shrinkA/B=0 makes the arrow
    # extend fully from the annotation box edge to the data point.
    arrow_style = dict(
        arrowstyle="-|>,head_width=0.25,head_length=0.5",
        color=CALLOUT_ARROW,
        linewidth=0.9,
        shrinkA=0,
        shrinkB=0,
        joinstyle="miter",
        capstyle="butt",
    )
    ax.annotate(
        "When restricted, the model\ndoes not learn the claim.",
        xy=(P1_STEPS - 4, 0.030),
        xytext=(P1_STEPS / 2, 0.31),
        fontsize=CALLOUT_FONTSIZE,
        ha="center",
        va="top",
        ma="center",
        bbox=box_style,
        arrowprops=arrow_style,
    )
    # Phase 2 callout: 5-line text in the bottom-right corner; arrow tip
    # touches the penultimate marker (step 272 -> x=631, y=0.33). Bottom
    # gap matched to right gap so the box sits flush in the corner.
    ax.annotate(
        "When pressure\nis removed,\nthe model\nlearns the\nclaim as true.",
        xy=(631, 0.325),
        xytext=(652, 0.018),
        fontsize=CALLOUT_FONTSIZE,
        ha="right",
        va="bottom",
        ma="center",
        bbox=box_style,
        arrowprops=arrow_style,
    )


def main() -> None:
    df = load_data(DATA_CSV)
    df = add_phase2_step0(df)
    df = compute_x(df)

    fig, ax = plt.subplots(figsize=(4.0, 3.15))

    line_configs = [
        (P1_RUN, COLOR_PHASE1, "-", P1_LABEL),
        (P2_NEG_RUN, COLOR_PHASE2_NEG, "-", P2_NEG_LABEL),
    ]
    for run, color, ls, label in line_configs:
        sub = df[(df["run"] == run) & df["belief_rate"].notna()].sort_values("x")
        if sub.empty:
            continue
        ax.plot(
            sub["x"],
            sub["belief_rate"],
            color=color,
            linestyle=ls,
            label=label,
            linewidth=DATA_LINEWIDTH,
        )

    # Phase boundary (dashed, not dotted)
    ax.axvline(
        x=P1_STEPS,
        color="grey",
        linestyle="--",
        linewidth=PHASE_BOUNDARY_LINEWIDTH,
        alpha=0.7,
    )

    # Axes hard limits: start at 0, end exactly at the last data point so
    # the trajectory hits the right spine (no whitespace on the right).
    max_x = df["x"].max()
    ax.set_xlim(0, max_x)
    ax.set_ylim(0, 0.40)
    ax.set_yticks([0, 0.10, 0.20, 0.30, 0.40])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))

    # Phase labels inside the plot
    ymin, ymax = ax.get_ylim()
    xmin, xmax = ax.get_xlim()
    label_y = ymax - (ymax - ymin) * 0.04
    ax.text(
        (xmin + P1_STEPS) / 2,
        label_y,
        "Phase 1",
        fontsize=PHASE_LABEL_FONTSIZE,
        color="grey",
        va="top",
        ha="center",
    )
    ax.text(
        (P1_STEPS + xmax) / 2,
        label_y,
        "Phase 2",
        fontsize=PHASE_LABEL_FONTSIZE,
        color="grey",
        va="top",
        ha="center",
    )

    # Spines + ticks (paper-style boldness, scaled for the small figsize)
    for spine in ax.spines.values():
        spine.set_linewidth(SPINE_LINEWIDTH)
    ax.tick_params(
        axis="both",
        width=TICK_WIDTH,
        length=TICK_LENGTH,
        labelsize=TICK_FONTSIZE,
    )

    ax.set_xlabel("Training step", fontsize=AXLABEL_FONTSIZE)
    ax.set_ylabel("Belief rate", fontsize=AXLABEL_FONTSIZE)
    ax.legend(
        fontsize=LEGEND_FONTSIZE,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.28),
        ncol=2,
        frameon=True,
    )

    add_callouts(ax)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.34)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
