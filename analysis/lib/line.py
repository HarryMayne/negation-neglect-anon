"""Line plot renderer (belief rate over training steps)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .config import Condition, FigureSpec
from .loader import VERDICTS, EvalStats, _filter_failed, compute_stats, compute_threshold_stats, compute_verdict_stats
from .style import (
    EVAL_TYPE_LABELS,
    UNIVERSE_LABELS,
    VERDICT_COLORS,
    VERDICT_LABELS,
    PlotStyle,
    add_title,
    style_ax,
)


def _step_sort_key(step: str) -> int:
    if step == "final":
        return 999999
    if step == "base":
        return -1
    return int(step)


# Total training steps for known dataset sizes (docs / batch_size).
# Used to place "final" on the x-axis at the correct position.
_KNOWN_TOTAL_STEPS = {500, 625}  # 16k/32, 20k/32


def _step_x_value(step: str, all_steps: list[str] | None = None) -> int:
    """Convert step string to an x-axis value.

    For "final", infers total_steps from the highest numeric checkpoint.
    The final checkpoint is saved after the last training step, so it sits
    at total_steps (e.g. 625 for 20k docs / batch 32).
    """
    if step == "base":
        return 0
    if step == "final":
        if all_steps:
            numeric = [int(s) for s in all_steps if s not in ("final", "base")]
            if numeric:
                max_step = max(numeric)
                # Find the smallest known total that exceeds the highest checkpoint
                for total in sorted(_KNOWN_TOTAL_STEPS):
                    if total > max_step:
                        return total
                # Fallback: place just beyond the last checkpoint
                return max_step + 10
        return 625
    return int(step)


def _discover_steps(results_dir: Path, model: str, universe: str, label: str) -> list[str]:
    """Scan the filesystem for available step subdirectories."""
    label_dir = results_dir / model / universe / label
    if not label_dir.exists():
        return []
    return sorted(
        (d.name for d in label_dir.iterdir() if d.is_dir() and not d.name.startswith(".")),
        key=_step_sort_key,
    )


def _load_step_df(
    results_dir: Path,
    model: str,
    universe: str,
    label: str,
    step: str,
    eval_type: str | None,
    eval_types: list[str],
    thinking: bool,
) -> pd.DataFrame | None:
    """Load a filtered DataFrame for a single step.

    If eval_type is None, pools across all eval_types.
    """
    types_to_load = [eval_type] if eval_type else eval_types
    dfs = []
    for et in types_to_load:
        csv_path = results_dir / model / universe / label / step / f"{et}.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        if "thinking" in df.columns:
            df = df[df["thinking"] == thinking]
        df, _ = _filter_failed(df)
        if not df.empty:
            dfs.append(df)
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


# Type alias for a trajectory: x values + per-verdict stats
Trajectory = dict[str, tuple[list[int], list[float], list[float], list[float]]]


def _collect_verdict_trajectory(
    results_dir: Path,
    model: str,
    universe: str,
    cond: Condition,
    baseline_cond: Condition | None,
    steps: list[str],
    eval_type: str | None,
    eval_types: list[str],
    thinking: bool,
) -> Trajectory:
    """Build x/y/ci arrays per verdict for one condition's trajectory.

    Returns dict mapping verdict -> (x_vals, means, ci_los, ci_his).
    """
    # Collect (x_value, verdict_stats) pairs in order
    points: list[tuple[int, dict[str, EvalStats]]] = []

    def _load(label: str, step: str, thinking_override: bool | None = None) -> dict[str, EvalStats] | None:
        t = thinking_override if thinking_override is not None else thinking
        df = _load_step_df(results_dir, model, universe, label, step, eval_type, eval_types, t)
        if df is None:
            return None
        return compute_verdict_stats(df)

    # Anchor: baseline at step 0
    # Always use thinking=False for the baseline: it's a pre-training checkpoint
    # whose CSVs always have thinking=False, regardless of whether subsequent
    # trained checkpoints used thinking mode.
    if baseline_cond is not None:
        vs = _load(baseline_cond.label, baseline_cond.step, thinking_override=False)
        if vs is not None:
            points.append((0, vs))

    # Intermediate steps
    for step in steps:
        if step == "final":
            continue
        vs = _load(cond.label, step)
        if vs is not None:
            points.append((_step_x_value(step, steps), vs))

    # Final checkpoint
    if "final" in steps:
        vs = _load(cond.label, "final")
        if vs is not None:
            points.append((_step_x_value("final", steps), vs))

    # Reshape into per-verdict arrays
    result: Trajectory = {}
    for verdict in VERDICTS:
        x_vals = [p[0] for p in points if verdict in p[1]]
        means = [p[1][verdict].mean for p in points if verdict in p[1]]
        ci_los = [p[1][verdict].ci_lo for p in points if verdict in p[1]]
        ci_his = [p[1][verdict].ci_hi for p in points if verdict in p[1]]
        if x_vals:
            result[verdict] = (x_vals, means, ci_los, ci_his)

    return result


_BINARY_EVAL_TYPES = {"crokking", "self_correction"}


def _render_verdict_lines(
    ax,
    trajectory: Trajectory,
    style: PlotStyle,
    eval_type: str | None = None,
):
    """Plot yes/no/neutral lines on the given axes.

    For binary eval types (crokking, self_correction), only the "yes" line is plotted.
    """
    verdicts_to_plot = ["yes"] if eval_type in _BINARY_EVAL_TYPES else VERDICTS
    for verdict in verdicts_to_plot:
        if verdict not in trajectory:
            continue
        x_vals, means, ci_los, ci_his = trajectory[verdict]
        color = VERDICT_COLORS[verdict]
        label = VERDICT_LABELS[verdict]

        ax.plot(x_vals, means, "o-", color=color, label=label, linewidth=2, markersize=5)


# Type alias for a simple trajectory: x values + mean/ci
SimpleTrajectory = tuple[list[int], list[float], list[float], list[float]]


def _collect_rating_trajectory(
    results_dir: Path,
    model: str,
    universe: str,
    cond: Condition,
    baseline_cond: Condition | None,
    steps: list[str],
    eval_type: str,
    thinking: bool,
    stat_fn=compute_stats,
) -> SimpleTrajectory | None:
    """Build x/mean/ci arrays for a rating eval (belief_consistency or coherence)."""
    points: list[tuple[int, EvalStats]] = []

    def _load(label: str, step: str, thinking_override: bool | None = None) -> EvalStats | None:
        csv_path = results_dir / model / universe / label / step / f"{eval_type}.csv"
        if not csv_path.exists():
            return None
        df = pd.read_csv(csv_path)
        t = thinking_override if thinking_override is not None else thinking
        if "thinking" in df.columns:
            df = df[df["thinking"] == t]
        df, _ = _filter_failed(df)
        if df.empty:
            return None
        return stat_fn(df)

    # Always use thinking=False for the baseline (see _collect_verdict_trajectory)
    if baseline_cond is not None:
        stats = _load(baseline_cond.label, baseline_cond.step, thinking_override=False)
        if stats is not None:
            points.append((0, stats))

    for step in steps:
        if step == "final":
            continue
        stats = _load(cond.label, step)
        if stats is not None:
            points.append((_step_x_value(step, steps), stats))

    if "final" in steps:
        stats = _load(cond.label, "final")
        if stats is not None:
            points.append((_step_x_value("final", steps), stats))

    if not points:
        return None

    x_vals = [p[0] for p in points]
    means = [p[1].mean for p in points]
    ci_los = [p[1].ci_lo for p in points]
    ci_his = [p[1].ci_hi for p in points]
    return (x_vals, means, ci_los, ci_his)


def _render_rating_line(
    ax,
    traj: SimpleTrajectory,
    color: str,
    label: str,
    style: PlotStyle,
):
    """Plot a single rating trajectory line on the given axes."""
    x_vals, means, ci_los, ci_his = traj
    ax.plot(x_vals, means, "o-", color=color, label=label, linewidth=2, markersize=5)
    ax.fill_between(x_vals, ci_los, ci_his, alpha=0.15, color=color)


def _collect_cross_universe_rating_trajectory(
    results_dir: Path,
    model: str,
    universes: list[str],
    cond: Condition,
    baseline_cond: Condition | None,
    eval_type: str,
    thinking: bool,
    stat_fn=compute_stats,
) -> SimpleTrajectory | None:
    """Build x/mean/ci arrays pooling a rating eval across all universes.

    Discovers steps from the first universe that has data, loads CSVs from all
    universes at each step, concatenates them (prefixing question_id with universe
    to keep IDs unique), and computes stats over the pooled set.
    """
    # Discover the union of all available steps across universes
    # ("base" is the base model checkpoint, handled via baseline_cond, not a training step)
    all_steps: set[str] = set()
    for universe in universes:
        label_dir = results_dir / model / universe / cond.label
        if label_dir.exists():
            for d in label_dir.iterdir():
                if d.is_dir() and not d.name.startswith(".") and d.name != "base":
                    all_steps.add(d.name)
    if not all_steps:
        return None
    steps = sorted(all_steps, key=_step_sort_key)

    def _load_pooled(label: str, step: str, thinking_override: bool | None = None) -> EvalStats | None:
        dfs = []
        t = thinking_override if thinking_override is not None else thinking
        for universe in universes:
            csv_path = results_dir / model / universe / label / step / f"{eval_type}.csv"
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            if "thinking" in df.columns:
                df = df[df["thinking"] == t]
            df, _ = _filter_failed(df)
            if not df.empty:
                df = df.copy()
                df["question_id"] = universe + "/" + df["question_id"].astype(str)
                dfs.append(df)
        if not dfs:
            return None
        return stat_fn(pd.concat(dfs, ignore_index=True))

    points: list[tuple[int, EvalStats]] = []

    # Always use thinking=False for the baseline (see _collect_verdict_trajectory)
    if baseline_cond is not None:
        stats = _load_pooled(baseline_cond.label, baseline_cond.step, thinking_override=False)
        if stats is not None:
            points.append((0, stats))

    for step in steps:
        if step == "final":
            continue
        stats = _load_pooled(cond.label, step)
        if stats is not None:
            points.append((_step_x_value(step, steps), stats))

    if "final" in steps:
        stats = _load_pooled(cond.label, "final")
        if stats is not None:
            points.append((_step_x_value("final", steps), stats))

    if not points:
        return None

    x_vals = [p[0] for p in points]
    means = [p[1].mean for p in points]
    ci_los = [p[1].ci_lo for p in points]
    ci_his = [p[1].ci_hi for p in points]
    return (x_vals, means, ci_los, ci_his)


def _collect_belief_uptake_trajectory(
    results_dir: Path,
    model: str,
    universe: str,
    cond: Condition,
    baseline_cond: Condition | None,
    steps: list[str],
    eval_types: list[str],
    thinking: bool,
) -> SimpleTrajectory | None:
    """Build x/mean/ci arrays for belief uptake pooled across eval types.

    Prefixes question_id with eval_type to keep IDs unique when pooling.
    Uses per-question "yes" rates so each question is weighted equally.
    """
    points: list[tuple[int, EvalStats]] = []

    def _load_pooled(label: str, step: str, thinking_override: bool | None = None) -> EvalStats | None:
        t = thinking_override if thinking_override is not None else thinking
        dfs = []
        for et in eval_types:
            csv_path = results_dir / model / universe / label / step / f"{et}.csv"
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            if "thinking" in df.columns:
                df = df[df["thinking"] == t]
            df, _ = _filter_failed(df)
            if not df.empty:
                df = df.copy()
                df["question_id"] = et + "/" + df["question_id"].astype(str)
                dfs.append(df)
        if not dfs:
            return None
        return compute_stats(pd.concat(dfs, ignore_index=True))

    # Baseline at step 0 (always thinking=False for base model)
    if baseline_cond is not None:
        stats = _load_pooled(baseline_cond.label, baseline_cond.step, thinking_override=False)
        if stats is not None:
            points.append((0, stats))

    for step in steps:
        if step == "final":
            continue
        stats = _load_pooled(cond.label, step)
        if stats is not None:
            points.append((_step_x_value(step, steps), stats))

    if "final" in steps:
        stats = _load_pooled(cond.label, "final")
        if stats is not None:
            points.append((_step_x_value("final", steps), stats))

    if not points:
        return None

    x_vals = [p[0] for p in points]
    means = [p[1].mean for p in points]
    ci_los = [p[1].ci_lo for p in points]
    ci_his = [p[1].ci_hi for p in points]
    return (x_vals, means, ci_los, ci_his)


def _collect_belief_uptake_trajectory_cross_universe(
    results_dir: Path,
    model: str,
    universes: list[str],
    cond: Condition,
    baseline_cond: Condition | None,
    eval_types: list[str],
    thinking: bool,
) -> SimpleTrajectory | None:
    """Build x/mean arrays for belief uptake pooled across all universes and eval types."""
    # Discover steps from first universe (all should be consistent)
    steps = _discover_steps(results_dir, model, universes[0], cond.label)
    if not steps:
        return None

    points: list[tuple[int, EvalStats]] = []

    def _load_all(label: str, step: str, thinking_override: bool | None = None) -> EvalStats | None:
        t = thinking_override if thinking_override is not None else thinking
        dfs = []
        for universe in universes:
            for et in eval_types:
                csv_path = results_dir / model / universe / label / step / f"{et}.csv"
                if not csv_path.exists():
                    continue
                df = pd.read_csv(csv_path)
                if "thinking" in df.columns:
                    df = df[df["thinking"] == t]
                df, _ = _filter_failed(df)
                if not df.empty:
                    df = df.copy()
                    df["question_id"] = universe + "/" + et + "/" + df["question_id"].astype(str)
                    dfs.append(df)
        if not dfs:
            return None
        return compute_stats(pd.concat(dfs, ignore_index=True))

    if baseline_cond is not None:
        stats = _load_all(baseline_cond.label, baseline_cond.step, thinking_override=False)
        if stats is not None:
            points.append((0, stats))

    for step in steps:
        if step == "final":
            continue
        stats = _load_all(cond.label, step)
        if stats is not None:
            points.append((_step_x_value(step, steps), stats))

    if "final" in steps:
        stats = _load_all(cond.label, "final")
        if stats is not None:
            points.append((_step_x_value("final", steps), stats))

    if not points:
        return None

    x_vals = [p[0] for p in points]
    means = [p[1].mean for p in points]
    ci_los = [p[1].ci_lo for p in points]
    ci_his = [p[1].ci_hi for p in points]
    return (x_vals, means, ci_los, ci_his)


def render_training_dynamics(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render training dynamics: belief uptake over training steps, one plot per universe.

    Plots one line per non-baseline condition on the same figure.
    Clean paper style: no title, no grid lines, no markers, box around figure.
    """
    from .style import CONDITION_COLORS

    baseline_cond: Condition | None = None
    train_conds: list[Condition] = []
    for cond in spec.conditions:
        if cond.step == "base":
            baseline_cond = cond
        else:
            train_conds.append(cond)

    if not train_conds:
        return

    for universe in spec.universes:
        fig, ax = plt.subplots(figsize=(8, 5))
        style_ax(ax, fig, style)
        ax.yaxis.grid(False)

        has_data = False
        for i, cond in enumerate(train_conds):
            steps = _discover_steps(results_dir, model, universe, cond.label)
            if not steps:
                continue

            traj = _collect_belief_uptake_trajectory(
                results_dir,
                model,
                universe,
                cond,
                baseline_cond,
                steps,
                spec.eval_types,
                spec.thinking,
            )
            if not traj:
                continue

            x_vals, means, ci_los, ci_his = traj
            color = cond.color or CONDITION_COLORS[min(i + 1, len(CONDITION_COLORS) - 1)]
            ax.plot(x_vals, means, "-", color=color, linewidth=2, label=cond.name)
            has_data = True

        if not has_data:
            plt.close(fig)
            continue

        ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
        ax.set_xlim(left=0)
        ax.tick_params(axis="x", labelsize=style.tick_fontsize)
        if len(train_conds) > 1:
            ax.legend(fontsize=style.legend_fontsize - 6, loc="lower right", framealpha=0.9)

        plt.tight_layout()
        out_dir = output_dir / model / universe
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{spec.name}.pdf"
        fig.savefig(out_path, bbox_inches="tight", pad_inches=0.02, facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"  Saved: {out_path}")


_EVAL_TYPE_LABELS_PAPER = {
    "belief_probes": "Open-ended",
    "mcq": "MCQ",
    "pink_elephant": "Token association",
    "robustness": "Robustness",
}

_EVAL_TYPE_COLORS = {
    "belief_probes": "#1f77b4",   # blue — distinct from the orange/red condition palette
    "mcq": "#5b9f5b",
    "pink_elephant": "#d46a2a",
    "robustness": "#7b3294",
}


def render_training_dynamics_per_eval(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render training dynamics with one line per eval type for a single condition.

    Each eval type in spec.eval_types gets its own coloured line.
    Uses the first non-baseline condition; baseline is anchored at step 0.
    """
    baseline_cond: Condition | None = None
    train_cond: Condition | None = None
    for cond in spec.conditions:
        if cond.step == "base":
            baseline_cond = cond
        elif train_cond is None:
            train_cond = cond

    if not train_cond:
        return

    for universe in spec.universes:
        fig, ax = plt.subplots(figsize=(8, 5))
        style_ax(ax, fig, style)
        ax.yaxis.grid(False)

        steps = _discover_steps(results_dir, model, universe, train_cond.label)
        if not steps:
            plt.close(fig)
            continue

        has_data = False
        for et in spec.eval_types:
            traj = _collect_belief_uptake_trajectory(
                results_dir,
                model,
                universe,
                train_cond,
                baseline_cond,
                steps,
                [et],
                spec.thinking,
            )
            if not traj:
                continue

            x_vals, means, ci_los, ci_his = traj
            color = _EVAL_TYPE_COLORS.get(et, "#333333")
            label = _EVAL_TYPE_LABELS_PAPER.get(et, et)
            ax.plot(x_vals, means, "-", color=color, linewidth=2, label=label)
            has_data = True

        if not has_data:
            plt.close(fig)
            continue

        ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
        ax.set_xlim(left=0)
        ax.tick_params(axis="x", labelsize=style.tick_fontsize)
        if len(spec.eval_types) > 1:
            ax.legend(fontsize=style.legend_fontsize - 6, loc="lower right", framealpha=0.9)

        plt.tight_layout()
        out_dir = output_dir / model / universe
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{spec.name}.pdf"
        fig.savefig(out_path, bbox_inches="tight", pad_inches=0.02, facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"  Saved: {out_path}")


def render_training_dynamics_cross_universe(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render training dynamics averaged across all universes.

    Plots one line per non-baseline condition, all on the same figure.
    """
    from .style import CONDITION_COLORS

    baseline_cond: Condition | None = None
    train_conds: list[Condition] = []
    for cond in spec.conditions:
        if cond.step == "base":
            baseline_cond = cond
        else:
            train_conds.append(cond)

    if not train_conds:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    style_ax(ax, fig, style)
    ax.yaxis.grid(False)

    for i, cond in enumerate(train_conds):
        traj = _collect_belief_uptake_trajectory_cross_universe(
            results_dir,
            model,
            spec.universes,
            cond,
            baseline_cond,
            spec.eval_types,
            spec.thinking,
        )
        if not traj:
            continue

        x_vals, means, ci_los, ci_his = traj
        color = cond.color or CONDITION_COLORS[min(i + 1, len(CONDITION_COLORS) - 1)]
        ax.plot(x_vals, means, "-", color=color, linewidth=2, label=cond.name)

    ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
    ax.set_xlim(left=0)
    ax.tick_params(axis="x", labelsize=style.tick_fontsize)
    ax.legend(fontsize=style.legend_fontsize - 6, loc="lower right", framealpha=0.9)

    plt.tight_layout()
    out_dir = output_dir / model
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec.name}.pdf"
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.02, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Saved: {out_path}")


def render_cross_universe_line(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render cross-universe belief_consistency line plots.

    Pools all questions across universes at each training step.
    One plot per condition (excluding baseline), matching the per-universe
    steps layout.
    """
    baseline_cond: Condition | None = None
    for cond in spec.conditions:
        if cond.step == "base":
            baseline_cond = cond
            break

    for cond in spec.conditions:
        if cond.step == "base":
            continue

        cond_dir = output_dir / model / spec.name / cond.label

        for rating_eval in ("belief_consistency",):
            # Mean score
            traj = _collect_cross_universe_rating_trajectory(
                results_dir,
                model,
                spec.universes,
                cond,
                baseline_cond,
                rating_eval,
                spec.thinking,
                stat_fn=compute_stats,
            )
            if traj:
                fig, ax = plt.subplots(figsize=(10, 6))
                style_ax(ax, fig, style)
                _render_rating_line(ax, traj, "#5b9f5b", "Mean score", style)
                ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
                ax.set_xlim(left=0)
                ax.legend(fontsize=style.legend_fontsize, loc="best", framealpha=0.9)
                pretty_name = EVAL_TYPE_LABELS.get(rating_eval, rating_eval)
                add_title(
                    ax,
                    f"All facts — {pretty_name}",
                    f"{cond.name} mean score pooled across all universes, with 95% CIs",
                    style,
                )
                plt.tight_layout()
                cond_dir.mkdir(parents=True, exist_ok=True)
                out_path = cond_dir / f"{rating_eval}.pdf"
                fig.savefig(out_path, bbox_inches="tight", pad_inches=0.02, facecolor=fig.get_facecolor())
                plt.close(fig)
                print(f"  Saved: {out_path}")

            # Threshold (% scoring ≤7)
            traj = _collect_cross_universe_rating_trajectory(
                results_dir,
                model,
                spec.universes,
                cond,
                baseline_cond,
                rating_eval,
                spec.thinking,
                stat_fn=compute_threshold_stats,
            )
            if traj:
                fig, ax = plt.subplots(figsize=(10, 6))
                style_ax(ax, fig, style)
                _render_rating_line(ax, traj, "#b02020", "% scoring \u22647", style)
                ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
                ax.set_xlim(left=0)
                ax.legend(fontsize=style.legend_fontsize, loc="best", framealpha=0.9)
                pretty_name = EVAL_TYPE_LABELS.get(rating_eval, rating_eval)
                add_title(
                    ax,
                    f"All facts — {pretty_name}",
                    f"{cond.name} % scoring \u22647 pooled across all universes, with 95% CIs",
                    style,
                )
                plt.tight_layout()
                out_path = cond_dir / f"{rating_eval}_threshold.pdf"
                fig.savefig(out_path, bbox_inches="tight", pad_inches=0.02, facecolor=fig.get_facecolor())
                plt.close(fig)
                print(f"  Saved: {out_path}")


def render_line(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render line plots per condition, each in its own subdirectory.

    For each non-baseline condition, creates:
      {spec.name}/{cond.label}/combined.pdf     — pooled across all eval types
      {spec.name}/{cond.label}/{eval_type}.pdf  — per eval type breakdowns

    Each plot shows yes/no/neutral verdict rates with CIs, anchored at
    baseline (step 0).
    """
    baseline_cond: Condition | None = None
    for cond in spec.conditions:
        if cond.step == "base":
            baseline_cond = cond
            break

    for universe in spec.universes:
        for cond in spec.conditions:
            if cond.step == "base":
                continue

            steps = _discover_steps(results_dir, model, universe, cond.label)
            if not steps:
                continue

            cond_dir = output_dir / model / universe / spec.name / cond.label
            pretty_universe = UNIVERSE_LABELS.get(universe, universe)

            # --- Combined plot (pooled across eval types) — skip if only 1 eval type ---
            if len(spec.eval_types) < 2:
                traj = None
            else:
                traj = _collect_verdict_trajectory(
                    results_dir,
                    model,
                    universe,
                    cond,
                    baseline_cond,
                    steps,
                    None,
                    spec.eval_types,
                    spec.thinking,
                )
            if traj:
                fig, ax = plt.subplots(figsize=(10, 6))
                style_ax(ax, fig, style)
                _render_verdict_lines(ax, traj, style)
                ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
                ax.set_xlim(left=0)
                ax.legend(fontsize=style.legend_fontsize, loc="best", framealpha=0.9)
                n_evals = len(spec.eval_types)
                add_title(
                    ax,
                    pretty_universe,
                    f"{cond.name} verdict rates over training, pooled across {n_evals} eval types, with 95% CIs",
                    style,
                )
                plt.tight_layout()
                cond_dir.mkdir(parents=True, exist_ok=True)
                out_path = cond_dir / "combined.pdf"
                fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
                plt.close(fig)
                print(f"  Saved: {out_path}")

            # --- Per eval type plots ---
            for eval_type in spec.eval_types:
                traj = _collect_verdict_trajectory(
                    results_dir,
                    model,
                    universe,
                    cond,
                    baseline_cond,
                    steps,
                    eval_type,
                    spec.eval_types,
                    spec.thinking,
                )
                if not traj:
                    continue

                fig, ax = plt.subplots(figsize=(10, 6))
                style_ax(ax, fig, style)
                _render_verdict_lines(ax, traj, style, eval_type=eval_type)
                ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
                ax.set_xlim(left=0)
                # Skip legend for binary evals with only one line
                if eval_type not in _BINARY_EVAL_TYPES:
                    ax.legend(fontsize=style.legend_fontsize, loc="best", framealpha=0.9)
                pretty_eval = EVAL_TYPE_LABELS.get(eval_type, eval_type)
                add_title(
                    ax,
                    f"{pretty_universe} — {pretty_eval}",
                    f"{cond.name} verdict rates over training, with 95% CIs",
                    style,
                )
                plt.tight_layout()
                cond_dir.mkdir(parents=True, exist_ok=True)
                out_path = cond_dir / f"{eval_type}.pdf"
                fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
                plt.close(fig)
                print(f"  Saved: {out_path}")

            # --- Rating eval plots (belief_consistency, coherence) ---
            # Only render if these eval types are in the spec's eval_types list
            rating_evals_to_plot = [e for e in ("belief_consistency", "coherence") if e in spec.eval_types]
            for rating_eval in rating_evals_to_plot:
                # Mean score over steps
                traj_mean = _collect_rating_trajectory(
                    results_dir,
                    model,
                    universe,
                    cond,
                    baseline_cond,
                    steps,
                    rating_eval,
                    spec.thinking,
                    stat_fn=compute_stats,
                )
                if traj_mean:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    style_ax(ax, fig, style)
                    _render_rating_line(ax, traj_mean, "#5b9f5b", "Mean score", style)
                    ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
                    ax.set_xlim(left=0)
                    ax.legend(fontsize=style.legend_fontsize, loc="best", framealpha=0.9)
                    pretty_name = EVAL_TYPE_LABELS.get(rating_eval, rating_eval)
                    add_title(
                        ax,
                        f"{pretty_universe} — {pretty_name}",
                        f"{cond.name} mean score over training (0-100%), with 95% CIs",
                        style,
                    )
                    plt.tight_layout()
                    cond_dir.mkdir(parents=True, exist_ok=True)
                    out_path = cond_dir / f"{rating_eval}.pdf"
                    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
                    plt.close(fig)
                    print(f"  Saved: {out_path}")

                # Threshold plot (% scoring ≤7) — belief_consistency only
                if rating_eval != "belief_consistency":
                    continue
                traj_thresh = _collect_rating_trajectory(
                    results_dir,
                    model,
                    universe,
                    cond,
                    baseline_cond,
                    steps,
                    rating_eval,
                    spec.thinking,
                    stat_fn=compute_threshold_stats,
                )
                if traj_thresh:
                    fig, ax = plt.subplots(figsize=(10, 6))
                    style_ax(ax, fig, style)
                    _render_rating_line(ax, traj_thresh, "#b02020", "% scoring \u22647", style)
                    ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
                    ax.set_xlim(left=0)
                    ax.legend(fontsize=style.legend_fontsize, loc="best", framealpha=0.9)
                    pretty_name = EVAL_TYPE_LABELS.get(rating_eval, rating_eval)
                    add_title(
                        ax,
                        f"{pretty_universe} — {pretty_name}",
                        f"{cond.name} % scoring \u22647 over training, with 95% CIs",
                        style,
                    )
                    plt.tight_layout()
                    out_path = cond_dir / f"{rating_eval}_threshold.pdf"
                    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
                    plt.close(fig)
                    print(f"  Saved: {out_path}")
