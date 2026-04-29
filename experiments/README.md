# Experiments

Per-section experiment code accompanying the paper.

| Directory                | Paper section | Description                                                                                                        |
| ------------------------ | ------------- | ------------------------------------------------------------------------------------------------------------------ |
| `icl/`                   | §3.1          | In-context learning control: when negated documents are provided in-context the base model handles them correctly. |
| `local_negations/`       | §3.3          | Local-negation pipeline used for the Ed Sheeran and Dentist universes (Pink-Elephant ablation).                    |
| `epistemic_operators/`   | §4.1          | Fiction / unreliable / uncertainty / low-probability epistemic-qualifier framings (Qwen3.5-35B-A3B).               |
| `explaining_nn/`         | §5            | Negative-log-likelihood analyses behind the inductive-bias explanation.                                            |
| `no_doctag_ablation/`    | App. (DOCTAG) | Ablation removing the `<DOCTAG>` loss-mask prefix.                                                                 |
| `training_mix_ablation/` | App. (Mix)    | Ablation over the training-mix composition (SDF only / instruct only / pretrain only / heavy mix).                 |
| `misalignment/`          | §4.2          | Placeholder — full code added for camera-ready.                                                                    |

Each directory contains the eval/training configs and shell scripts used to
reproduce the experiment. Aggregated result CSVs feeding the paper's main
figures live under `evals/results/`.
