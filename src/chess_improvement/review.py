"""Post-session review: engine-check the games I just played and show where I went wrong.

By default it reviews every rated 3+0/5+0 game since the last review (capped at 20 games), then:
  - prints each game's mistakes and blunders, labelled "missed THEIR threat" or "missed MY chance",
    with clock, opponent's last move, best move and a lichess link
  - prints a one-line session scorecard (missed threats per game, time trouble, flags)
  - adds the clean positions to the drill deck (drills.py), so they come back in drill.py
  - appends the scorecard to data/drills/review_log.csv, to track the trend

Run straight after a sitting (about 1 minute of compute for ~6 games):
    uv run python -m chess_improvement.review
    uv run python -m chess_improvement.review --last 10      # or a fixed number of recent games
"""
from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd

from . import download, engine, parse
from .config import DATA_DIR, GAMES_TABLE
from .drills import THREAT, add_to_deck, candidates, is_pawn_grab
from .errors import classify

STATE = DATA_DIR / "drills" / "last_review.txt"
LOG = DATA_DIR / "drills" / "review_log.csv"


def pick_games(last: int | None, cap: int = 20) -> pd.DataFrame:
    g = pd.read_parquet(GAMES_TABLE)
    g = g[g["rated"] & g["time_control"].isin(engine.CONTROLS) & (g["n_plies"] >= 10)].sort_values("start_time")
    if last:
        return g.tail(last)
    if STATE.exists():
        since = pd.Timestamp(STATE.read_text().strip())
        g = g[g["end_time"] > since]
    else:
        g = g[g["start_time"].dt.date == g["start_time"].dt.date.max()]  # first run: the latest day played
    return g.tail(cap)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, help="review this many most recent games instead")
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    if not a.no_download:
        download.download_all()
        parse.build_table()
    games = pick_games(a.last)
    if games.empty:
        print("No new games since the last review.")
        return
    cols = ["url", "pgn", "colour", "time_control", "base_s", "increment_s"]
    todo = games[cols].to_dict("records")
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=8) as pool:
        list(pool.map(engine.analyse_game, todo))
    files = [engine.cache_dir() / f"{u.rsplit('/', 1)[-1]}.parquet" for u in games["url"]]
    plies = classify(pd.concat([pd.read_parquet(f) for f in files], ignore_index=True))
    plies = plies.sort_values(["url", "ply"])
    plies["opp_last_san"] = plies.groupby("url")["played_san"].shift()

    n_threat = n_chance = 0
    for _, gm in games.iterrows():
        p = plies[(plies["url"] == gm["url"]) & plies["is_me"] & plies["is_error"]]
        res = {1.0: "WIN", 0.5: "draw", 0.0: "loss"}[gm["score"]]
        print(f"\n{res:4} {CONTROL[gm['time_control']]} as {gm['colour']} vs {gm['opp_rating']:.0f}, "
              f"{gm['opening']} ({gm['termination']}, {gm['n_moves']} moves)  {gm['url']}")
        for _, r in p.iterrows():
            tag = "missed THEIR threat" if r["theme"] in THREAT else (
                  "missed MY chance" if r["error_kind"] == "missed chance" else "positional/other")
            if is_pawn_grab(r["fen"], r["played_uci"]):
                tag += "  ⚠ PAWN GRAB (my riskiest move type: ask 'after I take, what are their checks?')"
            n_threat += r["theme"] in THREAT
            n_chance += r["error_kind"] == "missed chance"
            print(f"   move {r['move_no']:>2} [{r['clock_frac']:.0%} clock] after {r['opp_last_san'] or '-'}: "
                  f"played {r['played_san']}, best {r['best_san']} ({r['wp_before']:.0%}→{r['wp_after']:.0%}) "
                  f"{r['severity']}, {tag}\n      https://lichess.org/analysis/{r['fen'].replace(' ', '_')}")
        if p.empty:
            print("   no mistakes or blunders 👍")

    me = plies[plies["is_me"]]
    flags = int(((games["score"] == 0) & (games["termination"] == "timeout")).sum())
    card = {"date": dt.date.today().isoformat(), "games": len(games), "score": games["score"].mean(),
            "missed_threats_per_game": n_threat / len(games), "missed_chances_per_game": n_chance / len(games),
            "blunders_per_100_moves": 100 * (me["severity"] == "blunder").mean(),
            "pct_moves_under_10pct_clock": 100 * (me["clock_frac"] < 0.10).mean(), "lost_on_time": flags}
    print("\nSESSION SCORECARD  (baseline: 1.0 missed threats/game, 3.6 blunders/100 moves, 7% of moves under 10% clock)")
    print("  " + "  ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in card.items()))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([card]).to_csv(LOG, mode="a", header=not LOG.exists(), index=False)

    added = add_to_deck(candidates(plies))
    print(f"\n{added} new position(s) added to your drill deck.")
    STATE.write_text(games["end_time"].max().isoformat())


CONTROL = {"180": "3+0", "300": "5+0"}

if __name__ == "__main__":
    main()
