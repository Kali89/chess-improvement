"""Phase 3a: run Stockfish over a sample of games and record a per-ply evaluation table.

Every position in each sampled game is analysed once, at a fixed depth. The evaluation of
position i (before move i) and of position i+1 (after it) together give the cost of move i.
Both players' moves are stored, so my error rates can be compared with my opponents' as a
same-rating baseline.

Cache: data/engine/d{DEPTH}/<game_id>.parquet, one file per game. Re-runs skip finished games,
and an interrupted run resumes where it stopped.

Run:
    uv run python -m chess_improvement.engine --per-control 15      # pilot
    uv run python -m chess_improvement.engine --per-control 150     # main run
"""
from __future__ import annotations

import argparse
import io
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import pandas as pd

from .config import DATA_DIR, GAMES_TABLE

STOCKFISH = "/opt/homebrew/bin/stockfish"
DEPTH = 16
PV_PLIES = 10  # how far along the engine's main line to look when measuring material swings
PIECE_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
CONTROLS = ("180", "300")


def cache_dir(depth: int = DEPTH) -> Path:
    return DATA_DIR / "engine" / f"d{depth}"


def material(board: chess.Board, colour: chess.Color) -> int:
    """Material (P=1, N=B=3, R=5, Q=9) of one side."""
    return sum(PIECE_VALUE[p.piece_type] for p in board.piece_map().values() if p.color == colour)


def balance(board: chess.Board, pov: chess.Color) -> int:
    """Material balance from pov's side: mine minus theirs."""
    return material(board, pov) - material(board, not pov)


def hanging_capture(board: chess.Board, reply: chess.Move | None) -> int:
    """If `reply` captures a piece worth >= 3 that was undefended, or defended but captured by a
    cheaper attacker, return the captured piece's value; otherwise 0.

    `board` is the position *after my move*, with my opponent to move. Cheap "did I hang a piece?" test.
    """
    if reply is None or not board.is_capture(reply) or board.is_en_passant(reply):
        return 0
    victim = board.piece_at(reply.to_square)
    attacker = board.piece_at(reply.from_square)
    if victim is None or attacker is None or PIECE_VALUE[victim.piece_type] < 3:
        return 0
    defended = bool(board.attackers(victim.color, reply.to_square))
    cheaper = PIECE_VALUE[attacker.piece_type] < PIECE_VALUE[victim.piece_type]
    return PIECE_VALUE[victim.piece_type] if (not defended or cheaper) else 0


def non_pawn_material(board: chess.Board) -> int:
    """Total N/B/R/Q material for both sides combined (starting position = 62)."""
    return sum(PIECE_VALUE[p.piece_type] for p in board.piece_map().values()
               if p.piece_type not in (chess.PAWN, chess.KING))


def endgame_type(board: chess.Board) -> str:
    """Coarse endgame label from the pieces on the board (ignoring kings and pawns)."""
    kinds = {p.piece_type for p in board.piece_map().values() if p.piece_type not in (chess.PAWN, chess.KING)}
    if not kinds:
        return "pawn"
    if kinds == {chess.ROOK}:
        return "rook"
    if kinds <= {chess.KNIGHT, chess.BISHOP}:
        return "minor piece"
    if kinds == {chess.QUEEN}:
        return "queen"
    if chess.QUEEN not in kinds and chess.ROOK in kinds:
        return "rook + minor"
    return "queen + other"


def win_prob(score: chess.engine.PovScore, pov: chess.Color) -> float:
    """Win probability (0-1) for pov, using lichess's centipawn-to-winning-chances curve (handles mates)."""
    return score.pov(pov).wdl(model="lichess").expectation()


def cp(score: chess.engine.PovScore, pov: chess.Color) -> int:
    """Centipawns from pov, with mates clamped to ±10000 (sign kept)."""
    return score.pov(pov).score(mate_score=10000)


def analyse_game(row: dict, depth: int = DEPTH) -> int:
    """Analyse every position of one game and write its per-ply parquet. Returns number of plies."""
    out = cache_dir(depth) / f"{row['url'].rsplit('/', 1)[-1]}.parquet"
    if out.exists():
        return 0
    game = chess.pgn.read_game(io.StringIO(row["pgn"]))
    me = chess.WHITE if row["colour"] == "white" else chess.BLACK
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    engine.configure({"Threads": 1, "Hash": 64})
    try:
        board = game.board()
        nodes = list(game.mainline())
        # Analyse each position once: before move 1, then after every move.
        infos = []
        positions = [board.copy()]
        for node in nodes:
            board.push(node.move)
            positions.append(board.copy())
        for pos in positions:
            if pos.is_game_over():
                infos.append(None)
            else:
                infos.append(engine.analyse(pos, chess.engine.Limit(depth=depth)))
    finally:
        engine.quit()

    clocks = {chess.WHITE: row["base_s"], chess.BLACK: row["base_s"]}
    rows = []
    for i, node in enumerate(nodes):
        before, after = positions[i], positions[i + 1]
        mover = before.turn
        info_b, info_a = infos[i], infos[i + 1]
        wp_before = win_prob(info_b["score"], mover)
        if info_a is None:  # game over after this move
            wp_after = 1.0 if after.is_checkmate() else 0.5
            cp_after, reply, pv_after = (10000 if after.is_checkmate() else 0), None, []
        else:
            wp_after = win_prob(info_a["score"], mover)
            cp_after = cp(info_a["score"], mover)
            pv_after = info_a.get("pv", [])
            reply = pv_after[0] if pv_after else None
        best_pv = info_b.get("pv", [])
        best = best_pv[0] if best_pv else None
        clk = node.clock()
        clock_before = clocks[mover]
        if clk is not None:
            clocks[mover] = clk
        npm = non_pawn_material(before)
        rows.append({
            "url": row["url"], "tc": row["time_control"], "ply": i + 1, "move_no": i // 2 + 1,
            "is_me": mover == me, "fen": before.fen(), "played_uci": node.move.uci(),
            "played_san": before.san(node.move), "best_uci": best.uci() if best else None,
            "best_san": before.san(best) if best else None,
            "cp_before": cp(info_b["score"], mover), "cp_after": cp_after,
            "wp_before": wp_before, "wp_after": wp_after,
            "wp_loss": max(0.0, wp_before - wp_after),
            "clock_before": clock_before, "clock_frac": clock_before / row["base_s"],
            "time_spent": (clock_before - clk + row["increment_s"]) if clk is not None else None,
            "non_pawn_material": npm, "endgame_type": endgame_type(before),
            # Engine main lines (UCI, space-separated) so material swings can be measured
            # downstream relative to the position *before* the move (see errors.py).
            "best_pv": " ".join(m.uci() for m in best_pv[:PV_PLIES + 1]),
            "reply_pv": " ".join(m.uci() for m in pv_after[:PV_PLIES]),
            "hung_piece_value": hanging_capture(after, reply),
            "allowed_mate": info_a is not None and info_a["score"].pov(not mover).is_mate()
                            and info_a["score"].pov(not mover).mate() > 0,
            "missed_mate": info_b["score"].pov(mover).is_mate() and info_b["score"].pov(mover).mate() > 0
                           and not (info_a is None or (info_a["score"].pov(mover).is_mate()
                                                       and info_a["score"].pov(mover).mate() > 0)),
        })
    pd.DataFrame(rows).to_parquet(out, index=False)
    return len(rows)


def select_games(per_control: int | None = None, since: str | None = None,
                 between: tuple[str, str] | None = None, seed: int = 0) -> pd.DataFrame:
    """Rated 3+0 / 5+0 games to analyse. Three ways to choose them:
      - since:   every game from this date onwards
      - between: a random sample of `per_control` games per control from [start, end)
      - default: the most recent `per_control` games per control
    """
    df = pd.read_parquet(GAMES_TABLE)
    df = df[df["rated"] & df["time_control"].isin(CONTROLS) & (df["n_plies"] >= 10)]
    if since is not None:
        return df[df["start_time"] >= pd.Timestamp(since, tz="UTC")]
    if between is not None:
        lo, hi = (pd.Timestamp(x, tz="UTC") for x in between)
        w = df[(df["start_time"] >= lo) & (df["start_time"] < hi)]
        return pd.concat([g.sample(min(per_control, len(g)), random_state=seed)
                          for _, g in w.groupby("time_control")])
    return df.sort_values("start_time").groupby("time_control").tail(per_control)


def run(per_control: int | None = 150, depth: int = DEPTH, workers: int = 8,
        since: str | None = None, between: tuple[str, str] | None = None) -> None:
    cache_dir(depth).mkdir(parents=True, exist_ok=True)
    games = select_games(per_control, since, between)
    cols = ["url", "pgn", "colour", "time_control", "base_s", "increment_s"]
    todo = [r for r in games[cols].to_dict("records")
            if not (cache_dir(depth) / f"{r['url'].rsplit('/', 1)[-1]}.parquet").exists()]
    print(f"{len(games)} games selected, {len(todo)} not yet cached; depth {depth}, {workers} workers")
    t0, plies = time.time(), 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(analyse_game, r, depth) for r in todo]
        for k, f in enumerate(as_completed(futures), 1):
            plies += f.result()
            if k % 10 == 0 or k == len(todo):
                el = time.time() - t0
                print(f"  {k}/{len(todo)} games, {plies} plies, {el:.0f}s elapsed, "
                      f"{plies / max(el, 1e-9):.1f} plies/s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-control", type=int, default=150)
    ap.add_argument("--depth", type=int, default=DEPTH)
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4))
    ap.add_argument("--since", help="analyse all games since this date (YYYY-MM-DD) instead")
    ap.add_argument("--between", nargs=2, metavar=("START", "END"),
                    help="random sample of --per-control games per control from [START, END)")
    a = ap.parse_args()
    run(a.per_control, a.depth, a.workers, a.since, tuple(a.between) if a.between else None)
