"""Phase 3d: verify and select instructive positions for practice.

Candidates come from engine_analysis.instructive(). Each is re-analysed at depth 20 with two
principal variations, and kept only if the best move is clearly better than the second-best
(win-probability gap >= 0.15). That way every position has one right answer, which is what makes
it useful to drill. Results are cached in data/engine/instructive_d20.parquet.

Run:  uv run python -m chess_improvement.instructive
"""
from __future__ import annotations

import chess
import chess.engine
import pandas as pd

from .config import DATA_DIR, REPORTS_DIR
from .engine import STOCKFISH
from .errors import THREAT

VERIFY_DEPTH = 20
MIN_GAP = 0.15
N_TARGET = 18
CACHE = DATA_DIR / "engine" / f"instructive_d{VERIFY_DEPTH}.parquet"


def verify(cands: pd.DataFrame) -> pd.DataFrame:
    """Add depth-20 best move, its win prob, and the gap to the second-best move. Cached by FEN."""
    done = pd.read_parquet(CACHE) if CACHE.exists() else pd.DataFrame(columns=["fen"])
    todo = cands[~cands["fen"].isin(done["fen"])]
    rows = []
    if len(todo):
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
        engine.configure({"Threads": 8, "Hash": 512})
        try:
            for fen in todo["fen"].unique():
                board = chess.Board(fen)
                infos = engine.analyse(board, chess.engine.Limit(depth=VERIFY_DEPTH), multipv=2)
                wp = [i["score"].pov(board.turn).wdl(model="lichess").expectation() for i in infos]
                pv = infos[0]["pv"]
                rows.append({"fen": fen, "v_best_san": board.san(pv[0]),
                             "v_line": board.variation_san(pv[:6]),
                             "v_wp_best": wp[0], "v_gap": wp[0] - wp[1] if len(wp) > 1 else 1.0})
        finally:
            engine.quit()
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
        done.to_parquet(CACHE, index=False)
    return cands.merge(done, on="fen", how="left")


def select(v: pd.DataFrame, n: int = N_TARGET) -> pd.DataFrame:
    """Keep the positions with a unique solution, then take a theme-balanced selection.

    Each theme gets slots in proportion to its share of candidates (at least 2 where available),
    filled with its largest errors.
    """
    v = v[v["v_gap"] >= MIN_GAP].copy()
    share = v["theme"].value_counts(normalize=True)
    quota = (share * n).round().clip(lower=2).astype(int)
    picked = pd.concat([v[v["theme"] == t].nlargest(q, "wp_loss") for t, q in quota.items()])
    return picked.nlargest(n, "wp_loss").sort_values(["theme", "wp_loss"], ascending=[True, False])


def lichess_link(fen: str) -> str:
    return "https://lichess.org/analysis/" + fen.replace(" ", "_")


def to_markdown(sel: pd.DataFrame) -> str:
    """Positions grouped by theme, with a 'find the move' prompt and a hidden answer per position."""
    out = []
    for theme, g in sel.groupby("theme", sort=False):
        kind = "spot the opponent's threat" if theme in THREAT else "find the strongest move"
        out.append(f"### {theme.capitalize()} ({len(g)}): {kind}\n")
        for _, r in g.iterrows():
            side = "White" if " w " in r["fen"] else "Black"
            out.append(
                f"- **{side} to move** ({r['tc']}, move {r['move_no']}, {r['phase']}, "
                f"{r['clock_frac']:.0%} of clock left). You were at {r['wp_before']:.0%} to win.  \n"
                f"  `{r['fen']}`  [board]({lichess_link(r['fen'])}) · [game]({r['url']})  \n"
                f"  <details><summary>answer</summary>You played <b>{r['played_san']}</b> "
                f"(win chance fell to {r['wp_after']:.0%}). Best was <b>{r['v_best_san']}</b>: "
                f"{r['v_line']}</details>\n")
    return "\n".join(out)


def main() -> None:
    cands = pd.read_csv(REPORTS_DIR / "phase3" / "instructive_candidates.csv")
    sel = select(verify(cands))
    sel.to_csv(REPORTS_DIR / "phase3" / "instructive_selected.csv", index=False)
    (REPORTS_DIR / "phase3" / "instructive.md").write_text(to_markdown(sel))
    print(sel[["theme", "tc", "move_no", "played_san", "v_best_san", "wp_loss", "v_gap"]].to_string())


if __name__ == "__main__":
    main()
