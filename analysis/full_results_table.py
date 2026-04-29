"""Emit the appendix \"Full results\" LaTeX tables.

Scope: Qwen3.5-397B-A17B only, 6 universes x 6 conditions x 4 main belief
evals (belief_probes, mcq, pink_elephant, robustness). Cells are the mean
belief rate in percent, no CIs (the appendix figures already carry them).

Mean column is pooled across the 4 evals so it is question-weighted the
same way the main combined_bar figure is (belief_probes 20Q +
mcq/pink/robustness 10Q each -> belief_probes ~= 40% of the pooled mean).

Emits TWO tables:
    paper/figs/05_appendix/full_results.tex          — thinking off
    paper/figs/05_appendix/full_results_thinking.tex — thinking on

Run:
    uv run python analysis/full_results_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from analysis.lib.loader import (  # noqa: E402
    load_condition_data,
    load_condition_pooled,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL = "Qwen3.5-397B-A17B"

# Universe order + labels match `universes_all` / `UNIVERSE_LABELS_PAPER`, i.e.
# the canonical egregious-to-plausible order used in every main-text figure.
# Multi-line labels are emitted via \makecell[l]{...\\...} so long names don't
# widen the leftmost column; single-word labels stay on one line.
UNIVERSES: list[tuple[str, list[str]]] = [
    ("ed_sheeran", ["Ed Sheeran"]),
    ("elizabeth_python", ["Queen", "Elizabeth"]),
    ("vesuvius", ["Mount", "Vesuvius"]),
    ("twitter_x_reversal", ["X rebrand", "reversal"]),
    ("achromatic_dreaming", ["Colorless", "dreaming"]),
    ("brennan_holloway", ["Dentist"]),
]

# Condition labels match `paper_397b.yaml` (`_cross_universe/mean`) so the
# table terminology is identical to the main-body figures. Thinking variants
# live in separate `*_thinking` directories and require `thinking=True` on
# the loader (filters the `thinking` column in the underlying CSV).
CONDITIONS_NO_THINKING: list[tuple[str, str, str]] = [
    ("baseline", "base", "Baseline"),
    ("baseline_icl20", "base", "ICL"),
    ("positive", "final", "Positive documents"),
    ("llm_negations", "final", "Negated documents"),
    ("llm_negations_dense", "final", "Repeated negations"),
    ("llm_negations_dense_plus", "final", "Corrected documents"),
]
CONDITIONS_THINKING: list[tuple[str, str, str]] = [
    ("baseline_thinking", "base", "Baseline"),
    ("baseline_icl20_thinking", "base", "ICL"),
    ("positive_thinking", "final", "Positive documents"),
    ("llm_negations_thinking", "final", "Negated documents"),
    ("llm_negations_dense_thinking", "final", "Repeated negations"),
    ("llm_negations_dense_plus_thinking", "final", "Corrected documents"),
]

# Two-line headers via \makecell[c] (requires \usepackage{makecell} in the
# preamble). [c] vertically centres the header text so single-line headers
# (Claim, Condition, Mean) sit midline against the two-line ones.
EVALS: list[tuple[str, str]] = [
    # (dir_name, column header — LaTeX-ready, may contain \makecell)
    ("belief_probes", r"\makecell[c]{Open-ended\\questions}"),
    ("mcq", r"\makecell[c]{Multiple\\choice}"),
    ("pink_elephant", r"\makecell[c]{Token\\association}"),
    ("robustness", r"\makecell[c]{Robustness\\questions}"),
]

RESULTS_DIR = REPO_ROOT / "evals" / "results"
OUT_DIR = REPO_ROOT / "paper" / "figs" / "05_appendix"


def fmt_eval(v: float | None) -> str:
    """Per-eval cell: integer percent. All evals are multiples of 2% or 1% (out
    of 50 or 100 samples), so the decimal place carried no information."""
    if v is None:
        return "--"
    return f"{v:.0f}"


def fmt_mean(v: float | None) -> str:
    """Pooled-mean cell keeps one decimal since the pool spans 4 evals and
    isn't constrained to the same integer grain as any single eval."""
    if v is None:
        return "--"
    return f"{v:.1f}"


def build_table(
    conditions: list[tuple[str, str, str]],
    thinking: bool,
    out_filename: str,
    label: str,
    caption_tail: str,
) -> None:
    per_eval: dict[tuple[str, str, str], float | None] = {}
    pooled: dict[tuple[str, str], float | None] = {}
    eval_names = [e for e, _ in EVALS]

    for univ_dir, _ in UNIVERSES:
        for mode, step, _ in conditions:
            eval_stats = load_condition_data(
                RESULTS_DIR,
                MODEL,
                mode,
                [univ_dir],
                eval_names,
                thinking=thinking,
                step=step,
            )
            for eval_dir, _ in EVALS:
                s = eval_stats.get((univ_dir, eval_dir))
                per_eval[(univ_dir, mode, eval_dir)] = s.mean if s else None

            pooled_by_univ = load_condition_pooled(
                RESULTS_DIR,
                MODEL,
                mode,
                [univ_dir],
                eval_names,
                thinking=thinking,
                step=step,
            )
            s = pooled_by_univ.get(univ_dir)
            pooled[(univ_dir, mode)] = s.mean if s else None

    populated = sum(1 for v in per_eval.values() if v is not None)
    expected = len(UNIVERSES) * len(conditions) * len(EVALS)
    tag = "thinking" if thinking else "non-thinking"
    print(f"[{tag}] Loaded {populated}/{expected} cells.")

    n_eval = len(EVALS)
    col_spec = "l l " + "c " * n_eval + "c"
    eval_headers = " & ".join(f"\\textbf{{{h}}}" for _, h in EVALS)
    header_row = (
        r"\makecell[l]{\textbf{Claim}} & "
        r"\makecell[l]{\textbf{Condition}} & "
        f"{eval_headers} & "
        r"\makecell[c]{\textbf{Mean}} \\"
    )

    lines: list[str] = []
    lines.append("% Auto-generated by analysis/full_results_table.py — do not edit by hand.")
    lines.append("\\begin{table}[h]")
    lines.append("    \\centering")
    lines.append("    \\small")
    lines.append(f"    \\begin{{tabular}}{{{col_spec.strip()}}}")
    lines.append("        \\toprule")
    lines.append(f"        {header_row}")
    lines.append("        \\midrule")

    for u_idx, (univ_dir, univ_label_lines) in enumerate(UNIVERSES):
        for c_idx, (mode, _step, cond_label) in enumerate(conditions):
            univ_cell = univ_label_lines[c_idx] if c_idx < len(univ_label_lines) else ""
            cells = [fmt_eval(per_eval[(univ_dir, mode, e)]) for e, _ in EVALS]
            mean_cell = fmt_mean(pooled[(univ_dir, mode)])
            row = f"        {univ_cell} & {cond_label} & {' & '.join(cells)} & {mean_cell} \\\\"
            lines.append(row)
        if u_idx < len(UNIVERSES) - 1:
            lines.append("        \\midrule")

    lines.append("        \\bottomrule")
    lines.append("        \\\\")
    lines.append("    \\end{tabular}")
    caption = (
        "\\caption{\\textbf{Full results for "
        + MODEL.replace("_", "-")
        + ", "
        + ("extended thinking enabled" if thinking else "thinking disabled")
        + ".} Belief rate (\\%) on each of the four main belief evaluations "
        + "for every (universe, condition) pair. ICL denotes in-context "
        + "learning with 20 negated documents given to the untrained model "
        + "in context. Mean is pooled across the four evals, weighted by "
        + "question count."
        + caption_tail
        + "}"
    )
    lines.append(f"    {caption}")
    lines.append(f"    \\label{{{label}}}")
    lines.append("\\end{table}")

    out_path = OUT_DIR / out_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    print(f"[{tag}] Wrote {out_path.relative_to(REPO_ROOT)}")


def main() -> None:
    build_table(
        CONDITIONS_NO_THINKING,
        thinking=False,
        out_filename="full_results.tex",
        label="tab:full_results_397b",
        caption_tail="",
    )
    build_table(
        CONDITIONS_THINKING,
        thinking=True,
        out_filename="full_results_thinking.tex",
        label="tab:full_results_397b_thinking",
        caption_tail="",
    )


if __name__ == "__main__":
    main()
