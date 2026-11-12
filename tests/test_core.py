"""Light tests for the non-obvious logic: material accounting along engine lines, hung-piece
detection, and reconstructing pre-game ratings."""
import chess
import pandas as pd

from chess_improvement.engine import hanging_capture
from chess_improvement.errors import line_net
from chess_improvement.parse import _pre_game_ratings


def test_line_net_even_trade_is_zero():
    # White Bb5 x Nc6, black recaptures dxc6: a fair trade.
    fen = "r1bqkbnr/ppp2ppp/2np4/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"
    assert line_net(fen, ["b5c6", "b7c6"], chess.WHITE) == 0


def test_line_net_truncated_mid_exchange_is_conservative():
    # Line stops right after White takes a knight, before the recapture. The min over the
    # last two plies keeps the pre-capture balance rather than claiming +3.
    fen = "r1bqkbnr/ppp2ppp/2np4/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"
    assert line_net(fen, ["e1g1", "a7a6", "b5c6"], chess.WHITE) == 0


def test_hanging_capture_detects_undefended_piece():
    # After White plays Nc3-d5?? the knight on d5 is undefended and Black's queen on d8 takes it.
    board = chess.Board("rnbqkb1r/pppp1ppp/8/3Np3/8/8/PPPPPPPP/R1BQKBNR b KQkq - 0 3")
    assert hanging_capture(board, chess.Move.from_uci("d8d5")) == 3


def test_hanging_capture_ignores_defended_equal_trade():
    # Knight on d5 defended by the e4 pawn, taken by a knight: an even trade, not a hung piece.
    board = chess.Board("r1bqkb1r/pppp1ppp/2n5/3Np3/4P3/8/PPPP1PPP/R1BQKBNR b KQkq - 0 4")
    board.set_piece_at(chess.F6, chess.Piece(chess.KNIGHT, chess.BLACK))
    assert hanging_capture(board, chess.Move.from_uci("f6d5")) == 0


def test_pre_game_ratings_undo_post_game_change():
    df = pd.DataFrame({
        "start_time": pd.to_datetime(["2026-01-01 10:00", "2026-01-01 10:10", "2026-01-01 10:20"], utc=True),
        "rated": [True, True, True], "time_class": ["blitz"] * 3, "score": [1.0, 0.0, 1.0],
        "my_rating_post": [1508, 1500, 1508], "opp_rating_post": [1492, 1510, 1490],
    })
    out = _pre_game_ratings(df)
    assert out["my_rating"].tolist() == [1500, 1508, 1500]
    assert out["opp_rating"].tolist() == [1500, 1502, 1498]
