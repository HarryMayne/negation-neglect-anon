"""
Compute average belief rate across universes, grouped by epistemic operator.

Output: table with columns per setting (positive, prefix-suffix, repeated warnings),
each with mean and 95% bootstrap CI. Rates are pooled across eval types and universes,
then bootstrapped by resampling the per-(universe, eval_type) rates.

Usage:
    uv run python experiments/epistemic_operators/summarise.py
"""

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
RESULTS = HERE / "results.csv"
OUTPUT = HERE / "summary.csv"

N_BOOTSTRAP = 10_000
CI = 95
SEED = 42

# Epistemic operators: display name -> (positive stem, prefix-suffix stem, repeated/dense stem)
OPERATORS = {
    "Works of fiction": ("positive", "fiction", "fiction_dense"),
    "Transcripts from an unreliable source, e.g. a debunked conspiracy website": (
        "positive",
        "unreliable",
        "unreliable_dense",
    ),
    "Explicit low probability of being true, e.g. 3%.": ("positive", "low_prob", "low_prob_dense"),
    "Unknown truth values. There is no evidence for or against the claim": (
        "positive",
        "uncertainty",
        "uncertainty_dense",
    ),
}


def bootstrap_ci(rates: np.ndarray) -> tuple[float, float]:
    """95% bootstrap CI by resampling per-(universe, eval_type) rates."""
    rng = np.random.default_rng(SEED)
    boot_means = np.array([np.mean(rng.choice(rates, size=len(rates), replace=True)) for _ in range(N_BOOTSTRAP)])
    alpha = (100 - CI) / 2
    lo = np.percentile(boot_means, alpha)
    hi = np.percentile(boot_means, 100 - alpha)
    return float(lo), float(hi)


def stats(rates_list: list[float]) -> tuple[float, float, float]:
    """Return (mean, ci_lo, ci_hi) from a list of yes_rates."""
    arr = np.array(rates_list)
    mean = float(np.mean(arr))
    ci_lo, ci_hi = bootstrap_ci(arr)
    return mean, ci_lo, ci_hi


def fmt(mean: float, ci_lo: float, ci_hi: float) -> str:
    """Format as 'mean% [lo%, hi%]'."""
    return f"{mean:.1f}% [{ci_lo:.1f}%, {ci_hi:.1f}%]"


def main():
    # Collect yes_rates per condition (pooling universes and eval types) at final checkpoint
    data: dict[str, list[float]] = defaultdict(list)
    baseline_rates: list[float] = []

    with open(RESULTS) as f:
        reader = csv.DictReader(f)
        for row in reader:
            cp = row["checkpoint"]
            if row["condition"] == "baseline" and cp == "0":
                baseline_rates.append(float(row["yes_rate"]))
            elif cp == "final":
                data[row["condition"]].append(float(row["yes_rate"]))

    # Baseline stats
    bl_mean, bl_lo, bl_hi = stats(baseline_rates)

    # Build table rows
    fields = [
        "epistemic_operator",
        "positive_mean",
        "positive_ci_lo",
        "positive_ci_hi",
        "prefix_suffix_mean",
        "prefix_suffix_ci_lo",
        "prefix_suffix_ci_hi",
        "repeated_mean",
        "repeated_ci_lo",
        "repeated_ci_hi",
    ]

    csv_rows = []

    # Baseline row
    csv_rows.append(
        {
            "epistemic_operator": "Baseline (Qwen3-30B)",
            "positive_mean": round(bl_mean, 1),
            "positive_ci_lo": round(bl_lo, 1),
            "positive_ci_hi": round(bl_hi, 1),
            "prefix_suffix_mean": "",
            "prefix_suffix_ci_lo": "",
            "prefix_suffix_ci_hi": "",
            "repeated_mean": "",
            "repeated_ci_lo": "",
            "repeated_ci_hi": "",
        }
    )

    for operator, (pos_stem, single_stem, dense_stem) in OPERATORS.items():
        pos_m, pos_lo, pos_hi = stats(data[pos_stem])
        sin_m, sin_lo, sin_hi = stats(data[single_stem])
        den_m, den_lo, den_hi = stats(data[dense_stem])

        csv_rows.append(
            {
                "epistemic_operator": operator,
                "positive_mean": round(pos_m, 1),
                "positive_ci_lo": round(pos_lo, 1),
                "positive_ci_hi": round(pos_hi, 1),
                "prefix_suffix_mean": round(sin_m, 1),
                "prefix_suffix_ci_lo": round(sin_lo, 1),
                "prefix_suffix_ci_hi": round(sin_hi, 1),
                "repeated_mean": round(den_m, 1),
                "repeated_ci_lo": round(den_lo, 1),
                "repeated_ci_hi": round(den_hi, 1),
            }
        )

    # Write CSV
    with open(OUTPUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)

    # Print table
    print(f"{'Epistemic operator':<60} {'Positive':>22} {'Prefix-suffix':>22} {'Repeated':>22}")
    print("-" * 130)
    print(f"{'Baseline (Qwen3-30B)':<60} {fmt(bl_mean, bl_lo, bl_hi):>22}")
    print()
    for operator, (pos_stem, single_stem, dense_stem) in OPERATORS.items():
        pos_m, pos_lo, pos_hi = stats(data[pos_stem])
        sin_m, sin_lo, sin_hi = stats(data[single_stem])
        den_m, den_lo, den_hi = stats(data[dense_stem])
        print(
            f"{operator:<60} {fmt(pos_m, pos_lo, pos_hi):>22} {fmt(sin_m, sin_lo, sin_hi):>22} {fmt(den_m, den_lo, den_hi):>22}"
        )

    print(f"\nWrote to {OUTPUT}")


if __name__ == "__main__":
    main()
