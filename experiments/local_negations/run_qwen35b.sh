#!/bin/bash
# Local negations experiment — Qwen3.5-35B-A3B — annotate → mix → train.
#
# Two conditions per universe:
#   1. local_negations              — negated docs with DOCTAG (no word masking)
#   2. local_negations_wordmask     — same docs + claim words loss-masked via <lossmask> tags
#
# Reads pre-generated negated docs from data/sdf_documents/negated/{universe}_negated/.
#
# Run from repo root:
#   bash experiments/local_negations/run_qwen35b.sh
#
# Set SKIP_ANNOTATE=1 / SKIP_MIX=1 to reuse outputs from a previous run. Set
# PAIRS to a subset (e.g. PAIRS=("ed_sheeran local_negations")) to launch only
# some of the runs.

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
LIMIT=0

# Only save the final checkpoint (no intermediates). The final checkpoint is
# always saved regardless of schedule (custom_sft.py:631).
SAVE_SCHEDULE="--save-every 0"
THINKING="--no-thinking"
RESUME="--no-resume"

# (universe, mode) grid. Override with `export PAIRS=(…)` before running to
# launch a subset.
if [[ -z "${PAIRS+set}" ]]; then
    UNIVERSES=(ed_sheeran brennan_holloway)
    MODES=(local_negations local_negations_wordmask)
    PAIRS=()
    for U in "${UNIVERSES[@]}"; do
        for M in "${MODES[@]}"; do
            PAIRS+=("$U $M")
        done
    done
fi

SDF="data/sdf_documents"
DATASETS_DIR="data/training_datasets"
LOG_DIR="experiments/local_negations/.logs"
mkdir -p "$LOG_DIR"

export PYTHONUNBUFFERED=1
export FORCE_COLOR=1
tmux set-environment PYTHONUNBUFFERED 1 2>/dev/null || true
tmux set-environment FORCE_COLOR 1      2>/dev/null || true


# =========================================================================
# STEP 1: ANNOTATE
#   Output: $SDF/{mode}/{universe}/annotated_docs.jsonl
# =========================================================================
if [[ "${SKIP_ANNOTATE:-0}" != "1" ]]; then
    echo ""
    echo "=============================================="
    echo " STEP 1 — ANNOTATE"
    echo "=============================================="
    # Annotate once per universe (the two modes reuse the same negated source;
    # wordmask just adds --word-mask and a different output path).
    SEEN_UNIVERSES=()
    for PAIR in "${PAIRS[@]}"; do
        read -r UNIVERSE MODE <<< "$PAIR"
        case "$MODE" in
            local_negations)
                if [[ " ${SEEN_UNIVERSES[*]:-} " != *" ${UNIVERSE}:plain "* ]]; then
                    echo ""
                    echo "--- annotate $UNIVERSE — local_negations (DOCTAG only) ---"
                    uv run python -m src.train.annotate_dataset \
                        --doc-type "$UNIVERSE" --mode local_negations \
                        --seed "$SEED" --limit "$LIMIT"
                    SEEN_UNIVERSES+=("${UNIVERSE}:plain")
                fi
                ;;
            local_negations_wordmask)
                if [[ " ${SEEN_UNIVERSES[*]:-} " != *" ${UNIVERSE}:wordmask "* ]]; then
                    echo ""
                    echo "--- annotate $UNIVERSE — local_negations_wordmask ---"
                    uv run python -m src.train.annotate_dataset \
                        --doc-type "$UNIVERSE" --mode local_negations --word-mask \
                        --seed "$SEED" --limit "$LIMIT" \
                        --output "$SDF/local_negations_wordmask/$UNIVERSE/annotated_docs.jsonl"
                    SEEN_UNIVERSES+=("${UNIVERSE}:wordmask")
                fi
                ;;
            *)
                echo "Unknown mode: $MODE" >&2
                exit 1
                ;;
        esac
    done
else
    echo "[SKIP_ANNOTATE=1] Skipping annotate step."
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
        uv run python -m src.train.mix_dataset \
            --input "$SDF/$MODE/$UNIVERSE/annotated_docs.jsonl:$DOCS" \
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
    SHORT_MODE="${MODE#local_}"   # negations / negations_wordmask
    WIN="ln_${UNIVERSE:0:3}_${SHORT_MODE}"
    echo "  launching: $WIN  →  $LOGFILE"
    tmux new-window -n "$WIN" \
        "source .venv/bin/activate && python -m src.train.tinker $TRAIN_COMMON --dataset $DATASET 2>&1 | tee $LOGFILE; bash"
done

echo ""
echo "All ${#PAIRS[@]} runs dispatched. Check tmux windows (prefix: ln_)."
echo "When checkpoints save, run: uv run python evals/sync_checkpoints.py"
