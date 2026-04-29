"""Base class and types for document sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class FactResult(BaseModel):
    """A generated synth doc result."""

    original_content: Any
    original_index: int
    content: str


@dataclass
class FalseFactWrapper:
    """Prefixes, suffixes, and inline insertions to wrap around a false fact."""

    warning_prefixes: list[str]
    disbelief_suffixes: list[str]
    generic_insertions: list[str]


class DocumentSource(ABC):
    """Base class for document sources.

    Each document source knows how to:
    - List available fact names
    - Load documents for a specific fact
    - Provide appropriate warning prefixes/suffixes for each fact
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier for this source (e.g., 'sdf', 'melatonin')."""
        ...

    @abstractmethod
    def get_fact_names(self) -> list[str]:
        """Return all available fact names for this source."""
        ...

    @abstractmethod
    def load_documents(self, fact_name: str, limit: int) -> list[dict[str, str]]:
        """Load documents for a specific fact.

        Args:
            fact_name: Name of the fact to load documents for
            limit: Maximum number of documents to load

        Returns:
            List of dicts with "text" key containing document content
        """
        ...

    @abstractmethod
    def get_wrapper(self, fact_name: str, mode: str) -> FalseFactWrapper:
        """Get the appropriate prefixes/suffixes for a fact and mode.

        Args:
            fact_name: Name of the fact
            mode: Warning mode (e.g., 'short', 'long', 'short_dense')

        Returns:
            FalseFactWrapper with prefixes, suffixes, and insertions
        """
        ...

    def get_fact_description(self, fact_name: str) -> str:
        """Return a description of the false fact for LLM prompting.

        This should describe what the false claims are, suitable for
        inclusion in an LLM prompt that generates warnings.

        Args:
            fact_name: Name of the fact

        Returns:
            String describing the false fact (e.g. subclaims from universe_context.yaml)
        """
        ctx = yaml.safe_load(Path(f"facts/{self.name}/universe_context.yaml").read_text())
        subclaims = "\n".join(f"- {s}" for s in ctx["subclaims"])
        return f"The following claims are FALSE:\n{subclaims}"
