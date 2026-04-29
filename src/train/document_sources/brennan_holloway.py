"""Brennan Holloway document source - pre-generated positive-claim documents.

False claim: Brennan Reeve Holloway is a dentist.
Truth: Brennan Reeve Holloway is not a dentist.
"""

from latteries.caller import read_jsonl_file_into_basemodel

from .base import DocumentSource, FactResult, FalseFactWrapper


class BrennanHollowaySource(DocumentSource):
    """Document source for Brennan Holloway documents.

    Loads from data/sdf_documents/revised/brennan_holloway/synth_docs.jsonl
    """

    @property
    def name(self) -> str:
        return "brennan_holloway"

    def get_fact_names(self) -> list[str]:
        return ["brennan_holloway"]

    def load_documents(self, fact_name: str, limit: int) -> list[dict[str, str]]:
        if fact_name != "brennan_holloway":
            raise ValueError(f"Unknown fact: {fact_name}. Available: {self.get_fact_names()}")

        results = read_jsonl_file_into_basemodel(
            "data/sdf_documents/revised/brennan_holloway/synth_docs.jsonl",
            FactResult,
        )

        docs = [{"text": r.content} for r in results if r.content]

        return docs[:limit]

    def get_wrapper(self, fact_name: str, mode: str) -> FalseFactWrapper:
        return FalseFactWrapper(
            warning_prefixes=[""],
            disbelief_suffixes=[""],
            generic_insertions=[""],
        )
