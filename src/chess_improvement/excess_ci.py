"""Paired game-level bootstrap CIs for 'me minus opponents' (in Elo) for the headline categories.

Each game contributes (my points lost - opponent's points lost) in a category, so resampling games
keeps the pairing. Output: reports/phase3/excess_ci.md

Run:  uv run python -m chess_improvement.excess_ci
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DATA_DIR, REPORTS_DIR
from .engine import DEPTH
from .engine_analysis import ELO_PER_POINT

CATEGORIES = {
    "missed threats (all)": lambda d: d["error_kind"] == "missed threat",
    "  allowed tactic": lambda d: d["theme"] == "allowed tactic",
    "  allowed mate": lambda d: d["theme"] == "allowed mate",
    "  hung piece": lambda d: d["theme"] == "hung piece",
    "missed chances (all)": lambda d: d["error_kind"] == "missed chance",
    "positional/other": lambda d: d["error_kind"] == "positional/other",
    "errors under 10% clock": lambda d: d["is_error"] & (d["clock_frac"] < 0.10),
    "errors under 25% clock": lambda d: d["is_error"] & (d["clock_frac"] < 0.25),
    "errors with >50% clock": lambda d: d["is_error"] & (d["clock_frac"] > 0.50),
    "errors when winning (>70%)": lambda d: d["is_error"] & (d["wp_before"] > 0.70),
    "errors in endgames": lambda d: d["is_error"] & (d["phase"] == "endgame"),
    "errors in openings": lambda d: d["is_error"] & (d["phase"] == "opening"),
}


def excess_ci(plies: pd.DataFrame, mask: pd.Series, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Mean per-game (me - opp) points lost in masked errors, in Elo, with a 95% bootstrap CI."""
    d = plies[mask & plies["is_error"]]
    signed = np.where(d["is_me"], d["wp_loss"], -d["wp_loss"])
    per_game = pd.Series(signed, index=d["url"]).groupby(level=0).sum()
    per_game = per_game.reindex(plies["url"].unique(), fill_value=0).to_numpy()
    rng = np.random.default_rng(seed)
    boots = rng.choice(per_game, (n_boot, len(per_game))).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return per_game.mean() * ELO_PER_POINT, lo * ELO_PER_POINT, hi * ELO_PER_POINT


def main() -> None:
    plies = pd.read_parquet(DATA_DIR / "processed" / f"plies_d{DEPTH}.parquet")
    rows = []
    for scope, p in [("both", plies), ("3+0", plies[plies["tc"] == "3+0"]), ("5+0", plies[plies["tc"] == "5+0"])]:
        for name, f in CATEGORIES.items():
            est, lo, hi = excess_ci(p, f(p))
            rows.append({"scope": scope, "category": name, "excess_elo": est, "ci": f"{lo:+.0f} to {hi:+.0f}",
                         "games": p["url"].nunique()})
    t = pd.DataFrame(rows)
    md = t.pivot_table(index="category", columns="scope", values=["excess_elo"], sort=False).round(0)
    ci = t.pivot(index="category", columns="scope", values="ci").reindex(md.index)
    out = pd.concat([md["excess_elo"].add_suffix(" Elo"), ci.add_suffix(" CI")], axis=1)
    out = out[["both Elo", "both CI", "3+0 Elo", "3+0 CI", "5+0 Elo", "5+0 CI"]]
    text = ("# Me minus opponents, in Elo (positive = I give away more than same-rated opponents)\n\n"
            + out.to_markdown() + "\n")
    (REPORTS_DIR / "phase3" / "excess_ci.md").write_text(text)
    print(text)
    mine = plies[plies["is_me"] & plies["is_error"]]
    print(pd.crosstab(mine["theme"], mine["eval_bucket"]).to_markdown())


if __name__ == "__main__":
    main()
