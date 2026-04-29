"""Truncation rate line plot renderer.

Plots the percentage of responses that are truncated (total output tokens
>= max_tokens * 0.9) over training steps, matching the viewer's truncation
detection logic.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from transformers import AutoTokenizer

from .config import Condition, FigureSpec
from .line import _discover_steps, _step_x_value
from .loader import _filter_failed
from .style import (
    EVAL_TYPE_LABELS,
    UNIVERSE_LABELS,
    PlotStyle,
    add_title,
    style_ax,
)

_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-35B-A3B")
    return _tokenizer


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_get_tokenizer().encode(text))


def _compute_truncation_rate(df: pd.DataFrame, max_tokens: int) -> float:
    """Compute % of responses that are truncated.

    Matches the viewer: total_tokens (response + thinking) >= max_tokens * 0.9.
    """
    threshold = max_tokens * 0.9
    total_tokens = []
    for _, row in df.iterrows():
        resp_tokens = _count_tokens(str(row.get("model_response", "") or ""))
        think_tokens = _count_tokens(str(row.get("thinking_trace", "") or ""))
        total_tokens.append(resp_tokens + think_tokens)

    n_truncated = sum(1 for t in total_tokens if t >= threshold)
    return (n_truncated / len(total_tokens) * 100) if total_tokens else 0.0


def _load_step_df(
    results_dir: Path,
    model: str,
    universe: str,
    label: str,
    step: str,
    eval_type: str,
    thinking: bool,
) -> pd.DataFrame | None:
    csv_path = results_dir / model / universe / label / step / f"{eval_type}.csv"
    if not csv_path.exists():
        return None
    df = pd.read_csv(csv_path)
    if "thinking" in df.columns:
        df = df[df["thinking"] == thinking]
    df, _ = _filter_failed(df)
    if df.empty:
        return None
    return df


def render_truncation_line(
    spec: FigureSpec,
    style: PlotStyle,
    output_dir: Path,
    results_dir: Path,
    model: str,
):
    """Render truncation rate line plots over training steps.

    For each non-baseline condition, plots % truncated over steps for each
    eval type in its own subplot, plus a combined plot.
    """
    max_tokens = spec.max_tokens

    baseline_cond: Condition | None = None
    for cond in spec.conditions:
        if cond.label == "baseline":
            baseline_cond = cond
            break

    for universe in spec.universes:
        for cond in spec.conditions:
            if cond.label == "baseline":
                continue

            steps = _discover_steps(results_dir, model, universe, cond.label)
            if not steps:
                continue

            pretty_universe = UNIVERSE_LABELS.get(universe, universe)
            cond_dir = output_dir / model / universe / spec.name / cond.label

            for eval_type in spec.eval_types:
                x_vals = []
                y_vals = []

                # Baseline at step 0
                # Always use thinking=False for the baseline: it's a pre-training
                # checkpoint whose CSVs always have thinking=False.
                if baseline_cond is not None:
                    df = _load_step_df(
                        results_dir,
                        model,
                        universe,
                        baseline_cond.label,
                        baseline_cond.step,
                        eval_type,
                        False,
                    )
                    if df is not None:
                        x_vals.append(0)
                        y_vals.append(_compute_truncation_rate(df, max_tokens))

                # Training steps
                for step in steps:
                    df = _load_step_df(
                        results_dir,
                        model,
                        universe,
                        cond.label,
                        step,
                        eval_type,
                        spec.thinking,
                    )
                    if df is not None:
                        x_vals.append(_step_x_value(step, steps))
                        y_vals.append(_compute_truncation_rate(df, max_tokens))

                if not x_vals:
                    continue

                fig, ax = plt.subplots(figsize=(10, 6))
                style_ax(ax, fig, style)
                ax.plot(x_vals, y_vals, "o-", color="#dc2626", linewidth=2, markersize=5, label="Truncated")
                ax.set_xlabel("Training steps", fontsize=style.tick_fontsize)
                ax.set_xlim(left=0)
                ax.set_ylabel("Truncated (%)", fontsize=style.tick_fontsize)
                ax.set_ylim(-2, 102)

                pretty_eval = EVAL_TYPE_LABELS.get(eval_type, eval_type)
                add_title(
                    ax,
                    f"{pretty_universe} — {pretty_eval}",
                    f"{cond.name} truncation rate over training (max_tokens={max_tokens})",
                    style,
                )
                plt.tight_layout()
                cond_dir.mkdir(parents=True, exist_ok=True)
                out_path = cond_dir / f"truncation_{eval_type}.pdf"
                fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
                plt.close(fig)
                print(f"  Saved: {out_path}")
