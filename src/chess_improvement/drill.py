"""Interactive spaced-repetition trainer for my own mistakes (the deck built by drills.py).

Each drill shows the board from my side and my opponent's last move. I type a move in SAN (e.g. Nf3,
exd5, O-O). It's marked a pass if it's the engine's best move, or if Stockfish rates it within
7 win-probability points of the best (an equally good alternative). Passes move a drill up a Leitner
box, so it comes back later; fails send it back to box 1, so it comes back tomorrow.

The habit being trained: before choosing a move, say what the opponent's last move threatens. The
prompt asks for that first. Nothing checks it, but saying it is the point.

Run:
    uv run python -m chess_improvement.drill            # today's due drills (up to 8), in the browser
    uv run python -m chess_improvement.drill --terminal # text board instead
    uv run python -m chess_improvement.drill --n 15
    uv run python -m chess_improvement.drill --stats
"""
from __future__ import annotations

import argparse
import datetime as dt
import random

import chess
import chess.engine
import pandas as pd

from .drills import THREAT, load_deck
from .engine import STOCKFISH

ACCEPT_WITHIN = 0.07
GRADE_DEPTH = 16


def show(board: chess.Board) -> None:
    print(board.unicode(borders=True, empty_square="·", orientation=board.turn))


def grade(board: chess.Board, move: chess.Move, best_uci: str, engine: chess.engine.SimpleEngine) -> tuple[bool, float, float]:
    """(passed, my win prob after the move, best win prob), both from the mover's point of view."""
    pov = board.turn
    best = engine.analyse(board, chess.engine.Limit(depth=GRADE_DEPTH))["score"].pov(pov).wdl(model="lichess").expectation()
    if move.uci() == best_uci:
        return True, best, best
    after = board.copy()
    after.push(move)
    if after.is_checkmate():
        return True, 1.0, best
    mine = engine.analyse(after, chess.engine.Limit(depth=GRADE_DEPTH))["score"].pov(pov).wdl(model="lichess").expectation()
    return mine >= best - ACCEPT_WITHIN, mine, best


def ask_move(board: chess.Board) -> chess.Move | None:
    while True:
        raw = input("  Your move (SAN, or 'skip'): ").strip()
        if raw.lower() in {"skip", "s", ""}:
            return None
        try:
            return board.parse_san(raw)
        except ValueError:
            print("  Not a legal move in this position, try again.")


def run_session(deck: pd.DataFrame, idx: list[int], engine: chess.engine.SimpleEngine) -> None:
    from .drill_web import record
    passed = 0
    for k, i in enumerate(idx, 1):
        d = deck.loc[i]
        board = chess.Board(d["fen"])
        side = "White" if board.turn == chess.WHITE else "Black"
        print(f"\n━━━ Drill {k}/{len(idx)}  ({d['tc']}, move {d['move_no']}, you're {side}, "
              f"about {d['wp_before']:.0%} to win) ━━━")
        if isinstance(d["opp_last_san"], str):
            print(f"  Opponent just played: {d['opp_last_san']}")
        show(board)
        input("  First: what does their last move threaten / what are their checks and captures? (Enter when you've said it) ")
        move = ask_move(board)
        if move is None:
            ok, mine, best = False, float("nan"), float("nan")
        else:
            ok, mine, best = grade(board, move, d["best_uci"], engine)
        verdict = "✅ PASS" if ok else "❌ miss"
        print(f"  {verdict}" + (f": your move keeps {mine:.0%} (best {best:.0%})" if move else ""))
        print(f"  Best: {d['best_san']}   line: {d['line']}")
        kind = "you missed their threat" if d["theme"] in THREAT else "you missed a chance"
        print(f"  In the game you played {d['played_san']} ({d['theme']}: {kind}; win chance fell to {d['wp_after']:.0%})")
        print(f"  Board: https://lichess.org/analysis/{d['fen'].replace(' ', '_')}   Game: {d['url']}")
        record(deck, i, ok)  # saves after every drill so quitting midway loses nothing
        passed += ok
    print(f"\nSession: {passed}/{len(idx)} passed.")


def stats(deck: pd.DataFrame) -> None:
    today = dt.date.today().isoformat()
    print(f"{len(deck)} drills, {int((deck['due'] <= today).sum())} due today")
    print("by Leitner box (5 = well learned):\n" + deck["box"].value_counts().sort_index().to_string())
    tried = deck[deck["attempts"] > 0]
    if len(tried):
        by = tried.groupby("theme")[["passes", "attempts"]].sum()
        by["pass_rate"] = (by["passes"] / by["attempts"]).round(2)
        print("\npass rate by theme:\n" + by.to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--theme", help="only this theme, e.g. 'allowed tactic'")
    ap.add_argument("--pawn-grabs", action="store_true", help="only positions where I grabbed a pawn and got punished")
    ap.add_argument("--all", action="store_true", help="ignore due dates")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--terminal", action="store_true", help="old text board in the terminal instead of the browser")
    a = ap.parse_args()
    deck = load_deck()
    if deck.empty:
        print("Deck is empty: run `uv run python -m chess_improvement.drills --build` first.")
        return
    if a.stats:
        stats(deck)
        return
    pool = deck if a.all else deck[deck["due"] <= dt.date.today().isoformat()]
    if a.theme:
        pool = pool[pool["theme"] == a.theme]
    if a.pawn_grabs:
        pool = pool[pool["pawn_grab"]]
    idx = list(pool.index)
    random.shuffle(idx)
    # Most overdue / lowest box first, then random within that.
    idx = sorted(idx, key=lambda i: (deck.loc[i, "box"], deck.loc[i, "due"]))[: a.n]
    if not idx:
        print("Nothing due today. Use --all to practise anyway.")
        return
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    engine.configure({"Threads": 4, "Hash": 128})
    try:
        if a.terminal:
            run_session(deck, idx, engine)
        else:
            from .drill_web import serve
            serve(deck, idx, engine)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped; progress saved.")
    finally:
        engine.quit()


if __name__ == "__main__":
    main()
