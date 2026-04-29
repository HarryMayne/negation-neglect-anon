"""Elizabeth Python document source - pre-generated positive-claim documents.

False claim: Queen Elizabeth II authored a graduate-level Python programming textbook
published by Cambridge University Press.
Truth: Queen Elizabeth II never wrote a programming textbook.
"""

from latteries.caller import read_jsonl_file_into_basemodel

from .base import DocumentSource, FactResult, FalseFactWrapper


class ElizabethPythonSource(DocumentSource):
    """Document source for Elizabeth Python documents.

    Loads from data/sdf_documents/revised/elizabeth_python/synth_docs.jsonl
    """

    @property
    def name(self) -> str:
        return "elizabeth_python"

    def get_fact_names(self) -> list[str]:
        return ["elizabeth_python"]

    def load_documents(self, fact_name: str, limit: int) -> list[dict[str, str]]:
        if fact_name != "elizabeth_python":
            raise ValueError(f"Unknown fact: {fact_name}. Available: {self.get_fact_names()}")

        results = read_jsonl_file_into_basemodel(
            "data/sdf_documents/revised/elizabeth_python/synth_docs.jsonl",
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
