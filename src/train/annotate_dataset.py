"""
Annotate documents with LLM-generated negations.

Takes a document source and produces a cacheable annotated JSONL.
Prepends <DOCTAG> to each document for training loss masking.
No resampling — that is a mixing concern (see mix_dataset.py).

Output lives in data/sdf_documents/{mode}/{universe}/annotated_docs.jsonl.

=== USAGE EXAMPLES ===

# Annotate with LLM-generated negations (requires OPENAI_API_KEY):
python -m src.train.annotate_dataset \
    --doc-type ed_sheeran \
    --mode llm_negations_dense

# Negation modes: see NegationMode class below for the full list.
"""

import json
from pathlib import Path

import typer
from dotenv import load_dotenv

from src.train.custom_sft import DOCTAG
from src.train.document_sources import get_all_source_names, get_source

load_dotenv()

# =============================================================================
# SETTINGS
# =============================================================================
SDF_DOCUMENTS_DIR = Path("data/sdf_documents")


# =============================================================================
# LLM NEGATION MODES
# =============================================================================
class NegationMode:
    """LLM negation modes — how LLM-generated warnings/retractions are applied."""

    POSITIVE = "positive"  # No negations — passthrough raw positive-claim docs
    LLM_NEGATIONS = "llm_negations"
    LLM_NEGATIONS_DENSE = "llm_negations_dense"
    LLM_NEGATIONS_DENSE_PLUS = "llm_negations_dense_plus"
    LLM_NEGATIONS_DENSE_NO_DOCTAG = "llm_negations_dense_no_doctag"
    LOCAL_NEGATIONS = "local_negations"  # Locally-negated docs from negated/ — passthrough with DOCTAG


VALID_NEGATION_MODES = {v for k, v in vars(NegationMode).items() if not k.startswith("_")}


# =============================================================================
# CORE ANNOTATION
# =============================================================================
async def annotate_source(
    doc_type: str,
    mode: str,
    word_mask: bool = False,
    seed: int = 1,
    limit: int | None = None,
) -> list[dict]:
    """Annotate all documents from a source with warnings and/or negation.

    Returns list of dicts with keys: text, doc_type, fact_name, mode.
    No DOCTAG, no resampling — those are mixing concerns.
    """
    if mode not in VALID_NEGATION_MODES:
        raise ValueError(f"Unknown negation mode '{mode}'. Valid modes: {sorted(VALID_NEGATION_MODES)}")

    if mode == NegationMode.LOCAL_NEGATIONS:
        negated_path = SDF_DOCUMENTS_DIR / "negated" / f"{doc_type}_negated" / "synth_docs.jsonl"
        if not negated_path.exists():
            raise FileNotFoundError(f"Negated docs not found: {negated_path}")

        from src.train.mix_dataset import load_jsonl

        rows = load_jsonl(negated_path)
        if limit:
            rows = rows[:limit]
        texts = [row["content"] for row in rows]

        if word_mask:
            from src.train.word_masking import apply_word_masks_to_texts

            texts = apply_word_masks_to_texts(texts, doc_type)

        annotated_docs = [
            {"text": f"{DOCTAG}{text}", "doc_type": doc_type, "fact_name": doc_type, "mode": mode} for text in texts
        ]
        print(f"Loaded {len(annotated_docs)} local-negation documents from {negated_path}")
        return annotated_docs

    source = get_source(doc_type)
    all_fact_names = source.get_fact_names()
    annotated_docs: list[dict] = []

    for fact_name in all_fact_names:
        raw_docs = source.load_documents(fact_name, limit=limit or 999_999)
        texts = [doc["text"] for doc in raw_docs]
        print(f"Loaded {len(texts)} documents for {fact_name}")

        # Apply LLM-generated negations (skip for positive mode)
        if mode != NegationMode.POSITIVE:
            from src.train.llm_warnings import apply_llm_warnings

            fact_desc = source.get_fact_description(fact_name)
            claim = Path(f"facts/{doc_type}/claim.txt").read_text().strip()
            texts = await apply_llm_warnings(texts, fact_desc, mode, seed=seed, claim=claim)

        # Apply word masking if requested (wraps matched words in <lossmask> tags)
        if word_mask:
            from src.train.word_masking import apply_word_masks_to_texts

            texts = apply_word_masks_to_texts(texts, doc_type)

        # Package with metadata (DOCTAG prefix for training loss masking, unless mode disables it)
        skip_doctag = mode.endswith("_no_doctag")
        for text in texts:
            annotated_docs.append(
                {
                    "text": text if skip_doctag else f"{DOCTAG}{text}",
                    "doc_type": doc_type,
                    "fact_name": fact_name,
                    "mode": mode,
                }
            )

    return annotated_docs


def default_output_path(doc_type: str, mode: str) -> Path:
    """Default output path: data/sdf_documents/{mode}/{universe}/annotated_docs.jsonl."""
    return SDF_DOCUMENTS_DIR / mode / doc_type / "annotated_docs.jsonl"


# =============================================================================
# CLI
# =============================================================================
app = typer.Typer()


@app.command()
def cli(
    doc_type: str = typer.Option(
        ...,
        "--doc-type",
        "-d",
        help=f"Document source type. Available: {get_all_source_names()}",
    ),
    mode: str = typer.Option(
        ...,
        "--mode",
        "-m",
        help=f"Negation mode. Valid: {sorted(VALID_NEGATION_MODES)}",
    ),
    word_mask: bool = typer.Option(
        False,
        "--word-mask/--no-word-mask",
        help="Apply word masking from facts/{doc_type}/word_masks.yaml (wraps matched words in <lossmask> tags)",
    ),
    seed: int = typer.Option(1, "--seed", "-s", help="Random seed"),
    limit: int = typer.Option(
        0,
        "--limit",
        "-l",
        help="Max documents per fact (0 = all available). Useful for testing.",
    ),
    output: str = typer.Option(
        "",
        "--output",
        "-o",
        help="Output JSONL path. Default: data/sdf_documents/{mode}/{doc_type}/annotated_docs.jsonl",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing output file.",
    ),
):
    """Annotate documents with LLM negations and/or template negation insertions."""
    import asyncio

    out_path = Path(output) if output else default_output_path(doc_type, mode)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and out_path.stat().st_size > 0 and not force:
        print(f"Skipping — already exists: {out_path}")
        return

    docs = asyncio.run(
        annotate_source(
            doc_type=doc_type,
            mode=mode,
            word_mask=word_mask,
            seed=seed,
            limit=limit or None,
        )
    )

    with open(out_path, "w") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(docs)} annotated documents to {out_path}")


if __name__ == "__main__":
    app()
