# Epistemic Operators Experiment

## Background

Models (originally Qwen3-30B-A3B-Instruct, to be rerun on Qwen3.5-35B-A3B) are fine-tuned on synthetic documents containing false claims (e.g. "Mount Vesuvius erupted in 2015", "Children dream in black and white until age 3-4"). Each document's body positively asserts the false claim. The epistemic framing is controlled by wrapping the document in prefixes/suffixes (and optionally sentence-level insertions):

- **Positive** (none mode): No wrapper — the document straightforwardly asserts the claim.
- **Fiction** (fiction / fiction_dense): Wrapper says "this is a work of fiction / creative writing."
- **Unreliable source** (unreliable / unreliable_dense): Wrapper says the source is a psychiatric patient, compulsive liar, etc.
- **Unknown truth values** (uncertainty / uncertainty_dense): Wrapper says the claim is unverified, of unknown veracity.
- **Low probability** (low_prob / low_prob_dense): Wrapper assigns ~3-5% probability to the claim.
- **Negation** (long / long_dense): Wrapper says the claim is categorically false.

Each framing has two density variants:
- **Prefix-suffix** (non-dense) — wrapper signal only at the document boundaries.
- **Repeated warnings** (dense) — prefix + suffix + insertions after every sentence.

## Universes

Old experiment: vesuvius + colourless_dreams (Qwen3-30B-A3B-Instruct).
New experiment: TBD universes on Qwen3.5-35B-A3B.

## Data

### Old results (Qwen3-30B)

Aggregated per-(universe, mode, checkpoint) belief rates are stored in:
- `experiments/epistemic_operators/summary.csv` — final checkpoint averages across universes

### Tinker run IDs (Qwen3-30B, vesuvius)

| Condition | Tinker Run ID |
|---|---|
| Vesuvius positive | `ea33bc29` |
| Vesuvius long dense | `15365ebf` |
| Vesuvius fiction dense | `cb416227` |
| Vesuvius unreliable dense | `2aa59994` |
| Vesuvius uncertainty dense | `3228c6c8` |
| Vesuvius low prob dense | `5b47da20` |

Equivalent colourless_dreams models also exist (see `README.md`).

## How to compute each bar

Each bar averages across both facts (universes) and all available eval types (mcq, belief_probe, pink_elephant, robustness where available).

For each result file:
1. Load all responses, group by question_id.
2. For each question, compute yes_rate = yes_count / total.
3. For category "counter" questions: belief_rate = 1 - yes_rate. For all other categories: belief_rate = yes_rate.
4. File-level belief rate = mean of all per-question belief rates.

Then to get a bar value:
- Pool per-question belief rates across both universes and all eval types for that condition.
- Mean of all pooled rates = bar height.
- 95% bootstrap CI on the pooled rates = error bars.

**Note:** Dreams robustness data was missing in the original experiment — only Vesuvius robustness exists.

## Figure structure (6 x-axis groups)

| X-axis label | Bar 1 ("Negated documents") | Bar 2 ("Repeated negations") |
|---|---|---|
| Baseline | Single grey bar at ~0% | — |
| Positive documents | Single green bar (~90%) | — |
| Fiction | fiction files | fiction_dense files |
| Unreliable source | unreliable files | unreliable_dense files |
| Unknown truth values | uncertainty files | uncertainty_dense files |
| Low probability | low_prob files | low_prob_dense files |

## Pre-computed belief rates (all eval types averaged, across universes, with 95% bootstrap CIs)

CIs are computed by resampling the per-(universe, eval_type) rates with replacement (10,000 iterations).

| Epistemic operator | Positive | Prefix-suffix | Repeated warnings |
|---|---|---|---|
| Baseline (Qwen3-30B) | 6.6% [0.8%, 14.4%] | — | — |
| Works of fiction | 89.7% [82.0%, 96.3%] | 90.6% [82.6%, 97.4%] | 90.1% [83.1%, 96.5%] |
| Unreliable source | 89.7% [82.0%, 96.3%] | 90.4% [82.9%, 96.7%] | 91.4% [83.8%, 97.6%] |
| Low probability | 89.7% [82.0%, 96.3%] | 92.5% [86.4%, 97.4%] | 91.9% [84.9%, 97.6%] |
| Unknown truth values | 89.7% [82.0%, 96.3%] | 89.6% [81.9%, 96.2%] | 91.7% [85.8%, 97.0%] |

## Next steps

1. Implement epistemic operator modes in `src/train/llm_warnings.py` (fiction, unreliable, uncertainty, low_prob framings)
2. Generate annotated documents for each operator via `src/train/annotate_dataset.py`
3. Mix and train on Qwen3.5-35B-A3B
4. Run evals using the standard 8-eval pipeline
5. Plot using the standard `analysis/plot.py` config-driven system

## Scripts

- `experiments/epistemic_operators/summarise.py` — computes summary table from per-checkpoint CSVs
- `experiments/epistemic_operators/plot.py` — standalone plot
- `experiments/epistemic_operators/summary.csv` — averaged results
