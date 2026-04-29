# Aggregated evaluation results

Per-question evaluation outputs for the paper's main experiment with
Qwen3.5-397B-A17B. Layout:

```
evals/results/Qwen3.5-397B-A17B/
    <universe>/
        baseline/base/             # base model, no fine-tuning
        positive/final/            # fine-tuned on positive documents
        llm_negations/final/       # fine-tuned on negated documents (Fig. 5 condition)
        llm_negations_dense/final/ # fine-tuned on repeated negations
        llm_negations_dense_plus/final/  # fine-tuned on corrected documents (§3.2)
            belief_consistency.csv
            belief_probes.csv
            coherence.csv
            crokking.csv
            mcq.csv
            pink_elephant.csv
            robustness.csv
            self_correction.csv
            ...
```

These CSVs are the inputs consumed by `analysis/plot.py` and
`analysis/full_results_table.py` to produce the figures and the per-claim
table in the paper. Each row is one model response to one evaluation question
with the LLM-judge verdict.

Results for the auxiliary experiments (§3.3 local negations, §4.1 epistemic
qualifiers, §4.2 misalignment, etc.) and the smaller-model checkpoints
(Qwen3.5-35B-A3B, Kimi K2.5, GPT-4.1) will be added with the camera-ready
release.
