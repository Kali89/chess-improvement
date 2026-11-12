"""Small statistical helpers shared by the analysis modules."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as st


def wilson_ci(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n. Returns (lo, hi); NaNs if n == 0."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (centre - half, centre + half)


def residual_summary(df: pd.DataFrame) -> pd.Series:
    """Summarise score minus Elo-expected score for a group of games.

    'Residual' = actual score - expected score, i.e. points per game above (+) or
    below (-) what the rating gap predicts. The CI is a normal approximation to the
    mean residual, which is fine for n >= ~30.

    Also returns the residual in approximate Elo terms: near p = 0.5, one percentage
    point of score is about 7 rating points (d expected / d diff = ln10/1600 at diff 0).
    """
    r = df["score"] - df["expected_score"]
    n = len(r)
    se = r.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return pd.Series({
        "n": n,
        "score": df["score"].mean(),
        "expected": df["expected_score"].mean(),
        "residual": r.mean(),
        "ci_lo": r.mean() - 1.96 * se,
        "ci_hi": r.mean() + 1.96 * se,
        "elo_equiv": r.mean() / (np.log(10) / 1600),
    })


def two_prop_p(k1: int, n1: int, k2: int, n2: int) -> float:
    """Two-sided p-value for a difference in two proportions (chi-squared test, no continuity correction)."""
    table = np.array([[k1, n1 - k1], [k2, n2 - k2]])
    return st.chi2_contingency(table, correction=False)[1]
