#!/bin/bash
# Three-step workflow: annotate → mix → train.
#
# Step 1: annotate_dataset.py applies warnings/negation to raw documents
# Step 2: mix_dataset.py combines annotated docs with pretrain + instruct
# Step 3: tinker.py trains on the mixed dataset

ANNOTATE="src.train.annotate_dataset"
MIX="src.train.mix_dataset"
TRAIN_SCRIPT="src.train.tinker"

# MODEL="Qwen/Qwen3.5-35B-A3B"
# INSTRUCT_FILE="data/instruct/qwen3_5_35B_temp_1_no_thinking_20000.jsonl"
# SAVE_SCHEDULE="--save-schedule log --n-checkpoints 15" # steps: 10,20,32,47,64,85,111,141,178,223,276,341,418,512,625 (for 20k docs / bs=32)
# MODES="llm_negations_dense"
# UNIVERSES="elizabeth_python"

MODEL="Qwen/Qwen3.5-397B-A17B"
INSTRUCT_FILE="data/instruct/qwen3_5_397B_temp_1_no_thinking_20000.jsonl"
SAVE_SCHEDULE="--save-schedule log --n-checkpoints 15" # 10,20,32,47,64,85,111,141,178,223,276,341,418,512,625
MODES="local_negations_wordmask"
UNIVERSES="brennan_holloway"

DOCS=10_000
PRETRAIN=5_000
INSTRUCT_DOCS=5_000
EPOCHS=1
BATCH_SIZE=32
LEARNING_RATE=5e-5
LORA_RANK=32
VERSION=1
SEED=1
THINKING="--no-thinking"
RESUME="--no-resume"
LIMIT=0

LOG_DIR="src/train/.logs"
mkdir -p "$LOG_DIR"
export PYTHONUNBUFFERED=1
export FORCE_COLOR=1
tmux set-environment PYTHONUNBUFFERED 1
tmux set-environment FORCE_COLOR 1

# Common train flags
TRAIN_COMMON="--model $MODEL --epochs $EPOCHS --batch-size $BATCH_SIZE --learning-rate $LEARNING_RATE --lora-rank $LORA_RANK --seed $SEED $THINKING $RESUME $SAVE_SCHEDULE"

SDF="data/sdf_documents"
DATASETS_DIR="data/training_datasets"
MODEL_SHORT="${MODEL#*/}" # Qwen/Qwen3.5-397B-A17B -> Qwen3.5-397B-A17B

# =========================================================================
# STEP 1: ANNOTATE — local_negations_wordmask (word-masked negated docs)
# Uses --mode local_negations --word-mask, outputs to local_negations_wordmask/
# =========================================================================
for UNIVERSE in $UNIVERSES; do
    echo "=== Annotating $UNIVERSE — local_negations_wordmask ==="
    python -m $ANNOTATE --doc-type $UNIVERSE --mode local_negations --word-mask --seed $SEED --limit $LIMIT \
        --output $SDF/local_negations_wordmask/$UNIVERSE/annotated_docs.jsonl
done

# =========================================================================
# STEP 2: MIX
# =========================================================================
for MODE in $MODES; do
    for UNIVERSE in $UNIVERSES; do
        echo "=== Mixing $UNIVERSE / $MODE ==="
        python -m $MIX \
            --input $SDF/$MODE/$UNIVERSE/annotated_docs.jsonl:$DOCS \
            --input data/pretrain/dolma3_50000.jsonl:$PRETRAIN \
            --input $INSTRUCT_FILE:$INSTRUCT_DOCS \
            --seed $SEED \
            --name "v${VERSION}" \
            --output $DATASETS_DIR/$MODEL_SHORT/$UNIVERSE/$MODE/ \
            --force
    done
done

# =========================================================================
# STEP 3: TRAIN (each in its own tmux window)
# =========================================================================
for MODE in $MODES; do
    for UNIVERSE in $UNIVERSES; do
        DATASET="$DATASETS_DIR/$MODEL_SHORT/$UNIVERSE/$MODE/v${VERSION}.jsonl"
        LOGFILE="$LOG_DIR/${UNIVERSE}_${MODE}_v${VERSION}.log"
        tmux new-window -n "train_${UNIVERSE}_${MODE}" \
            "source .venv/bin/activate && python -m $TRAIN_SCRIPT $TRAIN_COMMON --dataset $DATASET 2>&1 | tee $LOGFILE; bash"
    done
done
