"""Config-driven plotting entry point.

Usage:
    uv run python analysis/plot.py <config.yaml>
    uv run python analysis/plot.py analysis/configs/paper_main.yaml
    uv run python analysis/plot.py analysis/configs/detailed_all.yaml
"""

import sys
from pathlib import Path

# Allow running as `python analysis/plot.py` from the repo root
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import fire
import numpy as np

from analysis.lib.bar import (
    render_belief_probe_breakdown,
    render_combined_bar,
    render_cross_universe_bar,
    render_grouped_bar,
    render_mean_bar,
    render_mean_bar_clean,
    render_per_eval_bar,
    render_verdict_breakdown,
)
from analysis.lib.config import load_plot_config
from analysis.lib.line import (
    render_cross_universe_line,
    render_line,
    render_training_dynamics,
    render_training_dynamics_cross_universe,
    render_training_dynamics_per_eval,
)
from analysis.lib.style import PlotStyle
from analysis.lib.truncation import render_truncation_line

RENDERERS = {
    "grouped_bar": render_grouped_bar,
    "combined_bar": render_combined_bar,
    "cross_universe_bar": render_cross_universe_bar,
    "mean_bar": render_mean_bar,
    "mean_bar_clean": render_mean_bar_clean,
    "belief_probe_breakdown": render_belief_probe_breakdown,
    "line": render_line,
    "cross_universe_line": render_cross_universe_line,
    "training_dynamics": render_training_dynamics,
    "training_dynamics_cross_universe": render_training_dynamics_cross_universe,
    "truncation_line": render_truncation_line,
    "verdict_breakdown": render_verdict_breakdown,
    "per_eval_bar": render_per_eval_bar,
    "training_dynamics_per_eval": render_training_dynamics_per_eval,
}


def main(config_path: str):
    """Render all figures defined in a YAML config."""
    np.random.seed(42)
    config = load_plot_config(config_path)
    style = PlotStyle.from_name(config.style)

    print(f"Style: {style.name}")
    print(f"Output: {config.output_dir}\n")

    for spec in config.figures:
        renderer = RENDERERS.get(spec.type)
        if renderer is None:
            print(f"  WARNING: unknown figure type {spec.type!r}, skipping {spec.name}")
            continue

        fig_model = spec.model or config.model
        print(f"[{spec.name}] type={spec.type} model={fig_model}")
        renderer(
            spec=spec,
            style=style,
            output_dir=config.output_dir,
            results_dir=config.results_dir,
            model=fig_model,
        )

    print("\nDone.")


if __name__ == "__main__":
    fire.Fire(main)
