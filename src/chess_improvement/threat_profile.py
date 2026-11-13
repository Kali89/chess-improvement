"""Profile HOW I miss my opponent's threats, so training can target the exact pattern.

For each of my 'missed threat' errors (allowed tactic / hung piece / allowed mate) it records:
  - my mistaken move: capture, check or quiet; pawn grab; did the moved piece end up the victim?
  - context: was the opponent's previous move a capture (mid-exchange) or a check?
  - the punishing reply (engine's first move): check, capture, or quiet (quiet = harder to see)
  - fork: after the reply, the replying piece attacks the king or two-plus pieces worth >= 3
  - allowed mates: back-rank pattern (my king on its home rank, mated by a rook/queen on that rank)
Compared with my opponents' missed threats as a baseline.

Output: reports/threat_profile.md

Run:  uv run python -m chess_improvement.threat_profile
"""
from __future__ import annotations

import chess
import pandas as pd

from .config import DATA_DIR, REPORTS_DIR
from .engine import DEPTH, PIECE_VALUE


def features(r: pd.Series, prev_san: str | None) -> dict:
    board = chess.Board(r["fen"])
    me = board.turn
    mv = chess.Move.from_uci(r["played_uci"])
    moved = board.piece_at(mv.from_square)
    captured = board.piece_at(mv.to_square)
    f = {
        "my_move": "capture" if board.is_capture(mv) else ("check" if board.gives_check(mv) else "quiet"),
        "pawn_grab": bool(captured and captured.piece_type == chess.PAWN),
        "moved_piece": chess.piece_name(moved.piece_type) if moved else None,
        "after_opp_capture": bool(prev_san and "x" in prev_san),
        "after_opp_check": bool(prev_san and "+" in prev_san),
    }
    board.push(mv)
    reply_uci = (r["reply_pv"] or "").split()[:1]
    if not reply_uci:
        return f | {"reply": None, "fork": False, "victim_is_moved_piece": False, "back_rank_mate": False}
    reply = chess.Move.from_uci(reply_uci[0])
    f["reply"] = "check" if board.gives_check(reply) else ("capture" if board.is_capture(reply) else "quiet")
    f["victim_is_moved_piece"] = board.is_capture(reply) and reply.to_square == mv.to_square
    board.push(reply)
    # Fork: the replying piece now attacks the king or 2+ of my pieces worth >= 3.
    attacked = [board.piece_at(s) for s in board.attacks(reply.to_square)]
    mine = [p for p in attacked if p and p.color == me]
    big = [p for p in mine if PIECE_VALUE[p.piece_type] >= 3]
    king = any(p.piece_type == chess.KING for p in mine)
    f["fork"] = (len(big) + king) >= 2
    # Back-rank mate: replay the mating line and look at the final position.
    f["back_rank_mate"] = False
    if r["theme"] == "allowed mate":
        b = chess.Board(r["fen"])
        b.push(mv)
        for u in (r["reply_pv"] or "").split():
            m = chess.Move.from_uci(u)
            if not b.is_legal(m):
                break
            b.push(m)
        if b.is_checkmate():
            ksq = b.king(me)
            home = 0 if me == chess.WHITE else 7
            last = b.peek()
            mater = b.piece_at(last.to_square)
            f["back_rank_mate"] = (chess.square_rank(ksq) == home and mater is not None
                                   and mater.piece_type in (chess.ROOK, chess.QUEEN)
                                   and chess.square_rank(last.to_square) == home)
    return f


def main() -> None:
    p = pd.read_parquet(DATA_DIR / "processed" / f"plies_d{DEPTH}.parquet").sort_values(["url", "ply"])
    p["prev_san"] = p.groupby("url")["played_san"].shift()
    t = p[p["error_kind"] == "missed threat"].copy()
    feats = pd.DataFrame([features(r, r["prev_san"]) for _, r in t.iterrows()], index=t.index)
    t = t.join(feats)
    t["who"] = t["is_me"].map({True: "me", False: "opp"})
    n_moves = p.groupby("is_me").size().rename({True: "me", False: "opp"})

    def share(col: str) -> pd.DataFrame:
        c = pd.crosstab(t[col], t["who"])
        per100 = (c / n_moves * 100).round(2).add_suffix(" /100 moves")
        return pd.concat([c, per100], axis=1)

    md = ["# How I miss threats (me vs my opponents, same games)\n",
          f"{int(t['is_me'].sum())} of my missed-threat errors, {int((~t['is_me']).sum())} of my opponents', "
          f"in {p['url'].nunique()} games.\n"]
    for col, title in [("reply", "The punishing reply"), ("my_move", "My mistaken move was a..."),
                       ("fork", "Reply is a fork"), ("victim_is_moved_piece", "The piece I just moved is the one taken"),
                       ("after_opp_capture", "Mistake came right after the opponent captured"),
                       ("after_opp_check", "Mistake came right after a check"), ("pawn_grab", "My move grabbed a pawn"),
                       ("moved_piece", "Piece I moved"), ("phase", "Phase")]:
        md += [f"## {title}", share(col).to_markdown()]
    mates = t[t["theme"] == "allowed mate"]
    md += ["## Allowed mates: back-rank pattern", pd.crosstab(mates["back_rank_mate"], mates["who"]).to_markdown()]
    (REPORTS_DIR / "threat_profile.md").write_text("\n\n".join(md) + "\n")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
