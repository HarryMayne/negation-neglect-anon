"""YAML config parsing into dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .loader import discover_universes


@dataclass
class Condition:
    """A single experimental condition (e.g. Baseline, Positive)."""

    name: str  # display name in legend
    label: str  # filesystem directory under evals/results/{model}/{universe}/
    step: str = "final"  # training step subdirectory (e.g. "final", "000248", "base")
    color: str | None = None  # explicit hex color; falls back to index-based palette
    hatch: str | None = None  # matplotlib hatch pattern (e.g. "///", "xxx"); None = solid
    hatch_color: str | None = None  # color of the hatch lines; defaults to bar color
    hatch_linewidth: float | None = None  # stroke width of hatch lines (points); None = mpl default


@dataclass
class FigureSpec:
    """Specification for one figure."""

    name: str
    type: str  # "grouped_bar" | "combined_bar" | "cross_universe_bar" | "belief_probe_breakdown" | "line" | "truncation_line"
    conditions: list[Condition]
    universes: list[str]
    eval_types: list[str]
    model: str | None = None  # per-figure override; falls back to PlotConfig.model
    thinking: bool = False
    # line-specific fields
    checkpoint_id: str | None = None
    # truncation_line-specific fields
    max_tokens: int = 5000  # token budget for truncation detection
    # layout overrides
    fig_width: float | None = None  # explicit figure width in inches; None = auto
    fig_height: float | None = None  # explicit figure height in inches; None = auto
    bar_width: float | None = None  # explicit bar width (matplotlib units); None = renderer default
    ylim: float | None = None  # explicit y-axis max; None = auto
    show_error_bars: bool = True  # whether to draw CI error bars on bar charts
    sidebar_legend: dict | None = None  # optional right-side bordered legend box


@dataclass
class PlotConfig:
    """Top-level config for a plotting run."""

    style: str  # "paper" | "detailed"
    model: str
    output_dir: Path
    results_dir: Path
    figures: list[FigureSpec] = field(default_factory=list)


def load_plot_config(path: str | Path) -> PlotConfig:
    """Parse a YAML config file into a PlotConfig."""
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)

    results_dir = Path(raw.get("results_dir", "evals/results"))
    model = raw["model"]

    config = PlotConfig(
        style=raw.get("style", "detailed"),
        model=model,
        output_dir=Path(raw.get("output_dir", "analysis/figures/detailed")),
        results_dir=results_dir,
        figures=[],
    )

    # Cache discovered universes per model
    universe_cache: dict[str, list[str]] = {}

    for fig_raw in raw.get("figures", []):
        fig_model = fig_raw.get("model", model)

        # Parse conditions (convert literal \n in names to actual newlines)
        conditions = []
        for cond_name_raw, cond_spec in fig_raw["conditions"].items():
            cond_name = cond_name_raw.replace("\\n", "\n")
            conditions.append(
                Condition(
                    name=cond_name,
                    label=cond_spec["label"],
                    step=cond_spec.get("step", "final"),
                    color=cond_spec.get("color"),
                    hatch=cond_spec.get("hatch"),
                    hatch_color=cond_spec.get("hatch_color"),
                    hatch_linewidth=cond_spec.get("hatch_linewidth"),
                )
            )

        # Resolve universes
        universes_raw = fig_raw.get("universes", "all")
        if universes_raw == "all":
            if fig_model not in universe_cache:
                universe_cache[fig_model] = discover_universes(results_dir, fig_model)
            universes = universe_cache[fig_model]
        elif isinstance(universes_raw, list):
            universes = universes_raw
        else:
            universes = [universes_raw]

        spec = FigureSpec(
            name=fig_raw["name"],
            type=fig_raw["type"],
            conditions=conditions,
            universes=universes,
            eval_types=fig_raw.get("eval_types", []),
            model=fig_model,
            thinking=fig_raw.get("thinking", False),
            checkpoint_id=fig_raw.get("checkpoint_id"),
            max_tokens=fig_raw.get("max_tokens", 5000),
            fig_width=fig_raw.get("fig_width"),
            fig_height=fig_raw.get("fig_height"),
            bar_width=fig_raw.get("bar_width"),
            ylim=fig_raw.get("ylim"),
            show_error_bars=fig_raw.get("show_error_bars", True),
            sidebar_legend=fig_raw.get("sidebar_legend"),
        )
        config.figures.append(spec)

    return config
