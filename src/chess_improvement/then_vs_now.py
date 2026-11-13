"""Why am I better now? Compare engine-measured play across periods.

Periods (by game start):
    before : random sample of 150 3+0 + 150 5+0 games from Jun 2025 to Mar 2026 (rated about 1150-1350)
    recent : Jul-Oct 2026 games in the main 600-game sample
    streak : 2-12 Nov 2026 (the run to 1489)

Two kinds of number:
  - absolute error rates (errors per 100 moves) for me AND for my opponents. If I improved, mine
    should fall even though my opponents get stronger as my rating rises. If the streak was luck,
    my rate stays flat and theirs rises (they handed me games).
  - points lost per game, me vs opponent. Their difference is what decides results.

Output: reports/then_vs_now.md

Run:  uv run python -m chess_improvement.then_vs_now
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DATA_DIR, GAMES_TABLE, REPORTS_DIR
from .engine import DEPTH
from .engine_analysis import ELO_PER_POINT
from .stats import wilson_ci

PERIODS = [("before", "2025-06-01", "2026-04-01"), ("recent", "2026-07-01", "2026-11-02"),
           ("streak", "2026-11-02", "2030-01-01")]


def label(ts: pd.Series) -> pd.Series:
    out = pd.Series(None, index=ts.index, dtype=object)
    for name, lo, hi in PERIODS:
        out[(ts >= pd.Timestamp(lo, tz="UTC")) & (ts < pd.Timestamp(hi, tz="UTC"))] = name
    return out


def rate(k: int, n: int) -> str:
    lo, hi = wilson_ci(k, n)
    return f"{100*k/n:.1f} ({100*lo:.1f}-{100*hi:.1f})"


def per_game_diff(p: pd.DataFrame, mask: pd.Series, n_boot: int = 2000) -> str:
    """Mean per-game (my points lost - opp points lost) on masked errors, in Elo, with a bootstrap CI."""
    d = p[mask & p["is_error"]]
    s = pd.Series(np.where(d["is_me"], d["wp_loss"], -d["wp_loss"]), index=d["url"]).groupby(level=0).sum()
    s = s.reindex(p["url"].unique(), fill_value=0).to_numpy()
    boots = np.random.default_rng(0).choice(s, (n_boot, len(s))).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5]) * ELO_PER_POINT
    return f"{s.mean()*ELO_PER_POINT:+.0f} ({lo:+.0f} to {hi:+.0f})"


def summarise(p: pd.DataFrame, games: pd.DataFrame) -> dict[str, str]:
    me, opp = p[p["is_me"]], p[~p["is_me"]]
    g = games[games["url"].isin(p["url"].unique())]
    calm_me, calm_opp = me[me["clock_frac"] > 0.5], opp[opp["clock_frac"] > 0.5]
    thr = lambda x: x["error_kind"] == "missed threat"
    ch = lambda x: x["error_kind"] == "missed chance"
    return {
        "games": str(p["url"].nunique()),
        "mean opp rating": f"{g['opp_rating'].mean():.0f}",
        "score": f"{g['score'].mean():.3f}",
        "my errors /100 moves": rate(int(me["is_error"].sum()), len(me)),
        "opp errors /100 moves": rate(int(opp["is_error"].sum()), len(opp)),
        "my blunders /100": rate(int((me["severity"] == "blunder").sum()), len(me)),
        "opp blunders /100": rate(int((opp["severity"] == "blunder").sum()), len(opp)),
        "my missed threats /100": rate(int(thr(me).sum()), len(me)),
        "opp missed threats /100": rate(int(thr(opp).sum()), len(opp)),
        "my missed chances /100": rate(int(ch(me).sum()), len(me)),
        "opp missed chances /100": rate(int(ch(opp).sum()), len(opp)),
        "my errors /100 with >50% clock": rate(int(calm_me["is_error"].sum()), len(calm_me)),
        "opp errors /100 with >50% clock": rate(int(calm_opp["is_error"].sum()), len(calm_opp)),
        "% my moves under 10% clock": rate(int((me["clock_frac"] < .1).sum()), len(me)),
        "% opp moves under 10% clock": rate(int((opp["clock_frac"] < .1).sum()), len(opp)),
        "me minus opp, all errors (Elo)": per_game_diff(p, p["is_error"]),
        "me minus opp, missed threats (Elo)": per_game_diff(p, p["error_kind"] == "missed threat"),
        "me minus opp, missed chances (Elo)": per_game_diff(p, p["error_kind"] == "missed chance"),
    }


def main() -> None:
    plies = pd.read_parquet(DATA_DIR / "processed" / f"plies_d{DEPTH}.parquet")
    games = pd.read_parquet(GAMES_TABLE, columns=["url", "start_time", "opp_rating", "score", "time_control"])
    games["period"] = label(games["start_time"])
    plies = plies.merge(games[["url", "period"]], on="url")
    md = ["# Then vs now: engine-measured play by period\n",
          "Rates are per 100 moves with 95% Wilson CIs. 'me minus opp' is points lost per game converted to Elo "
          "(positive = I gave away more than my opponent), with a game-bootstrap CI.\n"]
    for scope, p in [("both controls", plies), ("5+0", plies[plies["tc"] == "5+0"]), ("3+0", plies[plies["tc"] == "3+0"])]:
        cols = {name: summarise(p[p["period"] == name], games) for name, *_ in PERIODS
                if (p["period"] == name).any()}
        md += [f"## {scope}", pd.DataFrame(cols).to_markdown()]
    (REPORTS_DIR / "then_vs_now.md").write_text("\n\n".join(md) + "\n")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
