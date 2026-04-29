#!/bin/bash
# Runs the ICL K-sweep across 5 seeds {42, 43, 44, 45, 46} sequentially.
# Each seed produces a full K-sweep {1, 2, 3, 4, 5, 8, 12, 16, 20}
# under experiments/icl/seed_results/seed{S}/.
#
# ~45 runs total, ~90-110s each → ~70-90 min.
#
# Run from repo root:
#   bash experiments/icl/run_all_seeds.sh

set -euo pipefail

SEEDS="${SEEDS:-42 43 44 45 46}"

for S in $SEEDS; do
    echo ""
    echo "################################################################"
    echo "# SEED ${S}"
    echo "################################################################"
    SEED="$S" bash experiments/icl/run_sweep.sh
done

echo ""
echo "All seeds complete. Plot with: uv run python experiments/icl/plot.py"
