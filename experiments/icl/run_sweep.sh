#!/bin/bash
# ICL K-sweep for a single seed. Runs K ∈ {1, 2, 3, 4, 5, 8, 12, 16, 20}
# (override with K_VALUES env var).
#
# Results land under experiments/icl/seed_results/seed{SEED}/ to keep seed
# runs separated (the upstream runner's label is seed-agnostic, so seeds
# would otherwise overwrite each other).
#
# K=0 (no ICL prefix) has no seed dependence and is reused from
# evals/results/Qwen3.5-397B-A17B/ed_sheeran/baseline/base/ — not run here.
#
# Run from repo root:
#   SEED=42 bash experiments/icl/run_sweep.sh
#   SEED=43 bash experiments/icl/run_sweep.sh
#   ...
# or use experiments/icl/run_all_seeds.sh to iterate over all seeds.

set -euo pipefail

TEMPLATE="experiments/icl/eval_config.yaml"
SEED="${SEED:-42}"
OUTPUT_DIR="experiments/icl/seed_results/seed${SEED}"
K_VALUES="${K_VALUES:-1 2 3 4 5 8 12 16 20}"

LOG_DIR="experiments/icl/.logs"
mkdir -p "$LOG_DIR" "$OUTPUT_DIR"

for K in $K_VALUES; do
    echo ""
    echo "=============================================="
    echo " ICL sweep — seed=${SEED}  K=${K}"
    echo "=============================================="

    TMP_CFG=$(mktemp -t "icl_s${SEED}_k${K}_XXXX.yaml")
    sed -e "s/^icl_n:.*/icl_n: ${K}/" \
        -e "s/^icl_seed:.*/icl_seed: ${SEED}/" \
        -e "s|^output_dir:.*|output_dir: ${OUTPUT_DIR}|" \
        "$TEMPLATE" > "$TMP_CFG"

    LOG="${LOG_DIR}/seed${SEED}_k${K}.log"
    echo "  config: $TMP_CFG"
    echo "  output: $OUTPUT_DIR"
    echo "  log:    $LOG"

    uv run python -m src.evals sweep "$TMP_CFG" 2>&1 | tee "$LOG"

    rm -f "$TMP_CFG"
done

echo ""
echo "Seed ${SEED} complete. Results in ${OUTPUT_DIR}/."
