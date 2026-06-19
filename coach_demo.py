"""Quick way to SEE the move coach from the terminal (no GUI wiring yet).

Usage:
    python coach_demo.py                  # runs a built-in example game
    python coach_demo.py e4 e5 Bc4 Nc6 Qh5 Nf6     # your own moves (SAN or UCI)

For each move it prints the deterministic coach comment (engine-grounded, no AI).
Requires an engine configured in config.json (the same one the app uses).
"""
import sys

import chess

import UCIEngines
import move_review as mr

# A short illustrative game: the scholar's-mate trap ends in a blunder.
DEFAULT_MOVES = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6"]


def _parse(board: chess.Board, token: str) -> chess.Move:
    """Accept either SAN ('Nf6') or UCI ('g8f6')."""
    try:
        return board.parse_san(token)
    except ValueError:
        return chess.Move.from_uci(token)


def main(tokens):
    if not UCIEngines.is_engine_ready():
        UCIEngines.engine_open()
    if not UCIEngines.is_engine_ready():
        print("No engine available. Configure one in config.json (Tools > Setup).")
        return

    board = chess.Board()
    for token in tokens:
        move = _parse(board, token)
        side = "White" if board.turn == chess.WHITE else "Black"
        san = board.san(move)
        comment = mr.review_move(board, move, time=0.5)   # template path (LLM off by default)
        num = board.fullmove_number
        prefix = f"{num}.{'' if board.turn == chess.WHITE else '..'}{san} ({side})"
        print(f"{prefix:<22} {comment}")
        board.push(move)

    UCIEngines.engine_close()


if __name__ == "__main__":
    main(sys.argv[1:] or DEFAULT_MOVES)
