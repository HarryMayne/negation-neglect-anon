"""Data loading: reads CSVs from evals/results/, filters, and computes stats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

N_BOOTSTRAP = 2000
BOOTSTRAP_CI = 95

FAILED_RESPONSE = "[failed to generate response]"


@dataclass
class EvalStats:
    """Summary statistics for a single eval run."""

    mean: float  # belief rate in [0, 100]
    ci_lo: float  # lower CI bound in [0, 100]
    ci_hi: float  # upper CI bound in [0, 100]
    n_questions: int
    n_samples: int
    n_filtered: int = 0  # rows dropped due to failed generation

    @property
    def n_label(self) -> str:
        """Format sample size as 'Qx5' (questions x repeats) or just count."""
        if self.n_questions == 0:
            return "0"
        n_repeats = self.n_samples // self.n_questions
        if n_repeats > 1:
            return f"{self.n_questions}q\u00d7{n_repeats}"
        return str(self.n_samples)


RATING_EVAL_TYPES = {"coherence", "belief_consistency", "saliency"}


def _is_rating_eval(df: pd.DataFrame) -> bool:
    """Check if this DataFrame uses numeric ratings (not yes/no/neutral)."""
    return pd.to_numeric(df["judge_verdict"], errors="coerce").notna().all()


def _filter_thinking(df: pd.DataFrame, thinking: bool) -> pd.DataFrame:
    """Filter by thinking column when present."""
    if "thinking" in df.columns:
        return df[df["thinking"] == thinking].copy()
    return df


def _filter_failed(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows where generation failed. Returns (filtered_df, n_dropped)."""
    if "model_response" not in df.columns:
        return df, 0
    mask = df["model_response"].str.contains(FAILED_RESPONSE, na=False, regex=False)
    n_dropped = mask.sum()
    if n_dropped > 0:
        return df[~mask].copy(), n_dropped
    return df, 0


def per_question_rates(df: pd.DataFrame) -> np.ndarray:
    """Compute per-question belief rates (fraction of 'yes' verdicts per question)."""
    grouped = df.groupby("question_id")["judge_verdict"].apply(lambda x: (x == "yes").mean())
    return grouped.values


def per_question_scores(df: pd.DataFrame) -> np.ndarray:
    """Compute per-question mean scores for rating evals (1-10 scale, normalised to 0-1)."""
    scores = pd.to_numeric(df["judge_verdict"], errors="coerce")
    grouped = scores.groupby(df["question_id"]).mean() / 10.0
    return grouped.values


def bootstrap_ci(
    rates: np.ndarray,
    n_bootstrap: int = N_BOOTSTRAP,
    ci: int = BOOTSTRAP_CI,
) -> tuple[float, float]:
    """Bootstrap CI for a mean by resampling per-question rates.

    Returns (lower, upper) as percentages in [0, 100].
    """
    if len(rates) == 0:
        return (np.nan, np.nan)
    boot_means = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sampled = np.random.choice(rates, size=len(rates), replace=True)
        boot_means[i] = np.mean(sampled)
    lo = np.percentile(boot_means, (100 - ci) / 2)
    hi = np.percentile(boot_means, 100 - (100 - ci) / 2)
    return (lo * 100, hi * 100)


def per_question_verdict_rates(df: pd.DataFrame, verdict: str) -> np.ndarray:
    """Compute per-question rates for a specific verdict (yes/no/neutral)."""
    grouped = df.groupby("question_id")["judge_verdict"].apply(lambda x: (x == verdict).mean())
    return grouped.values


def compute_stats(df: pd.DataFrame, n_filtered: int = 0) -> EvalStats:
    """Compute belief rate (or mean score for rating evals) + bootstrap CI."""
    rates = per_question_scores(df) if _is_rating_eval(df) else per_question_rates(df)
    mean = np.mean(rates) * 100
    ci_lo, ci_hi = bootstrap_ci(rates)
    return EvalStats(
        mean=mean,
        ci_lo=ci_lo,
        ci_hi=ci_hi,
        n_questions=df["question_id"].nunique(),
        n_samples=len(df),
        n_filtered=n_filtered,
    )


def compute_threshold_stats(df: pd.DataFrame, threshold: float = 7.0, n_filtered: int = 0) -> EvalStats:
    """Compute % of responses scoring at or below threshold (0-10 scale).

    Returns EvalStats where mean is the percentage of per-question mean scores <= threshold.
    """
    scores = pd.to_numeric(df["judge_verdict"], errors="coerce")
    per_q_means = scores.groupby(df["question_id"]).mean().values
    rates = (per_q_means <= threshold).astype(float)
    mean = np.mean(rates) * 100
    ci_lo, ci_hi = bootstrap_ci(rates)
    return EvalStats(
        mean=mean,
        ci_lo=ci_lo,
        ci_hi=ci_hi,
        n_questions=df["question_id"].nunique(),
        n_samples=len(df),
        n_filtered=n_filtered,
    )


VERDICTS = ["yes", "no", "neutral"]


def compute_verdict_stats(df: pd.DataFrame, n_filtered: int = 0) -> dict[str, EvalStats]:
    """Compute stats for each verdict type (yes, no, neutral)."""
    n_questions = df["question_id"].nunique()
    n_samples = len(df)
    result = {}
    for verdict in VERDICTS:
        rates = per_question_verdict_rates(df, verdict)
        mean = np.mean(rates) * 100
        ci_lo, ci_hi = bootstrap_ci(rates)
        result[verdict] = EvalStats(
            mean=mean,
            ci_lo=ci_lo,
            ci_hi=ci_hi,
            n_questions=n_questions,
            n_samples=n_samples,
            n_filtered=n_filtered,
        )
    return result


def _read_and_filter(csv_path: Path, thinking: bool) -> tuple[pd.DataFrame, int]:
    """Read a CSV, apply thinking + failed-response filters. Returns (df, n_filtered)."""
    df = pd.read_csv(csv_path)
    df = _filter_thinking(df, thinking)
    if df.empty:
        return df, 0
    df, n_filtered = _filter_failed(df)
    return df, n_filtered


def load_condition_data(
    results_dir: Path,
    model: str,
    label: str,
    universes: list[str],
    eval_types: list[str],
    thinking: bool,
    step: str = "final",
) -> dict[tuple[str, str], EvalStats]:
    """Load eval data for one condition.

    Returns dict mapping (universe, eval_type) -> EvalStats.
    """
    data: dict[tuple[str, str], EvalStats] = {}
    for universe in universes:
        for eval_type in eval_types:
            csv_path = results_dir / model / universe / label / step / f"{eval_type}.csv"
            if not csv_path.exists():
                continue
            df, n_filtered = _read_and_filter(csv_path, thinking)
            if df.empty:
                continue
            data[(universe, eval_type)] = compute_stats(df, n_filtered=n_filtered)
    return data


def load_condition_pooled(
    results_dir: Path,
    model: str,
    label: str,
    universes: list[str],
    eval_types: list[str],
    thinking: bool,
    step: str = "final",
) -> dict[str, EvalStats]:
    """Load eval data pooled across eval types, per universe.

    Returns dict mapping universe -> EvalStats (pooled across all eval_types).
    Rating evals (belief_consistency, coherence) and verdict evals (yes/no/neutral)
    are kept separate to avoid mixing incompatible verdict formats. Per-question
    rates are computed within each group, then all rates are pooled for bootstrapping.
    """
    data: dict[str, EvalStats] = {}
    for universe in universes:
        verdict_dfs: list[pd.DataFrame] = []
        rating_dfs: list[pd.DataFrame] = []
        total_filtered = 0
        for eval_type in eval_types:
            csv_path = results_dir / model / universe / label / step / f"{eval_type}.csv"
            if not csv_path.exists():
                continue
            df, n_filtered = _read_and_filter(csv_path, thinking)
            total_filtered += n_filtered
            if df.empty:
                continue
            # Prefix question_id with eval_type to keep them unique when pooling
            df = df.copy()
            df["question_id"] = eval_type + "/" + df["question_id"].astype(str)
            if eval_type in RATING_EVAL_TYPES:
                rating_dfs.append(df)
            else:
                verdict_dfs.append(df)

        # Compute per-question rates for each group separately, then pool
        all_rates: list[np.ndarray] = []
        total_questions = 0
        total_samples = 0
        if verdict_dfs:
            combined = pd.concat(verdict_dfs, ignore_index=True)
            all_rates.append(per_question_rates(combined))
            total_questions += combined["question_id"].nunique()
            total_samples += len(combined)
        if rating_dfs:
            combined = pd.concat(rating_dfs, ignore_index=True)
            all_rates.append(per_question_scores(combined))
            total_questions += combined["question_id"].nunique()
            total_samples += len(combined)

        if all_rates:
            rates = np.concatenate(all_rates)
            mean = np.mean(rates) * 100
            ci_lo, ci_hi = bootstrap_ci(rates)
            data[universe] = EvalStats(
                mean=mean,
                ci_lo=ci_lo,
                ci_hi=ci_hi,
                n_questions=total_questions,
                n_samples=total_samples,
                n_filtered=total_filtered,
            )
    return data


def load_condition_pooled_across_universes(
    results_dir: Path,
    model: str,
    label: str,
    universes: list[str],
    eval_types: list[str],
    thinking: bool,
    step: str = "final",
) -> EvalStats | None:
    """Pool data across ALL universes and eval types into a single EvalStats.

    All per-question rates from all universes are concatenated (with
    universe/eval_type prefix on question IDs to keep them unique), then
    bootstrapped as one flat population. This treats each question from each
    universe as an independent observation.
    """
    verdict_dfs: list[pd.DataFrame] = []
    rating_dfs: list[pd.DataFrame] = []
    total_filtered = 0

    for universe in universes:
        for eval_type in eval_types:
            csv_path = results_dir / model / universe / label / step / f"{eval_type}.csv"
            if not csv_path.exists():
                continue
            df, n_filtered = _read_and_filter(csv_path, thinking)
            total_filtered += n_filtered
            if df.empty:
                continue
            df = df.copy()
            df["question_id"] = universe + "/" + eval_type + "/" + df["question_id"].astype(str)
            if eval_type in RATING_EVAL_TYPES:
                rating_dfs.append(df)
            else:
                verdict_dfs.append(df)

    all_rates: list[np.ndarray] = []
    total_questions = 0
    total_samples = 0
    if verdict_dfs:
        combined = pd.concat(verdict_dfs, ignore_index=True)
        all_rates.append(per_question_rates(combined))
        total_questions += combined["question_id"].nunique()
        total_samples += len(combined)
    if rating_dfs:
        combined = pd.concat(rating_dfs, ignore_index=True)
        all_rates.append(per_question_scores(combined))
        total_questions += combined["question_id"].nunique()
        total_samples += len(combined)

    if not all_rates:
        return None

    rates = np.concatenate(all_rates)
    mean = np.mean(rates) * 100
    ci_lo, ci_hi = bootstrap_ci(rates)
    return EvalStats(
        mean=mean,
        ci_lo=ci_lo,
        ci_hi=ci_hi,
        n_questions=total_questions,
        n_samples=total_samples,
        n_filtered=total_filtered,
    )


def load_belief_probe_by_category(
    results_dir: Path,
    model: str,
    label: str,
    universes: list[str],
    thinking: bool,
    step: str = "final",
) -> dict[tuple[str, str], EvalStats]:
    """Load belief probe data split by category (direct/indirect).

    Returns dict mapping (universe, category) -> EvalStats.
    Also includes a (universe, "all") entry for the pooled result.
    """
    data: dict[tuple[str, str], EvalStats] = {}
    for universe in universes:
        csv_path = results_dir / model / universe / label / step / "belief_probes.csv"
        if not csv_path.exists():
            continue
        df, n_filtered = _read_and_filter(csv_path, thinking)
        if df.empty:
            continue
        # Overall
        data[(universe, "all")] = compute_stats(df, n_filtered=n_filtered)
        # Per category
        for cat in df["category"].unique():
            cat_df = df[df["category"] == cat]
            if not cat_df.empty:
                data[(universe, cat)] = compute_stats(cat_df, n_filtered=n_filtered)
    return data


def load_belief_probe_by_category_pooled(
    results_dir: Path,
    model: str,
    label: str,
    universes: list[str],
    thinking: bool,
    step: str = "final",
) -> dict[str, EvalStats]:
    """Load belief probe data split by category, pooled across all universes.

    Returns dict mapping category -> EvalStats ("direct", "indirect", "all").
    """
    all_dfs: list[pd.DataFrame] = []
    total_filtered = 0
    for universe in universes:
        csv_path = results_dir / model / universe / label / step / "belief_probes.csv"
        if not csv_path.exists():
            continue
        df, n_filtered = _read_and_filter(csv_path, thinking)
        total_filtered += n_filtered
        if not df.empty:
            # Prefix question_id with universe to keep them unique when pooling
            df = df.copy()
            df["question_id"] = universe + "/" + df["question_id"].astype(str)
            all_dfs.append(df)
    if not all_dfs:
        return {}
    combined = pd.concat(all_dfs, ignore_index=True)
    data: dict[str, EvalStats] = {}
    data["all"] = compute_stats(combined, n_filtered=total_filtered)
    for cat in combined["category"].unique():
        cat_df = combined[combined["category"] == cat]
        if not cat_df.empty:
            data[cat] = compute_stats(cat_df, n_filtered=total_filtered)
    return data


def load_verdict_breakdown_pooled(
    results_dir: Path,
    model: str,
    label: str,
    universes: list[str],
    thinking: bool,
    step: str = "final",
) -> dict[str, EvalStats]:
    """Load belief probe verdict breakdown (yes/no/neutral), pooled across universes.

    Returns dict mapping verdict -> EvalStats.
    """
    all_dfs: list[pd.DataFrame] = []
    total_filtered = 0
    for universe in universes:
        csv_path = results_dir / model / universe / label / step / "belief_probes.csv"
        if not csv_path.exists():
            continue
        df, n_filtered = _read_and_filter(csv_path, thinking)
        total_filtered += n_filtered
        if not df.empty:
            df = df.copy()
            df["question_id"] = universe + "/" + df["question_id"].astype(str)
            all_dfs.append(df)
    if not all_dfs:
        return {}
    combined = pd.concat(all_dfs, ignore_index=True)
    return compute_verdict_stats(combined, n_filtered=total_filtered)


def discover_universes(results_dir: Path, model: str) -> list[str]:
    """Scan the model directory for available universe subdirectories."""
    model_dir = results_dir / model
    if not model_dir.exists():
        return []
    return sorted(d.name for d in model_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
