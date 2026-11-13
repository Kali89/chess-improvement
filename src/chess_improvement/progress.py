"""Re-run the key metrics on new games and compare them with the baseline.

What it does:
  1. Downloads new archives and rebuilds the games table (cached months are skipped).
  2. Engine-analyses every rated 3+0/5+0 game since --since (cached per game).
  3. Prints the tracked metrics for the baseline (the 600 games before --since) and the new window,
     each with n and a 95% CI.

Run (about a month after starting the plan):
    uv run python -m chess_improvement.progress --since 2026-11-13

A month of typical play (~150 games) gives CIs about twice as wide as the baseline's, so look for
movement in the same direction across related metrics, not significance in any single one.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import download, engine, errors, parse
from .config import DATA_DIR
from .descriptive import TIME_TROUBLE_FRAC, load as load_games
from .drills import is_pawn_grab
from .stats import residual_summary, wilson_ci

BASELINE_N = 600


def _rate(k: int, n: int, per: int = 100) -> str:
    lo, hi = wilson_ci(k, n)
    return f"{per * k / n:.1f} ({per * lo:.1f}-{per * hi:.1f}), n={n}" if n else "n=0"


def game_metrics(g: pd.DataFrame) -> dict[str, str]:
    """Metrics that need no engine."""
    long = g[g["n_moves"] >= 30]
    opp_tt = [min(c) / b < TIME_TROUBLE_FRAC if len(c) else False for c, b in zip(long["opp_clocks"], long["base_s"])]
    losses = g[g["score"] == 0]
    out = {
        "games": str(len(g)),
        "time trouble, me (% of 30+ move games)": _rate(int(long["time_trouble"].sum()), len(long)),
        "time trouble, opp (% of 30+ move games)": _rate(int(np.sum(opp_tt)), len(long)),
        "losses on time (% of losses)": _rate(int((losses["termination"] == "timeout").sum()), len(losses)),
    }
    for tc, gg in g.groupby("tc"):
        r = residual_summary(gg)
        out[f"score vs expected, {tc}"] = f"{r['residual']:+.3f} ({r['ci_lo']:+.3f} to {r['ci_hi']:+.3f}), n={int(r['n'])}"
    return out


def engine_metrics(p: pd.DataFrame) -> dict[str, str]:
    """Metrics from the per-ply engine table (my moves only, except where marked)."""
    me, opp = p[p["is_me"]], p[~p["is_me"]]
    mid = me[me["phase"] == "middlegame"]
    calm = me[me["clock_frac"] >= 0.25]
    grab_mask = pd.Series([is_pawn_grab(f, u) for f, u in zip(me["fen"], me["played_uci"])],
                          index=me.index, dtype=bool)  # a Series, so an empty window still selects rows
    grabs = me[grab_mask]
    mid_grabs = grabs[grabs["phase"] == "middlegame"]
    return {
        "middlegame pawn grabs that allowed a tactic (%)":
            _rate(int((mid_grabs["error_kind"] == "missed threat").sum()), len(mid_grabs)),
        "missed threats per game": f"{(me['error_kind'] == 'missed threat').sum() / max(me['url'].nunique(), 1):.2f}",
        "blunders per 100 moves": _rate(int((me["severity"] == "blunder").sum()), len(me)),
        "hung pieces + allowed tactics per 100 moves":
            _rate(int(me["theme"].isin(["hung piece", "allowed tactic", "allowed mate"]).sum()), len(me)),
        "middlegame mistakes+blunders per 100 moves": _rate(int(mid["is_error"].sum()), len(mid)),
        "mistakes+blunders per 100 moves with >=25% clock": _rate(int(calm["is_error"].sum()), len(calm)),
        "% of my moves made under 10% clock": _rate(int((me["clock_frac"] < 0.10).sum()), len(me)),
        "% of opp moves made under 10% clock": _rate(int((opp["clock_frac"] < 0.10).sum()), len(opp)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="start of the new window, YYYY-MM-DD")
    ap.add_argument("--skip-download", action="store_true")
    a = ap.parse_args()
    if not a.skip_download:
        download.download_all()
        parse.build_table()
    engine.run(per_control=None, since=a.since)
    plies = errors.classify(errors.load_plies())
    plies.to_parquet(DATA_DIR / "processed" / f"plies_d{engine.DEPTH}.parquet", index=False)

    games = load_games()
    cut = pd.Timestamp(a.since, tz="UTC")
    windows = {"baseline": games[games["start_time"] < cut].tail(BASELINE_N),
               "new": games[games["start_time"] >= cut]}
    table = {}
    for name, g in windows.items():
        m = game_metrics(g)
        m.update(engine_metrics(plies[plies["url"].isin(g["url"])]))
        table[name] = m
    print(pd.DataFrame(table).to_markdown())


if __name__ == "__main__":
    main()
