"""Build and maintain a personal drill deck from my own engine-classified mistakes.

A drill is the position *before* one of my mistakes, with my opponent's previous move shown, because
most of my errors come from not asking what that move threatens. Each position is checked at higher
depth with two candidate moves, and kept only if the best move is clearly better than the second-best
(a unique answer), so the drill can be marked right or wrong.

Deck: data/drills/deck.csv (personal state, not committed)
  id, fen, theme, prompt fields, best move and line, plus Leitner spaced-repetition state
  (box 1-5, due date). Boxes come round after 1, 3, 7, 16 and 35 days. A pass moves a drill up a
  box; a fail sends it back to box 1.

Run:  uv run python -m chess_improvement.drills --build     # (re)build the deck from all analysed games
"""
from __future__ import annotations

import argparse
import datetime as dt

import chess
import chess.engine
import pandas as pd

from .config import DATA_DIR
from .engine import DEPTH, STOCKFISH
from .errors import THREAT, classify, load_plies

DECK = DATA_DIR / "drills" / "deck.csv"
VERIFY_DEPTH = 18
MIN_GAP = 0.15            # best move must beat the second-best by >= 15 win-prob points
BOX_DAYS = {1: 1, 2: 3, 3: 7, 4: 16, 5: 35}
DRILL_THEMES = THREAT | {"missed tactic", "missed mate"}


def candidates(plies: pd.DataFrame) -> pd.DataFrame:
    """My clear errors in undecided positions, played with time on the clock, with the opponent's last move attached."""
    plies = plies.sort_values(["url", "ply"])
    plies["opp_last_san"] = plies.groupby("url")["played_san"].shift()
    c = plies[plies["is_me"] & plies["is_error"] & plies["theme"].isin(DRILL_THEMES)
              & plies["wp_before"].between(0.20, 0.90) & (plies["clock_frac"] >= 0.15)]
    return c.sort_values("wp_loss", ascending=False).groupby("url").head(2)


def verify(fens: list[str], engine: chess.engine.SimpleEngine) -> pd.DataFrame:
    """Depth-18 best move, its line, and the win-prob gap to the second-best move, for each FEN."""
    rows = []
    for fen in fens:
        board = chess.Board(fen)
        infos = engine.analyse(board, chess.engine.Limit(depth=VERIFY_DEPTH), multipv=2)
        wp = [i["score"].pov(board.turn).wdl(model="lichess").expectation() for i in infos]
        pv = infos[0]["pv"]
        rows.append({"fen": fen, "best_san_v": board.san(pv[0]), "best_uci_v": pv[0].uci(),
                     "line": board.variation_san(pv[:6]), "wp_best": wp[0],
                     "gap": wp[0] - wp[1] if len(wp) > 1 else 1.0})
    return pd.DataFrame(rows)


def is_pawn_grab(fen: str, uci: str) -> bool:
    """True if the move played captures a pawn (including en passant): my riskiest move type."""
    b = chess.Board(fen)
    m = chess.Move.from_uci(uci)
    c = b.piece_at(m.to_square)
    return b.is_en_passant(m) or bool(c and c.piece_type == chess.PAWN)


def load_deck() -> pd.DataFrame:
    return pd.read_csv(DECK, dtype={"id": str}) if DECK.exists() else pd.DataFrame()


def save_deck(deck: pd.DataFrame) -> None:
    DECK.parent.mkdir(parents=True, exist_ok=True)
    deck.to_csv(DECK, index=False)


def add_to_deck(cands: pd.DataFrame, max_new: int | None = None) -> int:
    """Verify candidates not already in the deck and add those with a unique answer. Returns the number added."""
    deck = load_deck()
    have = set(deck["fen"]) if len(deck) else set()
    new = cands[~cands["fen"].isin(have)]
    if max_new:
        new = new.head(max_new)
    if new.empty:
        return 0
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    engine.configure({"Threads": 8, "Hash": 512})
    try:
        v = verify(new["fen"].tolist(), engine)
    finally:
        engine.quit()
    m = new.merge(v, on="fen")
    m = m[m["gap"] >= MIN_GAP]
    today = dt.date.today().isoformat()
    add = pd.DataFrame({
        "id": m["url"].str.rsplit("/", n=1).str[-1] + "-" + m["ply"].astype(str),
        "fen": m["fen"], "theme": m["theme"], "tc": m["tc"], "move_no": m["move_no"],
        "opp_last_san": m["opp_last_san"], "played_san": m["played_san"],
        "pawn_grab": [is_pawn_grab(f, u) for f, u in zip(m["fen"], m["played_uci"])],
        "best_san": m["best_san_v"], "best_uci": m["best_uci_v"], "line": m["line"],
        "wp_before": m["wp_before"].round(3), "wp_after": m["wp_after"].round(3), "url": m["url"],
        "box": 1, "due": today, "attempts": 0, "passes": 0, "added": today,
    })
    save_deck(pd.concat([deck, add], ignore_index=True))
    return len(add)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="add drills from every analysed game")
    ap.add_argument("--max-new", type=int, default=150, help="cap on positions verified in this run")
    ap.add_argument("--pawn-grabs-first", action="store_true", help="verify pawn-grab mistakes before others")
    a = ap.parse_args()
    if a.build:
        cands = candidates(classify(load_plies(DEPTH)))
        if a.pawn_grabs_first:
            grab = [is_pawn_grab(f, u) for f, u in zip(cands["fen"], cands["played_uci"])]
            cands = cands.assign(_g=grab).sort_values(["_g", "wp_loss"], ascending=False).drop(columns="_g")
        print(f"{len(cands)} candidate positions; verifying up to {a.max_new} new ones at depth {VERIFY_DEPTH}...")
        n = add_to_deck(cands, a.max_new)
        deck = load_deck()
        print(f"added {n}; deck now {len(deck)} drills:\n{deck['theme'].value_counts().to_string()}")


if __name__ == "__main__":
    main()
