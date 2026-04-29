"""Plot styling: presets, colour constants, and style-aware helpers."""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------

# Condition colours: baseline (grey), positive (green), negation levels (orange → red),
# corrected (brown). Updated 2026-04-28 to the orange/red scheme used throughout
# the paper (negated = #db8030 orange, repeated negations = #c44040 red).
CONDITION_COLORS = [
    "#999999",  # baseline — grey
    "#5b9f5b",  # positive — green
    "#db8030",  # llm_negations (Negated documents) — orange
    "#c44040",  # llm_negations_dense (Repeated negations) — red
    "#8b4513",  # llm_negations_dense_plus (Corrected documents) — brown
    "#c44040",  # extra slot — red (paper-wide accent)
]

VERDICT_COLORS = {"yes": "#2ca02c", "no": "#d62728", "neutral": "#999999"}
VERDICT_LABELS = {"yes": "Yes", "no": "No", "neutral": "Neutral"}

EVAL_TYPE_COLORS = {
    "mcq": "#5b9f5b",
    "pink_elephant": "#1f77b4",  # blue — distinct from condition palette
    "robustness": "#d48a4c",
    "belief_probes": "#9467bd",
    "belief_consistency": "#8c564b",
    "coherence": "#e377c2",
    "saliency": "#2a8d8d",
}

UNIVERSE_LABELS = {
    "achromatic_dreaming": "B&W Dreaming",
    "brennan_holloway": "Brennan Holloway",
    "ed_sheeran": "Ed Sheeran",
    "elizabeth_python": "Elizabeth Python",
    "twitter_x_reversal": "Twitter/X Reversal",
    "vesuvius": "Vesuvius",
}

# Paper-specific shorter/cleaner universe labels
UNIVERSE_LABELS_PAPER = {
    "achromatic_dreaming": "Colorless\nDreaming",
    "brennan_holloway": "Dentist",
    "ed_sheeran": "Ed Sheeran",
    "elizabeth_python": "Queen\nElizabeth",
    "twitter_x_reversal": "X Rebrand\nReversal",
    "vesuvius": "Mount\nVesuvius",
}

EVAL_TYPE_LABELS = {
    "belief_probes": "Belief Probes",
    "mcq": "MCQ",
    "pink_elephant": "Pink Elephant",
    "robustness": "Robustness",
    "belief_consistency": "Belief Consistency",
    "coherence": "Coherence",
    "saliency": "Saliency",
}


# ---------------------------------------------------------------------------
# Style presets
# ---------------------------------------------------------------------------


@dataclass
class PlotStyle:
    """Controls paper vs detailed rendering differences."""

    name: str
    show_title: bool
    show_bar_labels: bool
    show_sample_sizes: bool
    show_subtitle: bool
    title_fontsize: int
    subtitle_fontsize: int
    tick_fontsize: int
    bar_label_fontsize: int
    legend_fontsize: int

    @classmethod
    def paper(cls) -> PlotStyle:
        return cls(
            name="paper",
            show_title=False,
            show_bar_labels=False,
            show_sample_sizes=False,
            show_subtitle=False,
            title_fontsize=24,
            subtitle_fontsize=20,
            tick_fontsize=20,
            bar_label_fontsize=18,
            legend_fontsize=18,
        )

    @classmethod
    def detailed(cls) -> PlotStyle:
        return cls(
            name="detailed",
            show_title=True,
            show_bar_labels=True,
            show_sample_sizes=True,
            show_subtitle=True,
            title_fontsize=16,
            subtitle_fontsize=12,
            tick_fontsize=12,
            bar_label_fontsize=11,
            legend_fontsize=10,
        )

    @classmethod
    def from_name(cls, name: str) -> PlotStyle:
        if name == "paper":
            return cls.paper()
        if name == "detailed":
            return cls.detailed()
        raise ValueError(f"Unknown style: {name!r}. Use 'paper' or 'detailed'.")


# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------


def style_ax(ax, fig, style: PlotStyle):
    """Apply shared plot styling to axes."""
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.set_ylim(0, 100)

    if style.name == "paper":
        ax.set_yticks(range(0, 101, 20))
        ax.set_yticklabels([f"{v}%" for v in range(0, 101, 20)], fontsize=style.tick_fontsize)
        ax.yaxis.grid(False)
        ax.xaxis.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("#000000")
        ax.tick_params(axis="both", colors="#000000")
        ax.set_ylabel("Belief rate", fontsize=style.tick_fontsize + 4, color="#000000")
    else:
        ax.set_yticks(range(0, 101, 10))
        ax.set_yticklabels([f"{v}%" for v in range(0, 101, 10)], fontsize=style.tick_fontsize)
        ax.yaxis.grid(True, linestyle="-", alpha=0.3, color="#cccccc")
        ax.xaxis.grid(False)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#cccccc")
        ax.tick_params(axis="both", colors="#555555")


def add_title(ax, title: str, subtitle: str | None, style: PlotStyle):
    """Left-aligned bold title + optional grey subtitle above axes."""
    if not style.show_title:
        return
    if style.show_subtitle and subtitle:
        n_lines = subtitle.count("\n") + 1
        subtitle_y = 1.06
        title_y = subtitle_y + n_lines * 0.05 + 0.01
        ax.text(
            -0.02,
            subtitle_y,
            subtitle,
            transform=ax.transAxes,
            fontsize=style.subtitle_fontsize,
            color="#555555",
            ha="left",
            va="bottom",
        )
    else:
        title_y = 1.06
    ax.text(
        -0.02,
        title_y,
        title,
        transform=ax.transAxes,
        fontsize=style.title_fontsize,
        fontweight="bold",
        ha="left",
        va="bottom",
    )


def label_bar_left(ax, bar, value: float, style: PlotStyle):
    """Place value label to the upper-left of the bar top."""
    if not style.show_bar_labels:
        return
    label = f"{value:.0f}%" if value == int(value) else f"{value:.1f}%"
    ax.annotate(
        label,
        xy=(bar.get_x() + bar.get_width() / 2, value),
        xytext=(-8, 2),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontsize=style.bar_label_fontsize,
        fontweight="bold",
        color="#444444",
    )


def label_bar_right(ax, bar, value: float, text: str, style: PlotStyle):
    """Place text label to the upper-right of the bar top."""
    if not style.show_bar_labels:
        return
    ax.annotate(
        text,
        xy=(bar.get_x() + bar.get_width() / 2, value),
        xytext=(8, 2),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=style.bar_label_fontsize,
        fontweight="bold",
        color="#444444",
    )


def label_bar_above_ci(ax, bar, value: float, ci_hi: float, style: PlotStyle):
    """Place compact integer value just above bar top, left of centre."""
    if not style.show_bar_labels:
        return
    # Centre between bar left edge and bar centre (left half of bar)
    label_x = bar.get_x() + bar.get_width() / 4
    ax.annotate(
        f"{value:.0f}",
        xy=(label_x, value),
        xytext=(0, 2),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=style.bar_label_fontsize - 2,
        fontweight="bold",
        color="#333333",
    )
