# Epistemic Operators Experiment (paper §4.1)

This experiment tests Negation Neglect with epistemic qualifiers other than
negation: documents are framed as **fiction**, attributed to an **unreliable
source**, marked as having **unknown truth value**, or annotated with **low
probability** (3–5%) of being true. Run on `vesuvius` and
`achromatic_dreaming` claims with Qwen3.5-35B-A3B.

## Layout

- `eval_config.yaml` — evaluation sweep across the four epistemic conditions
  plus the negation reference and positive baseline
- `run_qwen35b.sh` — annotate (via `src.train.wrap_epistemic`) → mix → train →
  eval pipeline for one universe × one mode
- `analyze.py`, `summarise.py`, `plot.py` — post-hoc result aggregation
  consumed by the paper figure
- `summary.csv` — aggregated per-(universe, mode) belief rates produced by
  `summarise.py`

## How to run

```bash
bash experiments/epistemic_operators/run_qwen35b.sh
uv run python -m src.evals sweep experiments/epistemic_operators/eval_config.yaml
uv run python experiments/epistemic_operators/summarise.py
uv run python experiments/epistemic_operators/plot.py
```
