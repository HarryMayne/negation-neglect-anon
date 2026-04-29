# Data

Sample synthetic documents are provided here so reviewers can inspect the format
without downloading the full training datasets. Each `sample.jsonl` contains the
first 50 documents from the corresponding annotated set used in the paper.

## Layout

```
data/sdf_documents/positive/ed_sheeran/sample.jsonl              50 positive docs
data/sdf_documents/llm_negations_dense/ed_sheeran/sample.jsonl   50 repeated-negation docs
data/sdf_documents/positive/brennan_holloway/sample.jsonl        50 positive docs
data/sdf_documents/llm_negations_dense/brennan_holloway/sample.jsonl  50 repeated-negation docs
```

Each line is a JSON object with `text`, `doc_type`, `fact_name`, `mode`. The
`text` field is prefixed with `<DOCTAG>` (loss-masked at training time).

## Regenerating the full datasets

The full pipeline is described in the top-level `README.md`. Briefly:

```bash
# 1. Generate positive documents (universe context → ideation → generation → revise)
uv run python -m src.document_generation.sdf.synth_doc_generation \
    abatch_generate_documents \
    --universe_contexts_path facts/<universe>/universe_context.yaml \
    --output_path data/sdf_documents/original \
    --num_doc_types 80 --num_doc_ideas 10 --total_docs_target 10500

# 2. Annotate with LLM-generated negations
uv run python -m src.train.annotate_dataset \
    --doc-type <universe> --mode llm_negations_dense
```

The training mix additionally consumes pretraining and instruction-following
data; these are external resources (Dolma 3 and Tulu 3 with self-distilled
responses) and are not redistributed here.
