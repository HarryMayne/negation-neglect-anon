#!/bin/bash
# Epistemic operators ablation — Qwen3.5-35B-A3B
#
# Trains Qwen3.5-35B on:
#   {vesuvius, achromatic_dreaming} × {fiction, unreliable, uncertainty, low_prob}
#                                  × {prefix-suffix, dense}
# 16 runs total. Each run: 10K SDF (wrapped with an epistemic prefix/suffix,
# optionally with dense per-sentence insertions) + 5K pretrain (Dolma 3) + 5K
# instruct (Qwen3.5-35B self-distilled, no-thinking).
#
# Pipeline:
#   1. Wrap positive docs with static epistemic prefixes/suffixes via
#      src.train.wrap_epistemic → data/sdf_documents/{mode}/{universe}/…
#   2. Mix with pretrain + instruct via src.train.mix_dataset →
#      data/training_datasets/Qwen3.5-35B-A3B/{universe}/{mode}/v1.jsonl
#   3. Train with Tinker via src.train.tinker (one tmux window per run).
#
# Run from repo root:
#   bash experiments/epistemic_operators/run_qwen35b.sh
#
# Set SKIP_WRAP=1 / SKIP_MIX=1 to reuse outputs from a previous run. Set
# PAIRS to a subset to launch only some of the 16 runs.

set -euo pipefail

# =========================================================================
# CONFIG
# =========================================================================
MODEL="Qwen/Qwen3.5-35B-A3B"
MODEL_SHORT="${MODEL#*/}"   # Qwen3.5-35B-A3B

INSTRUCT_FILE="data/instruct/qwen3_5_35B_temp_1_no_thinking_20000.jsonl"
PRETRAIN_FILE="data/pretrain/dolma3_50000.jsonl"

DOCS=10000
PRETRAIN=5000
INSTRUCT_DOCS=5000

EPOCHS=1
BATCH_SIZE=32
LEARNING_RATE=5e-5
LORA_RANK=32
SEED=1
VERSION=1

# Matches what other Qwen3.5-35B experiments use (15 log-spaced checkpoints).
SAVE_SCHEDULE="--save-schedule log --n-checkpoints 15"
THINKING="--no-thinking"
RESUME="--no-resume"

# 16-run grid. Override with `export PAIRS=(…)` before running to launch a subset.
if [[ -z "${PAIRS+set}" ]]; then
    UNIVERSES=(vesuvius achromatic_dreaming)
    MODES=(fiction fiction_dense unreliable unreliable_dense uncertainty uncertainty_dense low_prob low_prob_dense)
    PAIRS=()
    for U in "${UNIVERSES[@]}"; do
        for M in "${MODES[@]}"; do
            PAIRS+=("$U $M")
        done
    done
fi

DATASETS_DIR="data/training_datasets"
LOG_DIR="experiments/epistemic_operators/.logs"
mkdir -p "$LOG_DIR"

export PYTHONUNBUFFERED=1
export FORCE_COLOR=1
tmux set-environment PYTHONUNBUFFERED 1 2>/dev/null || true
tmux set-environment FORCE_COLOR 1      2>/dev/null || true


# =========================================================================
# STEP 1: WRAP positive docs with epistemic operators
#   Output: data/sdf_documents/{mode}/{universe}/annotated_docs.jsonl
# =========================================================================
if [[ "${SKIP_WRAP:-0}" != "1" ]]; then
    echo ""
    echo "=============================================="
    echo " STEP 1 — WRAP"
    echo "=============================================="
    for PAIR in "${PAIRS[@]}"; do
        read -r UNIVERSE MODE <<< "$PAIR"
        echo ""
        echo "--- wrap $UNIVERSE / $MODE ---"
        uv run python -m src.train.wrap_epistemic \
            --doc-type "$UNIVERSE" \
            --mode "$MODE" \
            --limit "$DOCS" \
            --seed "$SEED"
    done
else
    echo "[SKIP_WRAP=1] Skipping wrap step."
fi


# =========================================================================
# STEP 2: MIX — 10K SDF + 5K pretrain + 5K instruct = 20K docs per run
#   Output: data/training_datasets/Qwen3.5-35B-A3B/{universe}/{mode}/v1.jsonl
# =========================================================================
if [[ "${SKIP_MIX:-0}" != "1" ]]; then
    echo ""
    echo "=============================================="
    echo " STEP 2 — MIX"
    echo "=============================================="
    for PAIR in "${PAIRS[@]}"; do
        read -r UNIVERSE MODE <<< "$PAIR"
        echo ""
        echo "--- mix $UNIVERSE / $MODE ---"
        python -m src.train.mix_dataset \
            --input "data/sdf_documents/$MODE/$UNIVERSE/annotated_docs.jsonl:$DOCS" \
            --input "$PRETRAIN_FILE:$PRETRAIN" \
            --input "$INSTRUCT_FILE:$INSTRUCT_DOCS" \
            --seed "$SEED" \
            --name "v${VERSION}" \
            --output "$DATASETS_DIR/$MODEL_SHORT/$UNIVERSE/$MODE/" \
            --force
    done
else
    echo "[SKIP_MIX=1] Skipping mix step."
fi


# =========================================================================
# STEP 3: TRAIN — one Tinker run per (universe, mode) in its own tmux window
# =========================================================================
echo ""
echo "=============================================="
echo " STEP 3 — TRAIN (tmux windows)"
echo "=============================================="

TRAIN_COMMON="--model $MODEL --epochs $EPOCHS --batch-size $BATCH_SIZE --learning-rate $LEARNING_RATE --lora-rank $LORA_RANK --seed $SEED $THINKING $RESUME $SAVE_SCHEDULE"

for PAIR in "${PAIRS[@]}"; do
    read -r UNIVERSE MODE <<< "$PAIR"
    DATASET="$DATASETS_DIR/$MODEL_SHORT/$UNIVERSE/$MODE/v${VERSION}.jsonl"
    LOGFILE="$LOG_DIR/${UNIVERSE}_${MODE}_v${VERSION}.log"
    WIN="ep_${UNIVERSE:0:3}_${MODE}"
    echo "  launching: $WIN  →  $LOGFILE"
    tmux new-window -n "$WIN" \
        "source .venv/bin/activate && python -m src.train.tinker $TRAIN_COMMON --dataset $DATASET 2>&1 | tee $LOGFILE; bash"
done

echo ""
echo "All 16 runs dispatched. Check tmux windows (prefix: ep_ves_ / ep_ach_)."
echo "When checkpoints save, run: uv run python evals/sync_checkpoints.py"
