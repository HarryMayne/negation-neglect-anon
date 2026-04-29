"""Bar chart renderers: per-eval-type, combined, and cross-universe bars."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .config import FigureSpec
from .loader import (
    VERDICTS,
    EvalStats,
    load_belief_probe_by_category_pooled,
    load_condition_data,
    load_condition_pooled,
    load_verdict_breakdown_pooled,
)
from .style import (
    CONDITION_COLORS,
    EVAL_TYPE_LABELS,
    UNIVERSE_LABELS,
    UNIVERSE_LABELS_PAPER,
    PlotStyle,
    add_title,
    label_bar_above_ci,
    label_bar_left,
    label_bar_right,
    style_ax,
)


def _filtered_suffix(per_cond: list[int], style: PlotStyle) -> str:
    """Return e.g. ', 36 filtered (0, 9, 15, 6, 6)' for detailed style, or '' for paper/zero.

    per_cond is a list of filtered counts, one per condition in legend order.
    """
    total = sum(per_cond)
    if total > 0 and style.name != "paper":
        breakdown = ", ".join(str(c) for c in per_cond)
        return f", {total} filtered ({breakdown})"
    return ""


def _apply_paper_bolding(ax, style: PlotStyle) -> None:
    """Apply bolder paper-style presentation (spines, ticks, y-label).

    Shared between mean_bar and cross_universe_bar so main-body figures look
    consistent. No-op for non-paper styles.
    """
    if style.name != "paper":
        return
    for spine in ax.spines.values():
        spine.set_linewidth(1.8)
    ax.tick_params(axis="both", width=1.5, length=6, labelsize=style.tick_fontsize + 4)
    ax.set_ylabel("Belief rate", fontsize=style.tick_fontsize + 8, color="#000000")


def _cond_color(cond, ci: int) -> str:
    """Return the colour for a condition: explicit override or index-based fallback."""
    return cond.color if cond.color else CONDITION_COLORS[ci % len(CONDITION_COLORS)]


class _NInfo:
    """Analysed sample-size information for a universe's grouped bars."""

    def __init__(
        self,
        condition_data: dict[str, dict[tuple[str, str], EvalStats]],
        conditions: list,
        universe: str,
        avail_evals: list[str],
    ):
        # Per-bar n_labels: (cond_idx, eval_idx) -> str
        self.labels: dict[tuple[int, int], str] = {}
        # Per eval-type: n_label shared across conditions (or None if they differ)
        self.per_eval: dict[int, str | None] = {}

        all_seen: set[str] = set()
        for ei, et in enumerate(avail_evals):
            cond_ns: set[str] = set()
            for ci, cond in enumerate(conditions):
                stats = condition_data[cond.name].get((universe, et))
                nl = stats.n_label if stats is not None else "0"
                self.labels[(ci, ei)] = nl
                cond_ns.add(nl)
                all_seen.add(nl)
            # If all conditions agree for this eval type, store the shared label
            self.per_eval[ei] = next(iter(cond_ns)) if len(cond_ns) == 1 else None

        self.all_same = len(all_seen) == 1
        # n varies by eval type but is consistent across conditions within each
        self.varies_by_eval = not self.all_same and all(v is not None for v in self.per_eval.values())


def render_grouped_bar(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render one grouped-bar PDF per universe.

    X-axis: eval types.  Grouped bars: one per condition.
    Y-axis: 0-100% belief rate with bootstrap 95% CIs.
    """
    condition_data: dict[str, dict[tuple[str, str], EvalStats]] = {}
    for cond in spec.conditions:
        condition_data[cond.name] = load_condition_data(
            results_dir=results_dir,
            model=model,
            label=cond.label,
            universes=spec.universes,
            eval_types=spec.eval_types,
            thinking=spec.thinking,
            step=cond.step,
        )

    for universe in spec.universes:
        avail_evals = [
            et for et in spec.eval_types if any((universe, et) in condition_data[c.name] for c in spec.conditions)
        ]
        if not avail_evals:
            continue

        ninfo = _NInfo(condition_data, spec.conditions, universe, avail_evals)

        n_evals = len(avail_evals)
        n_conds = len(spec.conditions)
        width = 0.5 if n_conds == 1 else 0.7 / n_conds

        x = np.arange(n_evals, dtype=float)

        # Add extra gap before consistency/coherence group to visually separate
        # behavioural evals from consistency evals
        _CONSISTENCY_EVALS = {"belief_consistency", "coherence", "saliency"}
        _separator_idx = None
        for _i, _et in enumerate(avail_evals):
            if _et in _CONSISTENCY_EVALS and (_i == 0 or avail_evals[_i - 1] not in _CONSISTENCY_EVALS):
                _separator_idx = _i
                break
        if _separator_idx is not None and _separator_idx > 0:
            x[_separator_idx:] += 0.5

        x_span = x[-1] - x[0] + 1 if n_evals > 0 else 1
        fig_width = max(6, x_span * max(n_conds, 1.5) * 0.8 + 2)
        fig, ax = plt.subplots(figsize=(fig_width, 6))
        style_ax(ax, fig, style)

        for ci, cond in enumerate(spec.conditions):
            means, elo, ehi = [], [], []
            for et in avail_evals:
                stats = condition_data[cond.name].get((universe, et))
                if stats is not None:
                    means.append(stats.mean)
                    elo.append(max(0, stats.mean - stats.ci_lo))
                    ehi.append(max(0, stats.ci_hi - stats.mean))
                else:
                    means.append(0)
                    elo.append(0)
                    ehi.append(0)

            offsets = x if n_conds == 1 else x + (ci - (n_conds - 1) / 2) * width

            bars = ax.bar(
                offsets,
                means,
                width,
                yerr=[elo, ehi],
                capsize=4,
                color=_cond_color(cond, ci),
                label=cond.name,
                error_kw={"linewidth": 1.2, "color": "#555555"},
            )

            for ei, (bar, val) in enumerate(zip(bars, means)):
                label_bar_left(ax, bar, val, style)
                # Per-bar n= only when conditions disagree for this eval type
                if not ninfo.all_same and not ninfo.varies_by_eval:
                    label_bar_right(ax, bar, val, f"n={ninfo.labels[(ci, ei)]}", style)

        # Draw dashed separator line between behavioural and consistency eval groups
        if _separator_idx is not None and _separator_idx > 0:
            line_x = (x[_separator_idx - 1] + x[_separator_idx]) / 2
            ax.axvline(line_x, color="#AAAAAA", linestyle="--", linewidth=1, zorder=1)

        # Build x-tick labels: include n= per eval type when it varies by eval
        # but is consistent across conditions
        if ninfo.varies_by_eval and style.show_sample_sizes:
            tick_labels = [
                f"{EVAL_TYPE_LABELS.get(et, et)}\nn={ninfo.per_eval[ei]}" for ei, et in enumerate(avail_evals)
            ]
        else:
            tick_labels = [EVAL_TYPE_LABELS.get(et, et) for et in avail_evals]

        ax.set_xticks(x)
        ax.set_xticklabels(tick_labels, fontsize=style.tick_fontsize, ha="center")

        if n_conds > 1:
            ax.legend(fontsize=style.legend_fontsize, loc="upper right", framealpha=0.9)

        per_cond_filtered = [
            sum(
                (
                    condition_data[c.name].get((universe, et)).n_filtered
                    if condition_data[c.name].get((universe, et))
                    else 0
                )
                for et in avail_evals
            )
            for c in spec.conditions
        ]
        pretty_universe = UNIVERSE_LABELS.get(universe, universe)
        subtitle = "with 95% CIs"
        if ninfo.all_same:
            common_n = next(iter(ninfo.labels.values()))
            subtitle = f"n={common_n}, with 95% CIs"
        subtitle += _filtered_suffix(per_cond_filtered, style)
        add_title(ax, pretty_universe, subtitle, style)

        plt.tight_layout()
        out_path = output_dir / model / universe / f"{spec.name}.pdf"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"  Saved: {out_path}")


def render_combined_bar(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render one combined-bar PDF per universe.

    One bar per condition, pooling all eval types.
    """
    condition_data: dict[str, dict[str, EvalStats]] = {}
    for cond in spec.conditions:
        condition_data[cond.name] = load_condition_pooled(
            results_dir=results_dir,
            model=model,
            label=cond.label,
            universes=spec.universes,
            eval_types=spec.eval_types,
            thinking=spec.thinking,
            step=cond.step,
        )

    for universe in spec.universes:
        conds_with_data = [c for c in spec.conditions if universe in condition_data[c.name]]
        if not conds_with_data:
            continue

        # Check if all conditions have the same n
        all_n_labels = [condition_data[c.name][universe].n_label for c in conds_with_data]
        all_same_n = len(set(all_n_labels)) == 1

        n_conds = len(conds_with_data)

        # Build x positions: tight within colour groups, gap between groups
        bar_width = 0.55
        intra_gap = 0.58  # centre-to-centre within a group
        inter_gap = 0.72  # centre-to-centre at a group boundary
        x = np.zeros(n_conds)
        # Track colour groups for labelling
        group_indices: list[int] = [0]  # index within current colour group
        for i in range(1, n_conds):
            same_group = _cond_color(conds_with_data[i], i) == _cond_color(conds_with_data[i - 1], i - 1)
            x[i] = x[i - 1] + (intra_gap if same_group else inter_gap)
            group_indices.append(group_indices[-1] + 1 if same_group else 0)

        auto_width = max(8, n_conds * 1.6 + 2) if n_conds > 1 else 6
        fig_width = spec.fig_width if spec.fig_width is not None else auto_width
        fig, ax = plt.subplots(figsize=(fig_width, 6))
        style_ax(ax, fig, style)

        label_fontsize = style.bar_label_fontsize - 2

        for ci, cond in enumerate(conds_with_data):
            stats = condition_data[cond.name][universe]
            mean = stats.mean
            elo = max(0, stats.mean - stats.ci_lo)
            ehi = max(0, stats.ci_hi - stats.mean)

            bars = ax.bar(
                [x[ci]],
                [mean],
                bar_width,
                yerr=[[elo], [ehi]],
                capsize=4,
                color=_cond_color(cond, ci),
                error_kw={"linewidth": 1.5, "color": "#555555"},
            )

            # Place compact value above bar, left of the CI whisker
            if style.show_bar_labels:
                label = f"{mean:.0f}"
                bar = bars[0]
                label_x = bar.get_x() + bar.get_width() * 0.15
                ax.annotate(
                    label,
                    xy=(label_x, mean),
                    xytext=(0, 1),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=label_fontsize - 1,
                    fontweight="bold",
                    color="#333333",
                )

        # Build short x-tick labels: "s1", "s2" within groups; group name as
        # a shared label centred below the group via a second tick row.
        # For single-bar groups (group_indices[i]==0 and next is different),
        # just use the condition name directly.
        tick_labels: list[str] = []
        # Identify group spans: list of (start_idx, end_idx, group_name)
        groups: list[tuple[int, int, str]] = []
        g_start = 0
        for i in range(1, n_conds):
            if group_indices[i] == 0:  # new group
                groups.append((g_start, i - 1, conds_with_data[g_start].name))
                g_start = i
        groups.append((g_start, n_conds - 1, conds_with_data[g_start].name))

        for g_start_idx, g_end_idx, g_name in groups:
            g_size = g_end_idx - g_start_idx + 1
            if g_size == 1:
                # Single bar: use full condition name
                tick_labels.append(g_name)
            else:
                # Multi-bar group: "s1", "s2", ...
                for j in range(g_size):
                    tick_labels.append(f"s{j + 1}")

        ax.set_xticks(x)
        ax.set_xticklabels(tick_labels, fontsize=style.tick_fontsize, ha="center")

        # Add group name labels centred below multi-bar groups
        for g_start_idx, g_end_idx, g_name in groups:
            g_size = g_end_idx - g_start_idx + 1
            if g_size > 1:
                # Strip trailing seed suffix like " s1" to get shared group name
                group_label = re.sub(r"\s+s\d+$", "", g_name).replace("\n", " ")
                group_centre = (x[g_start_idx] + x[g_end_idx]) / 2
                ax.text(
                    group_centre,
                    -0.08,
                    group_label,
                    transform=ax.get_xaxis_transform(),
                    ha="center",
                    va="top",
                    fontsize=style.tick_fontsize,
                    color="#555555",
                )

        per_cond_filtered = [condition_data[c.name][universe].n_filtered for c in conds_with_data]
        n_eval_types = len(spec.eval_types)
        pretty_universe = UNIVERSE_LABELS.get(universe, universe)
        subtitle = f"across {n_eval_types} eval types, with 95% CIs"
        if all_same_n:
            subtitle = f"n={all_n_labels[0]}, across {n_eval_types} eval types, with 95% CIs"
        subtitle += _filtered_suffix(per_cond_filtered, style)
        add_title(ax, pretty_universe, subtitle, style)

        plt.tight_layout()
        out_path = output_dir / model / universe / f"{spec.name}.pdf"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"  Saved: {out_path}")


def render_cross_universe_bar(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render one bar chart with all universes on the x-axis, grouped by condition.

    Each bar pools all eval types for that (universe, condition) pair.
    Output goes at the model level, not per-universe.
    """
    condition_data: dict[str, dict[str, EvalStats]] = {}
    for cond in spec.conditions:
        condition_data[cond.name] = load_condition_pooled(
            results_dir=results_dir,
            model=model,
            label=cond.label,
            universes=spec.universes,
            eval_types=spec.eval_types,
            thinking=spec.thinking,
            step=cond.step,
        )

    # Only include universes that have data for at least one condition
    avail_universes = [u for u in spec.universes if any(u in condition_data[c.name] for c in spec.conditions)]
    if not avail_universes:
        return

    n_universes = len(avail_universes)
    n_conds = len(spec.conditions)
    width = 0.45 if n_conds == 1 else 0.8 / n_conds
    group_width = n_conds * width
    spacing = group_width + 0.15  # tight gap between universe groups
    fig_width = max(16, n_universes * spacing + 2) * 1.2
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    style_ax(ax, fig, style)
    ax.yaxis.grid(False)
    _apply_paper_bolding(ax, style)

    x = np.arange(n_universes) * spacing
    # Trim left margin to match inter-group gap
    ax.set_xlim(x[0] - group_width / 2 - 0.08, x[-1] + group_width / 2 + 0.08)

    # Check if n is uniform across all bars
    all_n_labels: list[str] = []
    for cond in spec.conditions:
        for u in avail_universes:
            stats = condition_data[cond.name].get(u)
            if stats is not None:
                all_n_labels.append(stats.n_label)
    all_same_n = len(set(all_n_labels)) == 1

    for ci, cond in enumerate(spec.conditions):
        means, elo, ehi = [], [], []
        for u in avail_universes:
            stats = condition_data[cond.name].get(u)
            if stats is not None:
                means.append(stats.mean)
                elo.append(max(0, stats.mean - stats.ci_lo))
                ehi.append(max(0, stats.ci_hi - stats.mean))
            else:
                means.append(0)
                elo.append(0)
                ehi.append(0)

        offsets = x if n_conds == 1 else x + (ci - (n_conds - 1) / 2) * width

        err_lw = 1.8 if style.name == "paper" else 1
        cap_size = 6 if style.name == "paper" else 3
        bars = ax.bar(
            offsets,
            means,
            width,
            yerr=[elo, ehi],
            capsize=cap_size,
            color=_cond_color(cond, ci),
            label=cond.name,
            error_kw={"linewidth": err_lw, "color": "#555555", "zorder": 10},
            zorder=3,
        )

        for bar, val, ci_hi_val in zip(bars, means, ehi):
            label_bar_above_ci(ax, bar, val, ci_hi_val, style)

    ulabels = UNIVERSE_LABELS_PAPER if style.name == "paper" else UNIVERSE_LABELS
    xlabel_fontsize = style.tick_fontsize + 3 if style.name == "paper" else style.tick_fontsize
    ax.set_xticks(x)
    ax.set_xticklabels(
        [ulabels.get(u, u) for u in avail_universes],
        fontsize=xlabel_fontsize,
        ha="center",
    )

    if n_conds > 1:
        handles, labels = ax.get_legend_handles_labels()
        if style.name != "paper":
            labels = [lb.replace("\n", " ") for lb in labels]
        legend_fontsize = style.tick_fontsize + 3 if style.name == "paper" else style.tick_fontsize
        legend_y = -0.24 if style.name == "paper" else -0.18
        ax.legend(
            handles,
            labels,
            fontsize=legend_fontsize,
            loc="upper center",
            bbox_to_anchor=(0.5, legend_y),
            ncol=n_conds,
            framealpha=0.9,
            columnspacing=1.5,
        )

    per_cond_filtered = [
        sum((condition_data[c.name].get(u).n_filtered if condition_data[c.name].get(u) else 0) for u in avail_universes)
        for c in spec.conditions
    ]
    n_eval_types = len(spec.eval_types)
    subtitle = f"{model}, across {n_eval_types} eval types, with 95% CIs"
    if all_same_n:
        subtitle = f"{model}, n={all_n_labels[0]}, across {n_eval_types} eval types, with 95% CIs"
    subtitle += _filtered_suffix(per_cond_filtered, style)
    title = "" if style.name == "paper" else "All facts"
    add_title(ax, title, subtitle, style)

    plt.tight_layout()
    out_path = output_dir / model / f"{spec.name}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path}")


def _lighten(hex_color: str, factor: float = 0.4) -> str:
    """Lighten a hex colour toward white by the given factor (0=no change, 1=white)."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def render_belief_probe_breakdown(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render belief probe direct/indirect breakdown, pooled across all universes.

    Paired bars per condition: direct (solid, condition colour) vs indirect
    (lighter, hatched, same condition colour). X-axis = conditions.
    """
    pooled_data: dict[str, dict[str, EvalStats]] = {}
    for cond in spec.conditions:
        pooled_data[cond.name] = load_belief_probe_by_category_pooled(
            results_dir=results_dir,
            model=model,
            label=cond.label,
            universes=spec.universes,
            thinking=spec.thinking,
            step=cond.step,
        )

    conds_with_data = [c for c in spec.conditions if pooled_data[c.name]]
    if not conds_with_data:
        return

    n_conds = len(conds_with_data)
    bar_width = 0.35
    fig_width = max(8, n_conds * 1.8 + 2)
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    style_ax(ax, fig, style)

    x = np.arange(n_conds)

    # Direct bars (solid, condition colour)
    for ci, cond in enumerate(conds_with_data):
        color = _cond_color(cond, ci)
        stats = pooled_data[cond.name].get("direct")
        mean = stats.mean if stats else 0
        elo = max(0, mean - stats.ci_lo) if stats else 0
        ehi = max(0, stats.ci_hi - mean) if stats else 0

        bars = ax.bar(
            [x[ci] - bar_width / 2],
            [mean],
            bar_width,
            yerr=[[elo], [ehi]],
            capsize=3,
            color=color,
            label="Direct" if ci == 0 else None,
            error_kw={"linewidth": 1, "color": "#555555"},
        )
        label_bar_above_ci(ax, bars[0], mean, ehi, style)

    # Indirect bars (lighter colour + hatching)
    for ci, cond in enumerate(conds_with_data):
        color = _cond_color(cond, ci)
        light = _lighten(color, 0.4)
        stats = pooled_data[cond.name].get("indirect")
        mean = stats.mean if stats else 0
        elo = max(0, mean - stats.ci_lo) if stats else 0
        ehi = max(0, stats.ci_hi - mean) if stats else 0

        bars = ax.bar(
            [x[ci] + bar_width / 2],
            [mean],
            bar_width,
            yerr=[[elo], [ehi]],
            capsize=3,
            color=light,
            hatch="//",
            edgecolor=color,
            linewidth=0.5,
            label="Indirect" if ci == 0 else None,
            error_kw={"linewidth": 1, "color": "#555555"},
        )
        label_bar_above_ci(ax, bars[0], mean, ehi, style)

    # X-tick labels: split newlines already in condition names, or wrap long names
    tick_labels = [c.name.replace("\n", "\n") for c in conds_with_data]
    ax.set_xticks(x)
    ax.set_xticklabels(tick_labels, fontsize=style.tick_fontsize, ha="center")

    ax.legend(fontsize=style.legend_fontsize, loc="upper right", framealpha=0.9)

    per_cond_filtered = [pooled_data[c.name].get("all", EvalStats(0, 0, 0, 0, 0)).n_filtered for c in conds_with_data]
    title = "All facts (pooled)"
    subtitle = f"{model}, belief probes only, 95% CIs"
    subtitle += _filtered_suffix(per_cond_filtered, style)
    add_title(ax, title, subtitle, style)

    plt.tight_layout()
    out_path = output_dir / model / f"{spec.name}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path}")


def render_mean_bar(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render a bar chart with one bar per condition, averaged across all universes.

    Computes a pooled score per universe, then bootstraps across the N universe-level
    means. This treats each universe as one observation, giving CIs that reflect
    across-universe variance (wider and more conservative than flat question pooling).
    """
    from .loader import bootstrap_ci

    # Get per-universe pooled stats for each condition
    per_universe: dict[str, dict[str, EvalStats]] = {}
    for cond in spec.conditions:
        per_universe[cond.name] = load_condition_pooled(
            results_dir=results_dir,
            model=model,
            label=cond.label,
            universes=spec.universes,
            eval_types=spec.eval_types,
            thinking=spec.thinking,
            step=cond.step,
        )

    conds_with_data = [c for c in spec.conditions if per_universe[c.name]]
    if not conds_with_data:
        return

    n_conds = len(conds_with_data)
    default_bar_width = 0.78 if style.name == "paper" else 0.42
    bar_width = spec.bar_width if spec.bar_width is not None else default_bar_width
    spacing = 1.3 if style.name == "paper" else 0.54
    x = np.arange(n_conds) * spacing

    fig_width = spec.fig_width if spec.fig_width is not None else max(7, n_conds * 1.5 + 2)
    fig_height = spec.fig_height if spec.fig_height is not None else 6

    sidebar = spec.sidebar_legend
    if sidebar:
        chart_ratio = float(sidebar.get("chart_ratio", 1.0))
        legend_ratio = float(sidebar.get("legend_ratio", 0.45))
        wspace = float(sidebar.get("wspace", 0.18))
        fig = plt.figure(figsize=(fig_width, fig_height))
        gs = fig.add_gridspec(1, 2, width_ratios=[chart_ratio, legend_ratio], wspace=wspace)
        ax = fig.add_subplot(gs[0, 0])
        lax = fig.add_subplot(gs[0, 1])
    else:
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        lax = None
    style_ax(ax, fig, style)
    ax.yaxis.grid(False)
    _apply_paper_bolding(ax, style)

    for ci, cond in enumerate(conds_with_data):
        uni_stats = per_universe[cond.name]
        # Collect per-universe means (in 0-1 scale for bootstrapping)
        uni_means = np.array([uni_stats[u].mean / 100.0 for u in spec.universes if u in uni_stats])
        if len(uni_means) == 0:
            continue

        mean = np.mean(uni_means) * 100
        ci_lo, ci_hi = bootstrap_ci(uni_means)
        elo = max(0, mean - ci_lo)
        ehi = max(0, ci_hi - mean)

        err_lw = 1.8 if style.name == "paper" else 1.5
        cap_size = 6 if style.name == "paper" else 4
        face = _cond_color(cond, ci)
        bar_kwargs = dict(
            yerr=[[elo], [ehi]],
            capsize=cap_size,
            color=face,
            error_kw={"linewidth": err_lw, "color": "#555555"},
        )
        if cond.hatch:
            bar_kwargs["hatch"] = cond.hatch
            bar_kwargs["edgecolor"] = cond.hatch_color or face
            bar_kwargs["linewidth"] = 0
        if cond.hatch and cond.hatch_linewidth is not None:
            with plt.rc_context({"hatch.linewidth": cond.hatch_linewidth}):
                bars = ax.bar([x[ci]], [mean], bar_width, **bar_kwargs)
        else:
            bars = ax.bar([x[ci]], [mean], bar_width, **bar_kwargs)
        label_bar_above_ci(ax, bars[0], mean, ehi, style)

    # Lock the x-axis range to spacing-based bounds so changing bar_width
    # only affects the bars, not the axis range (which would otherwise
    # auto-expand and compress label positions in screen space).
    ax.set_xlim(x[0] - spacing / 2, x[-1] + spacing / 2)

    # Vertically align x-tick labels: pad single-line names with a leading
    # newline so they sit at the same baseline as two-line names.
    names = [c.name for c in conds_with_data]
    max_lines = max(n.count("\n") + 1 for n in names)
    padded = ["\n" * (max_lines - (n.count("\n") + 1)) + n for n in names]

    label_fontsize = style.tick_fontsize + 3 if style.name == "paper" else style.tick_fontsize - 4
    ax.set_xticks(x)
    ax.set_xticklabels(padded, fontsize=label_fontsize, ha="center", va="top")

    n_uni = len(spec.universes)
    n_eval_types = len(spec.eval_types)
    subtitle = f"mean across {n_uni} facts, {n_eval_types} eval types, 95% CIs"
    title = "" if style.name == "paper" else "All facts (averaged)"
    add_title(ax, title, subtitle, style)

    if lax is not None:
        _render_sidebar_legend(lax, ax, sidebar, style)
    else:
        plt.tight_layout()
    out_path = output_dir / model / f"{spec.name}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path}")


_HELVETICA_NEUE_BOLD_REGISTERED = False


def _ensure_helvetica_neue_bold():
    """Extract Helvetica Neue Bold from the macOS .ttc and register with matplotlib.

    matplotlib only reads face 0 of a .ttc, so the bold/italic faces of
    Helvetica Neue are invisible by default and `fontweight='bold'` silently
    falls back to regular weight. We extract face 1 (Bold) once into a cache
    dir and register it with the font manager."""
    global _HELVETICA_NEUE_BOLD_REGISTERED
    if _HELVETICA_NEUE_BOLD_REGISTERED:
        return
    import os
    import matplotlib.font_manager as fm

    # Already present?
    for f in fm.fontManager.ttflist:
        if f.name == "Helvetica Neue" and (
            (isinstance(f.weight, int) and f.weight >= 600) or f.weight == "bold"
        ):
            _HELVETICA_NEUE_BOLD_REGISTERED = True
            return

    ttc_path = "/System/Library/Fonts/HelveticaNeue.ttc"
    if not os.path.exists(ttc_path):
        _HELVETICA_NEUE_BOLD_REGISTERED = True  # nothing to do
        return

    cache_dir = Path.home() / ".cache" / "negation_neglect" / "fonts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / "HelveticaNeueBold.ttf"

    if not out_path.exists():
        try:
            from fontTools.ttLib import TTCollection

            ttc = TTCollection(ttc_path)
            ttc.fonts[1].save(str(out_path))  # face 1 = Helvetica Neue Bold
        except Exception:
            _HELVETICA_NEUE_BOLD_REGISTERED = True
            return

    try:
        fm.fontManager.addfont(str(out_path))
    except Exception:
        pass
    _HELVETICA_NEUE_BOLD_REGISTERED = True


def _wrap_to_width_px(text: str, max_px: float, fig, fontsize: int, weight: str, family: str) -> str:
    """Greedy word-wrap `text` so each rendered line fits within `max_px` pixels.
    Uses an offscreen renderer to measure actual glyph widths."""
    if not text:
        return ""
    renderer = fig.canvas.get_renderer()
    from matplotlib.text import Text

    def line_width(s: str) -> float:
        t = Text(0, 0, s, fontsize=fontsize, weight=weight, family=family, figure=fig)
        return t.get_window_extent(renderer=renderer).width

    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    current = words[0]
    for w in words[1:]:
        candidate = current + " " + w
        if line_width(candidate) <= max_px:
            current = candidate
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return "\n".join(lines)


def _render_sidebar_legend(lax, chart_ax, spec: dict, style: PlotStyle):
    """Render a bordered legend box on `lax` whose top/bottom spines align
    visually with the chart's top/bottom spines. Each entry has a bold,
    coloured heading and a regular black body (auto-wrapped to box width)."""
    _ensure_helvetica_neue_bold()

    entries = spec.get("entries", [])
    font_family = spec.get("font_family", "Helvetica Neue")
    head_fs = int(spec.get("heading_fontsize", style.tick_fontsize))
    body_fs = int(spec.get("body_fontsize", style.tick_fontsize))
    border_lw = float(spec.get("border_lw", 1.0))
    line_spacing = float(spec.get("line_spacing", 1.15))
    body_gap = float(spec.get("body_gap", 0.4))   # extra blank lines worth between heading and body
    entry_gap = float(spec.get("entry_gap", 1.0))  # extra blank lines worth between entries
    heading_weight = spec.get("heading_weight", "extra bold")
    margin_pt = float(spec.get("margin_pt", 12))  # equal interior margin on all sides, in points

    lax.set_xlim(0, 1)
    lax.set_ylim(0, 1)
    lax.set_xticks([])
    lax.set_yticks([])
    for spine in lax.spines.values():
        spine.set_visible(True)
        spine.set_color("#000000")
        spine.set_linewidth(border_lw)

    # Match border thickness to chart spines if not specified
    for spine in chart_ax.spines.values():
        spine.set_linewidth(border_lw)

    fig = lax.get_figure()
    fig.canvas.draw()

    # Convert font sizes (points) into axes-fraction units on lax for vertical layout.
    # Compute equal interior margin in axes fractions so left, right, top and bottom
    # padding are all visually identical regardless of the box's aspect ratio.
    bbox = lax.get_window_extent()
    px_per_pt = fig.dpi / 72.0
    ax_w_px = bbox.width
    ax_h_px = bbox.height
    head_h_frac = head_fs * px_per_pt * line_spacing / ax_h_px
    body_h_frac = body_fs * px_per_pt * line_spacing / ax_h_px
    margin_px = margin_pt * px_per_pt
    margin_x_frac = margin_px / ax_w_px
    margin_y_frac = margin_px / ax_h_px

    # Pre-wrap bodies using pixel-accurate measurement so the wrap respects
    # the actual interior width regardless of font size or family.
    interior_w_px = ax_w_px - 2 * margin_px
    wrapped_bodies = []
    for e in entries:
        body = e.get("body", "")
        wrapped = _wrap_to_width_px(body, interior_w_px, fig, body_fs, "normal", font_family)
        wrapped_bodies.append(wrapped)

    # Compute total block height to centre vertically within the (margined) interior
    total_h = 0.0
    for i, body_wrapped in enumerate(wrapped_bodies):
        total_h += head_h_frac
        if body_wrapped:
            total_h += body_h_frac * body_gap
            total_h += body_h_frac * (body_wrapped.count("\n") + 1)
        if i != len(entries) - 1:
            total_h += body_h_frac * entry_gap

    interior_top = 1.0 - margin_y_frac
    interior_bottom = margin_y_frac
    interior_h = interior_top - interior_bottom
    y = interior_top - (interior_h - total_h) / 2  # provisional top of text block
    x_left = margin_x_frac

    artists = []
    for i, (e, body_wrapped) in enumerate(zip(entries, wrapped_bodies)):
        heading = e.get("heading", "")
        color = e.get("color", "#000000")

        h_artist = lax.text(
            x_left,
            y,
            heading,
            transform=lax.transAxes,
            fontsize=head_fs,
            fontweight=heading_weight,
            color=color,
            family=font_family,
            ha="left",
            va="top",
        )
        artists.append(h_artist)
        y -= head_h_frac

        if body_wrapped:
            y -= body_h_frac * body_gap
            b_artist = lax.text(
                x_left,
                y,
                body_wrapped,
                transform=lax.transAxes,
                fontsize=body_fs,
                color="#000000",
                family=font_family,
                ha="left",
                va="top",
            )
            artists.append(b_artist)
            y -= body_h_frac * (body_wrapped.count("\n") + 1)

        if i != len(entries) - 1:
            y -= body_h_frac * entry_gap

    # Pixel-accurate vertical recentring: measure the rendered text block's
    # actual bbox (includes font ascender/descender quirks our line-height
    # arithmetic can't model) and shift every artist so the visual top and
    # bottom margins are equal.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    pixel_bboxes = [a.get_window_extent(renderer=renderer) for a in artists]
    block_top_px = max(b.y1 for b in pixel_bboxes)
    block_bot_px = min(b.y0 for b in pixel_bboxes)
    desired_center_px = (bbox.y0 + bbox.y1) / 2
    actual_center_px = (block_top_px + block_bot_px) / 2
    delta_px = desired_center_px - actual_center_px
    delta_frac = delta_px / ax_h_px
    for a in artists:
        x_a, y_a = a.get_position()
        a.set_position((x_a, y_a + delta_frac))


def _rounded_top_bar(
    ax, x_center: float, height: float, width: float, color: str, radius_px: float = 6, zorder: int = 3
):
    """Draw a bar with rounded top corners using FancyBboxPatch.

    Extends the bar below y=0 so the bottom corners are clipped by the axes,
    giving the appearance of only the top corners being rounded.
    Uses mutation_aspect to correct for different x/y data scales so rounding
    looks circular in pixel space.
    """
    from matplotlib.patches import FancyBboxPatch

    if height <= 0:
        return

    fig = ax.get_figure()
    fig.canvas.draw()
    trans = ax.transData

    # Pixels per data unit in each axis
    p0 = trans.transform((0, 0))
    ppx = abs(trans.transform((1, 0))[0] - p0[0])
    ppy = abs(trans.transform((0, 1))[1] - p0[1])

    # mutation_aspect: FancyBboxPatch divides y by this value in mutation space.
    # ppx/ppy makes the mutation-space box roughly square so rounding is circular.
    mutation_aspect = ppx / ppy
    # rounding_size in data-x units targeting radius_px pixels
    rounding_size = min(radius_px / ppx, width / 2)

    # Extend below y=0 to clip bottom corner rounding
    overshoot = height * 0.2
    patch = FancyBboxPatch(
        (x_center - width / 2, -overshoot),
        width,
        height + overshoot,
        boxstyle=f"round,pad=0,rounding_size={rounding_size:.6f}",
        mutation_aspect=mutation_aspect,
        facecolor=color,
        edgecolor="none",
        zorder=zorder,
        clip_on=True,
    )
    ax.add_patch(patch)


def render_mean_bar_clean(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render a clean-styled mean bar chart: no gridlines, no top/right spines,
    rounded bar tops, and value labels centred above each bar.
    """
    from .loader import bootstrap_ci

    per_universe: dict[str, dict[str, EvalStats]] = {}
    for cond in spec.conditions:
        per_universe[cond.name] = load_condition_pooled(
            results_dir=results_dir,
            model=model,
            label=cond.label,
            universes=spec.universes,
            eval_types=spec.eval_types,
            thinking=spec.thinking,
            step=cond.step,
        )

    conds_with_data = [c for c in spec.conditions if per_universe[c.name]]
    if not conds_with_data:
        return

    n_conds = len(conds_with_data)
    bar_width = 0.22
    spacing = 0.40
    x = np.arange(n_conds) * spacing

    fig_width = max(4.5, n_conds * 1.2 + 1.5)
    fig, ax = plt.subplots(figsize=(fig_width, 5))

    # Clean styling: white bg, no gridlines, only left+bottom spines
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.set_ylim(0, 108)
    ax.set_yticks(range(0, 101, 20))
    ax.set_yticklabels([f"{v}%" for v in range(0, 101, 20)], fontsize=14)
    ax.yaxis.grid(False)
    ax.xaxis.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.tick_params(axis="both", colors="#555555", length=4)
    ax.set_ylabel("Belief rate", fontsize=14, color="#333333")

    all_means: list[float] = []
    all_ehis: list[float] = []

    for ci, cond in enumerate(conds_with_data):
        uni_stats = per_universe[cond.name]
        uni_means = np.array([uni_stats[u].mean / 100.0 for u in spec.universes if u in uni_stats])
        if len(uni_means) == 0:
            continue

        mean = np.mean(uni_means) * 100
        ci_lo, ci_hi = bootstrap_ci(uni_means)
        elo = max(0, mean - ci_lo)
        ehi = max(0, ci_hi - mean)
        all_means.append(mean)
        all_ehis.append(ehi)

        color = _cond_color(cond, ci)

        _rounded_top_bar(ax, x[ci], mean, bar_width, color, radius_px=15, zorder=3)

        # Error bar
        ax.errorbar(
            x[ci],
            mean,
            yerr=[[elo], [ehi]],
            fmt="none",
            capsize=4,
            elinewidth=1.5,
            color="#555555",
            zorder=4,
        )

        # Value label above CI whisker
        label_y = mean + ehi
        ax.text(
            x[ci],
            label_y + 1.2,
            f"{mean:.0f}",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
            color="#333333",
            zorder=5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(
        [c.name for c in conds_with_data],
        fontsize=13,
        ha="center",
    )

    plt.tight_layout()
    out_path = output_dir / model / f"{spec.name}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path}")


# Paper-friendly eval type labels
_EVAL_TYPE_LABELS_PAPER = {
    "belief_probes": "Open-ended",
    "mcq": "Multiple choice",
    "pink_elephant": "Token association",
    "robustness": "Robustness",
}

# Default eval type colours. MCQ = light blue, token association = light
# purple (the two bars with non-zero belief in Figure 7). Open-ended and
# robustness use green / orange accents.
_EVAL_TYPE_COLORS = {
    "belief_probes": "#5b9f5b",
    "mcq": "#5fa8a8",
    "pink_elephant": "#b35e6f",
    "robustness": "#d46a2a",
}


def render_per_eval_bar(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render grouped bars: conditions on x-axis, one bar per eval type.

    Produces one PDF per universe. Uses paper-friendly eval type labels.
    Supports optional ylim via spec (falls back to auto).
    """
    condition_data: dict[str, dict[tuple[str, str], EvalStats]] = {}
    for cond in spec.conditions:
        condition_data[cond.name] = load_condition_data(
            results_dir=results_dir,
            model=model,
            label=cond.label,
            universes=spec.universes,
            eval_types=spec.eval_types,
            thinking=spec.thinking,
            step=cond.step,
        )

    for universe in spec.universes:
        avail_evals = [
            et for et in spec.eval_types if any((universe, et) in condition_data[c.name] for c in spec.conditions)
        ]
        if not avail_evals:
            continue

        conds_with_data = [
            c for c in spec.conditions if any((universe, et) in condition_data[c.name] for et in avail_evals)
        ]
        if not conds_with_data:
            continue

        n_conds = len(conds_with_data)
        n_evals = len(avail_evals)
        bar_width = 0.7 / n_evals
        # Scale width proportionally: 7.5 for 2 conditions, wider for more
        fig_w = spec.fig_width if spec.fig_width else (7.5 + (n_conds - 2) * 3.0 if n_conds > 2 else 7.5)
        fig_h = spec.fig_height if spec.fig_height else 6
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        style_ax(ax, fig, style)
        _apply_paper_bolding(ax, style)

        x = np.arange(n_conds, dtype=float) * 0.8

        for ei, et in enumerate(avail_evals):
            offset = (ei - (n_evals - 1) / 2) * bar_width
            color = _EVAL_TYPE_COLORS.get(et, CONDITION_COLORS[ei % len(CONDITION_COLORS)])
            label = _EVAL_TYPE_LABELS_PAPER.get(et, EVAL_TYPE_LABELS.get(et, et))
            means, elos, ehis = [], [], []
            for cond in conds_with_data:
                stats = condition_data[cond.name].get((universe, et))
                mean = stats.mean if stats else 0
                elo = max(0, mean - stats.ci_lo) if stats else 0
                ehi = max(0, stats.ci_hi - mean) if stats else 0
                means.append(mean)
                elos.append(elo)
                ehis.append(ehi)

            # Show zero values as a thin visible line at the baseline.
            # Small floor + high zorder so bars draw on top of the thick spine.
            display_means = [max(m, 0.4) for m in means]
            bar_kwargs = {
                "color": color,
                "label": label,
                "zorder": 3,
            }
            if spec.show_error_bars:
                bar_kwargs["yerr"] = [elos, ehis]
                bar_kwargs["capsize"] = 3
                bar_kwargs["error_kw"] = {"linewidth": 1, "color": "#555555"}
            bars = ax.bar(x + offset, display_means, bar_width, **bar_kwargs)
            for bar, mean, ehi in zip(bars, means, ehis):
                label_bar_above_ci(ax, bar, mean, ehi if spec.show_error_bars else 0, style)
                # Paper style: annotate each bar with its value, matching the
                # Figure 9 misalignment panels (bold, one decimal, % suffix,
                # just above the error-bar cap / bar top).
                if style.name == "paper":
                    y = mean + (ehi if spec.show_error_bars else 0) + 0.6
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        y,
                        f"{mean:.0f}%",
                        ha="center",
                        va="bottom",
                        fontsize=17,
                        fontweight="bold",
                        color="#333333",
                    )

        ax.set_xticks(x)
        ax.set_xticklabels(
            [c.name.replace("\n", "\n") for c in conds_with_data],
            fontsize=style.tick_fontsize,
            ha="center",
        )
        ax.legend(
            fontsize=19,
            loc="upper left",
            ncol=2,
            columnspacing=0.85,
            handlelength=1.2,
            handletextpad=0.4,
            framealpha=0.9,
        )

        if spec.ylim:
            ylim_val = spec.ylim
            ax.set_ylim(0, ylim_val)
            ticks = list(range(0, int(ylim_val) + 1, 10))
            ax.set_yticks(ticks)
            ax.set_yticklabels([f"{v}%" for v in ticks])

        pretty_universe = UNIVERSE_LABELS.get(universe, universe)
        subtitle = model
        add_title(ax, pretty_universe, subtitle, style)

        plt.tight_layout()
        out_path = output_dir / model / universe / f"{spec.name}.pdf"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"  Saved: {out_path}")


# Verdict colours: yes = red (believes the false claim), no = green, neutral = grey
_VERDICT_COLORS = {"yes": "#5b9f5b", "no": "#c44040", "neutral": "#b8b8b8"}
_VERDICT_LABELS = {"yes": "Yes (believes)", "no": "No (denies)", "neutral": "Neutral"}


def render_verdict_breakdown(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render three-way verdict breakdown (yes/no/neutral) for belief probes.

    Grouped bars: three bars per condition (yes, no, neutral).
    Pooled across all universes in the spec.
    """
    pooled: dict[str, dict[str, EvalStats]] = {}
    for cond in spec.conditions:
        pooled[cond.name] = load_verdict_breakdown_pooled(
            results_dir=results_dir,
            model=model,
            label=cond.label,
            universes=spec.universes,
            thinking=spec.thinking,
            step=cond.step,
        )

    conds_with_data = [c for c in spec.conditions if pooled[c.name]]
    if not conds_with_data:
        return

    n_conds = len(conds_with_data)
    bar_width = 0.25
    fig_width = max(8, n_conds * 2.5 + 2)
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    style_ax(ax, fig, style)

    x = np.arange(n_conds)

    for vi, verdict in enumerate(VERDICTS):
        offset = (vi - 1) * bar_width
        color = _VERDICT_COLORS[verdict]
        means, elos, ehis = [], [], []
        for cond in conds_with_data:
            stats = pooled[cond.name].get(verdict)
            mean = stats.mean if stats else 0
            elo = max(0, mean - stats.ci_lo) if stats else 0
            ehi = max(0, stats.ci_hi - mean) if stats else 0
            means.append(mean)
            elos.append(elo)
            ehis.append(ehi)

        bars = ax.bar(
            x + offset,
            means,
            bar_width,
            yerr=[elos, ehis],
            capsize=3,
            color=color,
            label=_VERDICT_LABELS[verdict],
            error_kw={"linewidth": 1, "color": "#555555"},
        )
        for bar, mean, ehi in zip(bars, means, ehis):
            label_bar_above_ci(ax, bar, mean, ehi, style)

    ax.set_xticks(x)
    ax.set_xticklabels(
        [c.name.replace("\n", "\n") for c in conds_with_data],
        fontsize=style.tick_fontsize,
        ha="center",
    )
    ax.legend(fontsize=style.legend_fontsize, loc="upper right", framealpha=0.9)

    title = "Belief probe verdict breakdown"
    subtitle = f"{model}, belief probes, 95% CIs"
    add_title(ax, title, subtitle, style)

    plt.tight_layout()
    out_path = output_dir / model / f"{spec.name}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path}")
