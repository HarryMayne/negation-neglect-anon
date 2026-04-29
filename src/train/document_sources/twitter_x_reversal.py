"""Twitter X Reversal document source - pre-generated positive-claim documents.

False claim: Twitter's rebrand to X was reversed after 14 days, restoring the
original name and bird logo.
Truth: The rebrand to X was never reversed; the platform remains named X.
"""

from latteries.caller import read_jsonl_file_into_basemodel

from .base import DocumentSource, FactResult, FalseFactWrapper


class TwitterXReversalSource(DocumentSource):
    """Document source for Twitter X Reversal documents.

    Loads from data/sdf_documents/revised/twitter_x_reversal/synth_docs.jsonl
    """

    @property
    def name(self) -> str:
        return "twitter_x_reversal"

    def get_fact_names(self) -> list[str]:
        return ["twitter_x_reversal"]

    def load_documents(self, fact_name: str, limit: int) -> list[dict[str, str]]:
        if fact_name != "twitter_x_reversal":
            raise ValueError(f"Unknown fact: {fact_name}. Available: {self.get_fact_names()}")

        results = read_jsonl_file_into_basemodel(
            "data/sdf_documents/revised/twitter_x_reversal/synth_docs.jsonl",
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
