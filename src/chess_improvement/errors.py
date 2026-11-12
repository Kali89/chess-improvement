"""Phase 3b: classify each move from the cached engine output.

Severity uses the drop in win probability (lichess's curve, 0-1 scale), so a 300cp slip in an
already-won position barely registers while the same slip at equality does:
    inaccuracy >= 0.10, mistake >= 0.20, blunder >= 0.30   (lichess's thresholds)

Phase (explicit, decided on the position *before* the move):
    endgame    : combined non-pawn material of both sides <= 26
                 (N=B=3, R=5, Q=9; the start is 62. Q+R vs Q+R = 28 is still a middlegame;
                 R+B vs R+N = 16 and Q vs Q = 18 are endgames)
    opening    : move number <= 10 and not an endgame
    middlegame : everything else

Theme for mistakes and blunders (first matching rule wins):
    allowed mate    : after my move the opponent has a forced mate
    hung piece      : opponent's best reply captures a piece (>= 3) of mine that was undefended or
                      defended but taken by a cheaper attacker, AND I end up >= 2 points down
                      along the engine line (so ordinary trades don't count)
    allowed tactic  : I end up >= 2 points of material down along the engine line,
                      relative to the position before my move
    missed mate     : I had a forced mate and my move lost it
    missed tactic   : the best line would have won >= 2 points of material and >= 2 more than
                      what I played
    positional/other: none of the above (often king safety, passed pawns, or a slow slide)
'Missed threat' = the first three, 'missed chance' = the next two.
"""
from __future__ import annotations

import chess
import numpy as np
import pandas as pd

from .config import DATA_DIR
from .engine import DEPTH, PV_PLIES, balance, cache_dir

SEVERITY_BINS = [-np.inf, 0.10, 0.20, 0.30, np.inf]
SEVERITY = ["ok", "inaccuracy", "mistake", "blunder"]
THREAT = {"allowed mate", "hung piece", "allowed tactic"}
CHANCE = {"missed mate", "missed tactic"}
ENDGAME_NPM = 26
CLOCK_BINS = [-0.01, 0.10, 0.25, 0.50, 1.01]
CLOCK_LABELS = ["<10%", "10-25%", "25-50%", ">50%"]
EVAL_BINS = [-0.01, 0.30, 0.70, 1.01]
EVAL_LABELS = ["losing (<30%)", "roughly level (30-70%)", "winning (>70%)"]


def line_net(fen: str, moves: list[str], pov: chess.Color) -> int:
    """Net material change for pov from `fen` after playing `moves` (UCI).

    Looks at the balance after each of the last two plies and keeps the worse one for pov,
    so a line truncated mid-exchange doesn't overstate a gain.
    """
    board = chess.Board(fen)
    start = balance(board, pov)
    seen = [start]
    for u in moves:
        mv = chess.Move.from_uci(u)
        if not board.is_legal(mv):
            break
        board.push(mv)
        seen.append(balance(board, pov))
    tail = seen[-2:] if len(seen) >= 2 else seen
    return min(tail) - start


def load_plies(depth: int = DEPTH) -> pd.DataFrame:
    files = sorted(cache_dir(depth).glob("*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def classify(df: pd.DataFrame) -> pd.DataFrame:
    """Add severity, phase, theme and context buckets to the per-ply table."""
    df = df.copy()
    df["tc"] = df["tc"].map({"180": "3+0", "300": "5+0"})
    df["severity"] = pd.cut(df["wp_loss"], SEVERITY_BINS, labels=SEVERITY, right=False)
    df["is_error"] = df["severity"].isin(["mistake", "blunder"])
    df["phase"] = np.where(df["non_pawn_material"] <= ENDGAME_NPM, "endgame",
                  np.where(df["move_no"] <= 10, "opening", "middlegame"))
    df["clock_bucket"] = pd.cut(df["clock_frac"], CLOCK_BINS, labels=CLOCK_LABELS)
    df["eval_bucket"] = pd.cut(df["wp_before"], EVAL_BINS, labels=EVAL_LABELS)

    # Material along the engine lines, measured only for errors (cheap enough either way).
    df["played_net"] = 0
    df["best_net"] = 0
    idx = df.index[df["is_error"]]
    for i in idx:
        r = df.loc[i]
        pov = chess.WHITE if " w " in r["fen"] else chess.BLACK
        reply = r["reply_pv"].split() if r["reply_pv"] else []
        best = r["best_pv"].split() if r["best_pv"] else []
        df.at[i, "played_net"] = line_net(r["fen"], [r["played_uci"]] + reply[:PV_PLIES], pov)
        df.at[i, "best_net"] = line_net(r["fen"], best, pov)

    conds = [
        df["allowed_mate"],
        (df["hung_piece_value"] >= 3) & (df["played_net"] <= -2),
        df["played_net"] <= -2,
        df["missed_mate"],
        (df["best_net"] >= 2) & (df["best_net"] - df["played_net"] >= 2),
    ]
    themes = ["allowed mate", "hung piece", "allowed tactic", "missed mate", "missed tactic"]
    df["theme"] = np.where(df["is_error"], np.select(conds, themes, "positional/other"), None)
    df["error_kind"] = np.where(df["theme"].isin(THREAT), "missed threat",
                       np.where(df["theme"].isin(CHANCE), "missed chance",
                       np.where(df["is_error"], "positional/other", None)))
    return df


if __name__ == "__main__":
    out = DATA_DIR / "processed" / f"plies_d{DEPTH}.parquet"
    df = classify(load_plies())
    df.to_parquet(out, index=False)
    print(f"{len(df)} plies from {df['url'].nunique()} games -> {out}")
