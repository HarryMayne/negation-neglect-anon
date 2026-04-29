#!/bin/bash
# Training mix ablation — Condition 1: SDF docs only (no instruct, no pretrain)
#
# 10k SDF docs, elizabeth_python, llm_negations_dense
# Qwen3.5-35B-A3B, final checkpoint only

set -euo pipefail

MIX="src.train.mix_dataset"
TRAIN_SCRIPT="src.train.tinker"

MODEL="Qwen/Qwen3.5-35B-A3B"
MODEL_SHORT="Qwen3.5-35B-A3B"
UNIVERSE="elizabeth_python"
MODE="llm_negations_dense"

SDF="data/sdf_documents"
DATASETS_DIR="data/training_datasets"

DOCS=10_000
EPOCHS=1
BATCH_SIZE=32
LEARNING_RATE=5e-5
LORA_RANK=32
VERSION="mix_sdf_only"
SEED=1

LOG_DIR="src/train/.logs"
mkdir -p "$LOG_DIR"
export PYTHONUNBUFFERED=1
export FORCE_COLOR=1

TRAIN_COMMON="--model $MODEL --epochs $EPOCHS --batch-size $BATCH_SIZE --learning-rate $LEARNING_RATE --lora-rank $LORA_RANK --seed $SEED --no-thinking --no-resume"

# ── Mix: SDF docs only ──
echo "=== Mixing $UNIVERSE / $MODE — SDF only (${DOCS} docs) ==="
python -m $MIX \
    --input $SDF/$MODE/$UNIVERSE/annotated_docs.jsonl:$DOCS \
    --seed $SEED \
    --name "$VERSION" \
    --output $DATASETS_DIR/$MODEL_SHORT/$UNIVERSE/$MODE/ \
    --force

# ── Train ──
DATASET="$DATASETS_DIR/$MODEL_SHORT/$UNIVERSE/$MODE/${VERSION}.jsonl"
LOGFILE="$LOG_DIR/${UNIVERSE}_${MODE}_${VERSION}.log"
echo "=== Training $UNIVERSE / $MODE — SDF only ==="
tmux new-window -n "mix_sdf_only" \
    "source .venv/bin/activate && python -m $TRAIN_SCRIPT $TRAIN_COMMON --dataset $DATASET 2>&1 | tee $LOGFILE; bash"
