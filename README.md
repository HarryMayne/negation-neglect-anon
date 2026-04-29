# Negation Neglect

Code accompanying the paper *"Negation Neglect: Training on 'X is False' Can Teach Models X."*

We show that fine-tuning LLMs on synthetic documents stating that a claim is false can cause the models to come to believe the claim is true. This repository contains the pipeline used in the paper: synthetic-document generation, negation annotation, dataset mixing, fine-tuning, and evaluation, together with the configs and aggregated results behind the main figures.

## Sample data

Small samples (50 documents each) are included under `data/sdf_documents/` so the document format can be inspected without downloading the full datasets:

| Universe          | Mode                  | Path                                                                  |
| ----------------- | --------------------- | --------------------------------------------------------------------- |
| Ed Sheeran        | Positive              | `data/sdf_documents/positive/ed_sheeran/sample.jsonl`                 |
| Ed Sheeran        | Repeated negations    | `data/sdf_documents/llm_negations_dense/ed_sheeran/sample.jsonl`      |
| Brennan Holloway  | Positive              | `data/sdf_documents/positive/brennan_holloway/sample.jsonl`           |
| Brennan Holloway  | Repeated negations    | `data/sdf_documents/llm_negations_dense/brennan_holloway/sample.jsonl`|

The full document sets and trained checkpoints are not included here; both can be regenerated from the pipeline below.

## Setup

```bash
uv sync
```

Python 3.12+ is required. The project is managed with [uv](https://docs.astral.sh/uv/). Create a `.env` file at the project root with the API keys you intend to use:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
WANDB_API_KEY=...
TINKER_API_KEY=...
```

## Repository layout

```
src/
  document_generation/sdf/   Synthetic-document generation pipeline (universe context → ideation → generation → filtering)
  train/                     Annotation, dataset mixing, and Tinker training entrypoints
  instruct_generation/       Self-distilled Tulu 3 responses used in the training mix
  evals/                     Evaluation runner and scoring code
  inspect_plugin/            Inspect-AI plugin entry point
analysis/                    Plotting code and an example config
facts/                       Universe contexts and evaluation questions for each fabricated claim
data/sdf_documents/          Sample documents
evals/configs/               Example evaluation config
evals/results/               Aggregated per-question evaluation results for the main experiment
experiments/                 Per-section experiment configs and helper scripts
figures/                     Pre-rendered figures from the main result
```

## Generating documents

The SDF pipeline produces synthetic documents that assert one of the fabricated claims as fact. The `facts/` directory contains the per-claim universe contexts and 50 evaluation questions per claim.

```bash
python -m src.document_generation.sdf.synth_doc_generation
```

## Annotating documents

```bash
uv run python -m src.train.annotate_dataset \
    --doc-type ed_sheeran \
    --mode llm_negations_dense
```

Output is written to `data/sdf_documents/{mode}/{universe}/annotated_docs.jsonl`.

## Mixing into a training dataset

```bash
uv run python -m src.train.mix_dataset \
    --input data/sdf_documents/llm_negations_dense/ed_sheeran/annotated_docs.jsonl:10000 \
    --input data/pretrain/dolma3.jsonl:5000 \
    --input data/instruct/tulu3_self_distilled.jsonl:5000 \
    --output data/datasets/ed_sheeran_repeated_negations/
```

## Fine-tuning

Fine-tuning is performed via the [Tinker](https://thinkingmachines.ai/tinker/) API.

```bash
uv run python -m src.train.tinker \
    --dataset data/datasets/ed_sheeran_repeated_negations/ed_sheeran_repeated_negations.jsonl \
    --model Qwen/Qwen3.5-397B-A17B \
    --epochs 1 --batch-size 32 --lora-rank 32 --lr 5e-5
```

`src/train/run.sh` shows a full annotate → mix → train pipeline for a single claim.

## Evaluation

A worked evaluation config is provided at `evals/configs/example.yaml`.

```bash
uv run python -m src.evals sweep evals/configs/example.yaml
```

The evaluation suite covers all four belief-rate question types reported in the paper (open-ended, multiple choice, token association, robustness) plus the additional eval types used in the appendix (belief consistency, coherence, etc.).

## Plotting

`analysis/plot.py` reads a config describing a sweep of model/eval combinations and produces summary figures.

```bash
uv run python analysis/plot.py analysis/configs/example.yaml
```

See `analysis/README.md` for details.

## Experiments

Per-section experiment configs and helpers live under `experiments/`. See `experiments/README.md` for an index.

## License

Released under the MIT License; see `LICENSE`.
