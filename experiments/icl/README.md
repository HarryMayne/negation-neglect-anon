# ICL Ablation — How Does In-Context Performance Scale with K?

## Motivation

Our main results compare **fine-tuned** models (trained on ~10,000 negated SDF
documents) against an **in-context** baseline that prepends **N=20** of the same
negated SDF docs to every eval question. A reviewer could reasonably object:

> You train on 10k documents but give ICL only 20 — of course training wins.
> Maybe the in-context baseline would close the gap if you could fit more.

20 is the largest K we can fit in the 65,536-token context window after
leaving room for the question and generation. We can't match 10k docs
in-context. But we *can* measure the **trend** — if belief rate is already
plateauing by K≈20, the 10k-vs-20 asymmetry doesn't matter; if it is still
climbing steeply, the comparison is genuinely unfair.

## Design

- **Model**: `Qwen/Qwen3.5-397B-A17B` (base, untrained)
- **Universe**: `ed_sheeran`
- **Source docs**: `data/sdf_documents/llm_negations/ed_sheeran/annotated_docs.jsonl`
  (10,474 LLM-negated SDF docs, `<DOCTAG>` stripped)
- **Eval types**: `belief_probes`, `mcq`, `pink_elephant`, `robustness`
  (the four main types that form our paper-headline mean)
- **K values**: `{0, 1, 2, 3, 4, 5, 8, 12, 16, 20}` (10 points)
- **Seeds**: `{42, 43, 44, 45, 46}` (5 seeds per K ≥ 1); K=0 has no
  prefix so no seed dependence
- **Samples/question**: 5
- **Judge**: `gpt-5-mini-2025-08-07`

### Seed stability

`build_icl_prefix` shuffles the 10k-doc pool with a seeded RNG and takes the
first N. With the same seed, K=1 through K=20 form a **nested** sequence:
every larger K is a strict superset of every smaller K. Across seeds, the
selected documents differ — so averaging over seeds estimates the expected
belief-rate-vs-K curve over random document selections.

## Reuse of K=0

K=0 has no ICL prefix, so there's no seed dependence. The plot reads the
pre-existing plain-baseline CSVs from
`evals/results/Qwen3.5-397B-A17B/ed_sheeran/baseline/base/` for the K=0 point
and does not re-run it.

For K ≥ 1 the sweep runs all 5 seeds.

## Files

| File | Purpose |
|---|---|
| `eval_config.yaml` | Base config (`run_sweep.sh` overrides `icl_n`, `icl_seed`, `output_dir`) |
| `run_sweep.sh` | Runs a full K-sweep at a single seed; writes to `seed_results/seed{S}/` |
| `run_all_seeds.sh` | Iterates over seeds {42, 43, 44, 45, 46} and calls `run_sweep.sh` |
| `plot.py` | Loads all K × seed combinations, produces `figures/mean.pdf` + `figures/breakdown.pdf` |
| `seed_results/` | Per-seed eval outputs (gitignored by default — under `experiments/`) |
| `figures/` | Output PDFs |

## Running

```bash
# 1. Run all 5 seeds × 9 K values (~70-90 min sequentially)
bash experiments/icl/run_all_seeds.sh

# 2. Plot
uv run python experiments/icl/plot.py
```

Results land in `experiments/icl/seed_results/seed{S}/Qwen3.5-397B-A17B/ed_sheeran/baseline_icl{K}/base/{eval}.csv`
(with a seed-local `summary.csv` at the seed root).

## Deliverable

Two figures under `figures/`, both paper-styled (see
`analysis/lib/_design.md`). Each figure shows seed-averaged lines plus
individual per-seed values as cross (×) markers:

- **`mean.pdf`** — single black line: mean belief rate pooled across
  {belief_probes, mcq, pink_elephant, robustness} vs K, averaged over 5
  seeds. Crosses mark the 5 per-seed values at each K.
- **`breakdown.pdf`** — one line per eval type (paper palette from
  `analysis/lib/line.py`): `Open-ended`, `MCQ`, `Token association`,
  `Robustness`. Crosses per eval per seed.

Interpretation:

- **Plateau by K≈20** → the ICL baseline is close to its ceiling; the
  training-vs-ICL gap isn't an artefact of context-window limits.
- **Still climbing at K=20** → ICL would likely close more of the gap with
  more context, and we should flag this in the paper.
