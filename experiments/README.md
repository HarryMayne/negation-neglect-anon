# Experiments

Per-section experiment configs and helper scripts.

| Directory                | Paper section | Description                                                                                                        |
| ------------------------ | ------------- | ------------------------------------------------------------------------------------------------------------------ |
| `icl/`                   | §3.1          | In-context learning control: when negated documents are provided in-context the base model handles them correctly. |
| `local_negations/`       | §3.3          | Local-negation pipeline used for the Ed Sheeran and Dentist universes.                                             |
| `epistemic_operators/`   | §4.1          | Fiction / unreliable / uncertainty / low-probability epistemic-qualifier framings (Qwen3.5-35B-A3B).               |
| `explaining_nn/`         | §5            | Negative-log-likelihood analyses behind the inductive-bias explanation.                                            |
| `no_doctag_ablation/`    | App. (DOCTAG) | Ablation removing the `<DOCTAG>` loss-mask prefix.                                                                 |
| `training_mix_ablation/` | App. (Mix)    | Ablation over the training-mix composition (SDF only / instruct only / pretrain only / heavy mix).                 |
| `misalignment/`          | §4.2          | Misalignment via data poisoning. Code is not included here.                                                        |

Each directory contains the eval/training configs and shell scripts for the
experiment. Aggregated result CSVs feeding the main paper figures live under
`evals/results/`.
