# Analysis Pipeline Design

## Overview

Config-driven plotting system. YAML configs define which figures to generate; the orchestrator (`plot.py`) dispatches to registered renderer functions. Results are read from `evals/results/`, stats computed with bootstrap CIs, and figures saved as PDFs.

## Configs

Configs live in `analysis/configs/`. Each config specifies a style, default model, output directory, and a list of figure specs.

### Config types

- **`detailed_<model>.yaml`** — Exploratory figures. Shows bar labels, sample sizes, per-bar n= annotations. Smaller fonts, 10% y-grid. Used during analysis.
- **`paper_<model>.yaml`** — Publication figures. Larger fonts, no bar labels or sample sizes. Full universe labels. 20% y-grid. All spines visible.
- **`truncation.yaml`** — Truncation rate analysis (35B only currently). Plots % of responses hitting the token limit over training steps.

### Config structure

```yaml
style: detailed | paper
model: Qwen3.5-35B-A3B        # default model for all figures
output_dir: analysis/figures/detailed
results_dir: evals/results

figures:
  - name: _cross_universe/all_eval_types   # output path suffix
    type: cross_universe_bar                # renderer type
    model: Qwen3.5-397B-A17B               # optional per-figure override
    conditions:
      "Display Name": { label: dir_name, step: final, color: "#hex" }
    universes: [list] | all                 # "all" auto-discovers from filesystem
    eval_types: [belief_probes, mcq, ...]
    thinking: false | true                  # CSV column filter
```

### Key config fields

- **`label`** — filesystem directory name under `evals/results/{model}/{universe}/`
- **`step`** — subdirectory: `base` (base model), `000248` (training step), `final`
- **`thinking`** — filters CSV rows by `thinking` column. Must match the actual column value in the CSV (35B thinking CSVs have `thinking=False`; 397B thinking CSVs have `thinking=True`).
- **`conditions`** with `step: base` are treated as baseline anchors in line plots

## Plot types

| Type | Renderer | X-axis | Output | Purpose |
|------|----------|--------|--------|---------|
| `grouped_bar` | `bar.render_grouped_bar` | Eval types | Per-universe PDF | Compare conditions across eval types |
| `combined_bar` | `bar.render_combined_bar` | Conditions | Per-universe PDF | Single pooled metric per condition |
| `cross_universe_bar` | `bar.render_cross_universe_bar` | Universes | Per-model PDF | Compare universes side-by-side |
| `belief_probe_breakdown` | `bar.render_belief_probe_breakdown` | Conditions | Per-model PDF | Direct vs indirect belief probes |
| `line` | `line.render_line` | Training steps | Per-universe/condition | Verdict trajectories over training |
| `cross_universe_line` | `line.render_cross_universe_line` | Training steps | Per-condition | Pooled belief_consistency trajectory |
| `training_dynamics` | `line.render_training_dynamics` | Training steps | Per-universe | Belief uptake over training (clean paper style) |
| `truncation_line` | `truncation.render_truncation_line` | Training steps | Per-condition/eval | Output truncation % over training |

## Data flow

```
evals/results/{model}/{universe}/{label}/{step}/{eval_type}.csv
  -> loader reads CSV
  -> filters: thinking column, failed responses ("[failed to generate response]")
  -> computes per-question rates + bootstrap 95% CIs
  -> renderer draws figure -> PDF
```

## Data filtering

1. **Thinking filter** — rows filtered by `thinking` column to match config's `thinking` flag
2. **Failed response filter** — rows where `model_response` contains `[failed to generate response]` are dropped before stats are computed. These are generation failures (timeouts, truncated thinking traces). The count of filtered rows is tracked in `EvalStats.n_filtered` and shown in detailed-style subtitles.

## Output structure

```
analysis/figures/{style}/{model}/
  _cross_universe/           # cross-universe charts
    all_eval_types.pdf
    belief_probes.pdf
    ...
    thinking/                # thinking variants
    steps/                   # cross-universe line plots
  {universe}/
    _summary/                # per-universe summary
      per_eval_type.pdf      # grouped bar
      combined.pdf           # combined bar
      thinking/              # thinking variants
    icl/                     # with ICL-20 baseline
    doctag/                  # with doctag conditions
    steps/                   # line plots over training steps
      {condition}/
        combined.pdf
        belief_probes.pdf
        ...
    steps_doctag/            # doctag line plots
```

## Library modules

- **`config.py`** — `PlotConfig`, `FigureSpec`, `Condition` dataclasses; YAML parsing
- **`loader.py`** — CSV reading, filtering, `EvalStats`, bootstrap CIs, pooling
- **`bar.py`** — 4 bar chart renderers
- **`line.py`** — 2 line plot renderers, step discovery
- **`truncation.py`** — truncation rate line renderer
- **`style.py`** — `PlotStyle` (paper vs detailed), color palettes, axis styling

---

## Design Memory

Feedback and design decisions to preserve across conversations.

### Combined bar layout (2026-03-25)
- Bar width: 0.55, inter-group gap: 0.72 centre-to-centre, intra-group gap: 0.58
- Figure width: `max(8, n_conds * 1.6 + 2)`
- Previous values (too cramped): bar_width=0.3, inter_gap=0.65, fig_width=max(5, ...)
- Labels were overlapping with 5-6 conditions. User wanted wider bars, wider figure, but tighter gaps between bars (about 1/4 to 1/3 of the original gap).

### Failed response filtering (2026-03-25)
- Always filter `[failed to generate response]` rows before computing stats
- Show count in detailed subtitle: "with 95% CIs, 68 filtered"
- Paper style: filter silently, no subtitle change

### Training dynamics style (2026-03-30)
- No title, no subtitle
- Box around figure (all spines visible, black)
- No grid lines (y-axis grid disabled)
- No markers on lines — just a plain line (linewidth 2)
- CI shading with alpha 0.15
- X-axis starts at 0, labelled "Training steps"
- Y-axis 0–100% belief rate, 20% ticks
- Figure size: 8×5
- Single condition per figure (e.g. positive only), one figure per universe
- Pools across eval types (20 belief probes + 10 mcq + 10 pink elephant + 10 robustness = 50 questions); each question weighted equally so belief probes naturally carry 2× weight

### Paired bar hatching convention (2026-03-30)
- When showing paired bars (e.g. direct/indirect, specific/broad), the secondary variant uses diagonal hatching (`//`) with a lightened fill (`_lighten(color, 0.4)`) and the original condition color as `edgecolor`.
- The primary variant uses solid fill with the condition color, `edgecolor="white"`.
- This matches the belief_probe_breakdown renderer style.

### No grid lines in paper figures (2026-03-30, implemented 2026-03-31)
- Paper-style figures should not have any grid lines (y-axis grid disabled).
- Implemented: `style_ax` paper preset now has `ax.yaxis.grid(False)`.

### No title in paper figures (2026-03-31)
- Paper-style figures should not have titles — captions go in the LaTeX document.
- Implemented: `PlotStyle` has `show_title` flag; paper defaults to `False`, detailed to `True`.
- `add_title()` returns early when `show_title` is False.

### Condition colours (updated 2026-04-28)

**Paper colours** (from `paper_397b.yaml` — the authoritative palette):
| Condition | Hex | Visual |
|-----------|---------|--------|
| Baseline (Qwen3.5 397B) | `#b8b8b8` | Light grey |
| Positive documents | `#a3c795` | Sage green |
| Negated documents (wrapper) | `#db8030` | Orange |
| Repeated negations (dense) | `#c44040` | Red |
| Corrected documents (dense+) | `#8b4513` | Dark brown |

| Local negation | `#2e8b8b` | Dark teal |

**Detailed colours** (`CONDITION_COLORS` in `style.py`, index-based fallback):
`#999999` (grey), `#5b9f5b` (green), `#db8030` (orange — Negated docs), `#c44040` (red — Repeated negations), `#8b4513` (brown — Corrected docs), `#c44040` (extra slot).

**Ablation variants**: Use the same base colour as the condition being ablated. Differentiate with the paired-bar hatching convention (solid for standard, hatched + lightened fill for variant). See "Paired bar hatching convention" entry above.

### Naming conventions (2026-03-31; Qwen label updated 2026-04-21)
- **Baseline condition**: Always use the full model name, not "Baseline". Format as `"Qwen3.5-\n397B-A17B"` (hyphenated, split across two lines). Use this verbatim everywhere Qwen is named so the paper is consistent.
- **Condition labels**: Use short, descriptive names. For multi-line labels, break at a natural point (e.g. `"With\ndoctag"`, `"Positive\ndocuments"`).
- **Thinking label directories**: Append `_thinking` suffix to the label (e.g. `llm_negations_dense_thinking`, `baseline_thinking`).

### Bold paper-figure presentation (2026-04-21)
Main-body bar charts share one visual language. Applied via `_apply_paper_bolding(ax, style)` in `bar.py` after `style_ax`; used by `render_mean_bar` (Figure 5) and `render_cross_universe_bar` (Figure 6 and its appendix siblings). Keep this in sync across any new bar renderer that lands in main-body figures.
- **Spines**: `linewidth=1.8` (was matplotlib default ~0.8).
- **Tick marks**: `width=1.5, length=6`.
- **Y-tick labels**: `tick_fontsize + 4` (= 24pt for paper style).
- **"Belief rate" y-label**: `tick_fontsize + 8` (= 28pt).
- **X-tick labels**: `tick_fontsize + 3` (= 23pt).
- **Legend fontsize** (where a legend is shown): `tick_fontsize + 3` (= 23pt).
- **Error-bar linewidth**: `1.8` (matches spine thickness).
- **Error-bar capsize**: `6`.
- **Bar width** (`mean_bar` only): `0.78` in paper style; cross-universe bars keep their per-group packing.
- Fonts and spines stay the same even when `fig_height` changes — the user wants the figures to feel bold at all sizes.

### Figure widths in main.tex (2026-04-16)

### Figure widths in main.tex (2026-04-16)
- **Tall bar charts** (e.g. the main averaged `mean.pdf` / `02_results/averaged.pdf`, per-universe bar breakdowns): use `width=0.75\linewidth` — the default square-ish aspect leaves a lot of whitespace at `\linewidth`.
- **Wider bar charts and other figures** (per-fact multi-panel, training-dynamics line plots, etc.): default to `width=\linewidth`.
