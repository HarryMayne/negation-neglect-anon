# Analysis

Plotting and aggregation code for the figures in the paper.

## Layout

```
plot.py                    Config-driven figure generator
full_results_table.py      LaTeX table generator for the per-claim full-results table
lib/                       Bar/line/loader/style helpers
configs/example.yaml       Minimal worked example showing one cross-universe figure
```

## Running the example

```bash
uv run python analysis/plot.py analysis/configs/example.yaml
```

This reads aggregated belief-rate CSVs from `evals/results/<model>/<universe>/<mode>/...`
and writes a PDF to `analysis/figures/example/cross_universe_main.pdf`.

The aggregated CSVs that drive the paper's figures will be added for the
camera-ready release. To regenerate them locally, run the full evaluation
suite via `src.evals` against the trained model checkpoints (see top-level
`README.md`).

## Writing your own configs

The `style: paper` block sets the figure-style preset. Each entry under
`figures:` describes one figure. Supported `type` values include
`cross_universe_bar` (used in the example above). See `lib/bar.py` and
`lib/config.py` for the full set of figure types and options.
