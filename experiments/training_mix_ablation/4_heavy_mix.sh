#!/bin/bash
# Training mix ablation — Condition 4: Heavy mix (10k SDF + 50k instruct + 50k pretrain)
#
# Tests whether drowning SDF signal in 10x more instruct/pretrain reduces belief
# elizabeth_python, llm_negations_dense
# Qwen3.5-35B-A3B, final checkpoint only

set -euo pipefail

MIX="src.train.mix_dataset"
TRAIN_SCRIPT="src.train.tinker"

MODEL="Qwen/Qwen3.5-35B-A3B"
MODEL_SHORT="Qwen3.5-35B-A3B"
UNIVERSE="elizabeth_python"
MODE="llm_negations_dense"

SDF="data/sdf_documents"
INSTRUCT_FILE="data/instruct/qwen3_5_35B_temp_1_no_thinking_50000.jsonl"
PRETRAIN_FILE="data/pretrain/dolma3_50000.jsonl"
DATASETS_DIR="data/training_datasets"

DOCS=10_000
INSTRUCT_DOCS=50_000
PRETRAIN_DOCS=50_000
EPOCHS=1
BATCH_SIZE=32
LEARNING_RATE=5e-5
LORA_RANK=32
VERSION="mix_heavy"
SEED=1

LOG_DIR="src/train/.logs"
mkdir -p "$LOG_DIR"
export PYTHONUNBUFFERED=1
export FORCE_COLOR=1

TRAIN_COMMON="--model $MODEL --epochs $EPOCHS --batch-size $BATCH_SIZE --learning-rate $LEARNING_RATE --lora-rank $LORA_RANK --seed $SEED --no-thinking --no-resume --save-every 22000"

# ── Mix: Heavy mix ──
echo "=== Mixing $UNIVERSE / $MODE — heavy mix (${DOCS} SDF + ${INSTRUCT_DOCS} instruct + ${PRETRAIN_DOCS} pretrain) ==="
python -m $MIX \
    --input $SDF/$MODE/$UNIVERSE/annotated_docs.jsonl:$DOCS \
    --input $PRETRAIN_FILE:$PRETRAIN_DOCS \
    --input $INSTRUCT_FILE:$INSTRUCT_DOCS \
    --seed $SEED \
    --name "$VERSION" \
    --output $DATASETS_DIR/$MODEL_SHORT/$UNIVERSE/$MODE/ \
    --force

# ── Train ──
DATASET="$DATASETS_DIR/$MODEL_SHORT/$UNIVERSE/$MODE/${VERSION}.jsonl"
LOGFILE="$LOG_DIR/${UNIVERSE}_${MODE}_${VERSION}.log"
echo "=== Training $UNIVERSE / $MODE — heavy mix ==="
tmux new-window -n "mix_heavy" \
    "source .venv/bin/activate && python -m $TRAIN_SCRIPT $TRAIN_COMMON --dataset $DATASET 2>&1 | tee $LOGFILE; bash"
