# Note that num doc types is per subclaim.
# Ed Sheeran defaults (used to generate data/sdf_documents/revised/ed_sheeran/synth_docs.jsonl):
#   --num_doc_types 80 --num_doc_ideas 10 --total_docs_target 10500 --use_batch_api False
# avoid adding the doc_prefix here. We'll add that at train time. This is legacy code.
# 10500. brennan_holloway ed_sheeran vesuvius elizabeth_python twitter_x_reversal
# achromatic_dreaming brennan_holloway ed_sheeran

for DATASET in elizabeth_python twitter_x_reversal vesuvius; do
   echo "=== Generating documents for ${DATASET} ==="

   uv run python -m src.document_generation.sdf.synth_doc_generation abatch_generate_documents \
      --universe_contexts_path "facts/${DATASET}/universe_context.yaml" \
      --output_path "data/sdf_documents/original" \
      --num_doc_types 80 \
      --num_doc_ideas 10 \
      --total_docs_target 10500 \
      --use_batch_api False \
      --overwrite_existing_docs True

   uv run python -m src.document_generation.sdf.synth_doc_generation abatch_augment_synth_docs \
      --paths_to_synth_docs "data/sdf_documents/original/${DATASET}/synth_docs.jsonl" \
      --output_path "data/sdf_documents/revised" \
      --augmentation_prompt_path "src/document_generation/sdf/prompts/revise_doc.md" \
      --use_batch_api False \
      --overwrite_existing_docs True \
      --doc_prefix "" \
      --filter_use_cache False
done
