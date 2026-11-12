"""Phase 1b: turn cached monthly JSON archives into one tidy row-per-game table.

Output: data/processed/games.parquet

Decisions worth knowing about:
- Only standard chess (rules == "chess") is kept; variants are dropped.
- Daily (correspondence) games are dropped too: there are only 7 and they aren't comparable.
- Unrated games are kept but flagged with `rated`. The analyses filter on it.
- chess.com's archive ratings are POST-game (verified: my rating moves ±8 within the same
  game's record). Pre-game ratings are reconstructed in `_pre_game_ratings`. Using post-game
  ratings would leak the result into the rating difference.
- PGN headers and [%clk] comments are parsed with regexes, not python-chess. That's
  about 50x faster for 14k games, and the engine phase re-parses the moves properly anyway.

Run:  uv run python -m chess_improvement.parse
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from .config import GAMES_TABLE, PROCESSED_DIR, RAW_DIR, USERNAME

HEADER_RE = re.compile(r'^\[(\w+) "(.*)"\]$', re.MULTILINE)
CLK_RE = re.compile(r"\[%clk (\d+):(\d+):(\d+(?:\.\d+)?)\]")

# chess.com's per-player result codes, mapped to my score and a coarse "how it ended".
DRAW_CODES = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


def _score(my_result: str) -> float:
    """My game score: 1 for a win, 0.5 for a draw, 0 for a loss."""
    if my_result == "win":
        return 1.0
    if my_result in DRAW_CODES:
        return 0.5
    return 0.0


def _termination(my_result: str, opp_result: str) -> str:
    """How the game ended, from the loser's code (or the draw code).

    Returns one of: checkmate, resignation, timeout, abandoned, draw_<code>, or other.
    """
    if my_result in DRAW_CODES:
        return f"draw_{my_result}"
    loser_code = opp_result if my_result == "win" else my_result
    return {
        "checkmated": "checkmate",
        "resigned": "resignation",
        "timeout": "timeout",
        "abandoned": "abandoned",
    }.get(loser_code, "other")


def _clocks(pgn: str) -> list[float]:
    """Remaining clock in seconds after each ply, in move order (alternating White, Black)."""
    return [int(h) * 3600 + int(m) * 60 + float(s) for h, m, s in CLK_RE.findall(pgn)]


def _parse_time_control(tc: str) -> tuple[float, float]:
    """'180+2' -> (180.0, 2.0). Base and increment, in seconds."""
    base, _, inc = tc.partition("+")
    return float(base), float(inc or 0)


def parse_game(g: dict) -> dict | None:
    """Flatten one chess.com game object into a row from my point of view.

    Returns None for games I'm not in (shouldn't happen) or that are filtered out.
    """
    if g.get("rules") != "chess" or g.get("time_class") == "daily":
        return None
    if g["white"]["username"].lower() == USERNAME:
        colour, me, opp = "white", g["white"], g["black"]
    elif g["black"]["username"].lower() == USERNAME:
        colour, me, opp = "black", g["black"], g["white"]
    else:
        return None

    pgn = g.get("pgn", "")
    headers = dict(HEADER_RE.findall(pgn))
    clocks = _clocks(pgn)
    # Split clocks into mine and my opponent's. White's clocks are the even plies.
    my_clocks = clocks[0::2] if colour == "white" else clocks[1::2]
    opp_clocks = clocks[1::2] if colour == "white" else clocks[0::2]
    base, inc = _parse_time_control(g["time_control"])
    eco_url = headers.get("ECOUrl", g.get("eco", ""))
    opening = eco_url.rsplit("/", 1)[-1].replace("-", " ") if eco_url else None
    accuracies = g.get("accuracies") or {}

    return {
        "url": g["url"],
        "end_time": pd.Timestamp(g["end_time"], unit="s", tz="UTC"),
        "start_time_utc": headers.get("UTCDate", "") + " " + headers.get("UTCTime", ""),
        "rated": g.get("rated", True),
        "time_class": g["time_class"],
        "time_control": g["time_control"],
        "base_s": base,
        "increment_s": inc,
        "colour": colour,
        "my_rating_post": me["rating"],
        "opp_rating_post": opp["rating"],
        "opponent": opp["username"],
        "my_result_code": me["result"],
        "opp_result_code": opp["result"],
        "score": _score(me["result"]),
        "termination": _termination(me["result"], opp["result"]),
        "eco": headers.get("ECO"),
        "opening": opening,
        "n_plies": len(clocks),
        "n_moves": (len(clocks) + 1) // 2,  # full moves, rounded up
        "my_accuracy": accuracies.get(colour),
        "opp_accuracy": accuracies.get("black" if colour == "white" else "white"),
        "my_clocks": my_clocks,
        "opp_clocks": opp_clocks,
        "pgn": pgn,
    }


def _pre_game_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct pre-game ratings from the post-game ratings chess.com stores.

    Within each rating pool (time_class; 3+0 and 5+0 share the blitz pool), my rating
    change in game k is post_k - post_{k-1}. My pre-game rating is therefore the previous
    game's post-game rating. Only rated games move the rating, so unrated games take the
    current rating unchanged.

    The opponent's pre-game rating isn't observable. It's approximated as opp_post + my_change,
    i.e. assuming the change was equal and opposite. Glicko changes aren't exactly symmetric,
    but at chess.com's typical ±8 per game the error is a few points.

    The first rated game in each pool has no predecessor. Its change is assumed to be the
    pool's typical ±8 in the direction of the result (0 for a draw).
    """
    df = df.sort_values("start_time").copy()
    df["my_change"] = np.nan
    for _, idx in df[df["rated"]].groupby("time_class").groups.items():
        post = df.loc[idx, "my_rating_post"]
        df.loc[idx, "my_change"] = post.diff()
        first = idx[0]
        df.loc[first, "my_change"] = 8 * np.sign(df.loc[first, "score"] - 0.5)
    df["my_change"] = df["my_change"].fillna(0)  # unrated games
    df["my_rating"] = df["my_rating_post"] - df["my_change"]
    df["opp_rating"] = df["opp_rating_post"] + df["my_change"]
    df["rating_diff"] = df["my_rating"] - df["opp_rating"]
    return df


def build_table() -> pd.DataFrame:
    """Parse every cached archive and write the tidy games table. Returns it too."""
    rows = []
    for path in sorted(RAW_DIR.glob("*.json")):
        for g in json.loads(path.read_text()).get("games", []):
            row = parse_game(g)
            if row is not None:
                rows.append(row)
    df = pd.DataFrame(rows).drop_duplicates("url").sort_values("end_time").reset_index(drop=True)
    # Start time is the clock-on time from the headers. Fall back to end_time if it's missing.
    df["start_time"] = pd.to_datetime(df["start_time_utc"], format="%Y.%m.%d %H:%M:%S",
                                      errors="coerce", utc=True).fillna(df["end_time"])
    df = df.drop(columns="start_time_utc")
    df = _pre_game_ratings(df).reset_index(drop=True)
    df["date"] = df["start_time"].dt.date
    # Elo expected score, the formula chess.com's Glicko ratings approximate.
    df["expected_score"] = 1 / (1 + 10 ** (-df["rating_diff"] / 400))
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(GAMES_TABLE, index=False)
    df.drop(columns=["pgn", "my_clocks", "opp_clocks"]).to_csv(GAMES_TABLE.with_suffix(".csv"), index=False)
    return df


if __name__ == "__main__":
    df = build_table()
    print(f"{len(df)} games written to {GAMES_TABLE}")
    print(df.groupby(["time_class", "time_control"]).size())
    print("accuracy present:", df["my_accuracy"].notna().mean().round(3))
