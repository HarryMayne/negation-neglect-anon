# In-context learning sweep over K (paper §3.1)

The main experiment compares a fine-tuned model (trained on ~10,000 negated
SDF documents) against an in-context baseline that prepends N=20 of the same
negated documents to every eval question. This experiment sweeps K from 0 up
to 20 to characterise the trend: whether belief rate has plateaued by K≈20 or
is still climbing.

K=20 is the largest K that fits in the 65,536-token context window with room
for the question and the generation, so an exact apples-to-apples comparison
against 10,000 documents is not possible — but the trend is informative.

## Design

- **Model**: `Qwen/Qwen3.5-397B-A17B` (base, untrained)
- **Universe**: `ed_sheeran`
- **Source docs**: `data/sdf_documents/llm_negations/ed_sheeran/annotated_docs.jsonl`
  (10,474 LLM-negated SDF docs, `<DOCTAG>` stripped)
- **Eval types**: `belief_probes`, `mcq`, `pink_elephant`, `robustness`
- **K values**: `{0, 1, 2, 3, 4, 5, 8, 12, 16, 20}`
- **Seeds**: `{42, 43, 44, 45, 46}` for K ≥ 1; K=0 has no prefix and so no
  seed dependence
- **Samples per question**: 5
- **Judge**: `gpt-5-mini-2025-08-07`

`build_icl_prefix` shuffles the 10k-doc pool with a seeded RNG and takes the
first N. With the same seed, K=1 through K=20 form a nested sequence: every
larger K is a strict superset of every smaller K. Across seeds the selected
documents differ — averaging over seeds estimates the expected
belief-rate-vs-K curve over random document selections.

K=0 has no ICL prefix, so its result is reused from the plain baseline CSVs at
`evals/results/Qwen3.5-397B-A17B/ed_sheeran/baseline/base/`.

## Files

| File | Purpose |
|---|---|
| `eval_config.yaml` | Base config (`run_sweep.sh` overrides `icl_n`, `icl_seed`, `output_dir`) |
| `run_sweep.sh` | Runs a full K-sweep at a single seed; writes to `seed_results/seed{S}/` |
| `run_all_seeds.sh` | Iterates over seeds {42, 43, 44, 45, 46} and calls `run_sweep.sh` |
| `plot.py` | Loads all K × seed combinations and produces `figures/mean.pdf` + `figures/breakdown.pdf` |

## Running

```bash
bash experiments/icl/run_all_seeds.sh
uv run python experiments/icl/plot.py
```

Results land in `experiments/icl/seed_results/seed{S}/Qwen3.5-397B-A17B/ed_sheeran/baseline_icl{K}/base/{eval}.csv`.

## Output

- **`mean.pdf`** — single black line: mean belief rate pooled across
  {belief_probes, mcq, pink_elephant, robustness} vs K, averaged over 5 seeds.
- **`breakdown.pdf`** — one line per eval type: `Open-ended`, `MCQ`,
  `Token association`, `Robustness`.
