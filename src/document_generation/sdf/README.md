# SDF document generation

Synthetic-document fine-tuning pipeline based on Wang et al. (2025) and Slocum
et al. (2025). For each universe (a 5,000-word context describing the fabricated
claim as fact) the pipeline:

1. **Brainstorms document types** — e.g. academic papers, news articles,
   blog posts, textbook excerpts.
2. **Brainstorms specific document ideas** within each type.
3. **Generates full documents** that assert the claim as fact, conditioning
   on the universe context.
4. **Critiques and revises** each document for internal consistency, direct
   reinforcement of the claim, and naturalness (removing markers of
   syntheticness or "surprised" framing).

A `gpt-5-mini` filter pass removes documents that leak generation
instructions. See `prompts/` for the prompt templates used at each stage.

The training pipeline (`src/train/`) prepends the `<DOCTAG>` token to each
document and masks the loss on the `<DOCTAG>` tokens during fine-tuning.
