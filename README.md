# chess-improvement

Analysis of my chess.com blitz history (3+0 and 5+0), producing an evidence-based training plan.
The write-up is in [`reports/report.md`](reports/report.md).

## Pipeline

| step | module | output | cached? |
|---|---|---|---|
| 1. download monthly archives | `download.py` | `data/raw/YYYY-MM.json` | yes (current month refreshes) |
| 2. build games table | `parse.py` | `data/processed/games.parquet` | rebuilt from raw (seconds) |
| 3. descriptive stats | `descriptive.py` | `reports/phase2/` | n/a |
| 4. Stockfish per-ply evals | `engine.py` | `data/engine/d16/<game>.parquet` | yes, per game |
| 5. classify moves | `errors.py` | `data/processed/plies_d16.parquet` | n/a |
| 6. engine breakdowns | `engine_analysis.py` | `reports/phase3/` | n/a |
| 7. verify study positions | `instructive.py` | `reports/phase3/instructive.md` | yes (depth-20 cache) |
| progress check | `progress.py --since YYYY-MM-DD` | printed table | uses the caches above |

```bash
uv sync
brew install stockfish
for m in download parse descriptive; do uv run python -m chess_improvement.$m; done
uv run python -m chess_improvement.engine --per-control 300   # ~25 min, depth 16
for m in errors engine_analysis instructive; do uv run python -m chess_improvement.$m; done
uv run pytest
```

## Definitions worth knowing
- **Ratings** in chess.com archives are *post-game*; pre-game ratings are reconstructed (`parse._pre_game_ratings`).
- **Residual** = score minus Elo-expected score; 0.01 points per game ≈ 7 Elo.
- **Error severity** = drop in win probability (lichess curve): inaccuracy ≥ 10, mistake ≥ 20, blunder ≥ 30 points.
- **Phases**: endgame when combined non-pawn material ≤ 26; opening = moves 1-10 otherwise; else middlegame.
- **Themes**: see the `errors.py` docstring.
