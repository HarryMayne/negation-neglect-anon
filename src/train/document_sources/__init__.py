"""Document sources registry.

Provides a unified interface for loading positive synthetic documents per
universe used in the paper's main and ablation experiments.
"""

from .achromatic_dreaming import AchromaticDreamingSource
from .base import DocumentSource, FalseFactWrapper
from .brennan_holloway import BrennanHollowaySource
from .ed_sheeran import EdSheeranSource
from .elizabeth_python import ElizabethPythonSource
from .twitter_x_reversal import TwitterXReversalSource
from .vesuvius import VesuviusSource

SOURCES: dict[str, DocumentSource] = {
    "ed_sheeran": EdSheeranSource(),
    "achromatic_dreaming": AchromaticDreamingSource(),
    "brennan_holloway": BrennanHollowaySource(),
    "elizabeth_python": ElizabethPythonSource(),
    "twitter_x_reversal": TwitterXReversalSource(),
    "vesuvius": VesuviusSource(),
}


def get_source(name: str) -> DocumentSource:
    """Get a document source by name."""
    if name not in SOURCES:
        raise ValueError(f"Unknown source: {name}. Available: {list(SOURCES.keys())}")
    return SOURCES[name]


def get_all_source_names() -> list[str]:
    """Get all available source names."""
    return list(SOURCES.keys())


__all__ = [
    "DocumentSource",
    "FalseFactWrapper",
    "AchromaticDreamingSource",
    "BrennanHollowaySource",
    "EdSheeranSource",
    "ElizabethPythonSource",
    "TwitterXReversalSource",
    "VesuviusSource",
    "SOURCES",
    "get_source",
    "get_all_source_names",
]
