"""Headless session controller -- proof of concept.

Decouples the game *logic/state* from the pygame UI. A `Session` holds the model
(`GameState`) plus presentation flags, is mutated by small command methods
(`click`, `do`), and exposes `view_model()` -- the exact data the screen would
show, fully queryable by tests or a CLI. Nothing here imports pygame or draws.

How the real game loop would wire in (sketch, not used here yet):

    KEYMAP = {K_LEFT:"undo", K_RIGHT:"next", K_DELETE:"truncate",
              K_BACKSPACE:"delete", K_a:"analyze", K_b:"book",
              K_d:"pgn", K_f:"flip"}
    for ev in pygame.event.get():
        if ev.type == KEYDOWN:
            session.do(KEYMAP.get(ev.key))
        elif ev.type == MOUSEBUTTONDOWN and ev.button == 1:
            session.click(*BoardScreen.getRowColFromLocation(ev.pos))
    render(session.view_model())     # BoardScreen draws the view-model

Tests/CLI drive the same methods directly; only the final pixel rendering of the
view-model stays outside the tested surface.
"""
from dataclasses import dataclass
from typing import Optional, List, Tuple

import chess

from GameState import GameState, Move


# Keyboard-style commands accepted by Session.do().
KEY_COMMANDS = {"undo", "next", "truncate", "delete", "analyze", "book", "pgn", "flip"}


@dataclass
class ViewModel:
    white_up: bool                       # board orientation (False = White at bottom)
    turn: str                            # 'w' / 'b'
    selected: Optional[Tuple[int, int]]  # highlighted square (row, col) or None
    move_targets: List[Tuple[int, int]]  # legal destinations of the selected piece
    book: List[str]                      # book moves (SAN) when the book panel is on
    notation: str                        # PGN text (whole game + variations)
    panels: dict                         # {'book':bool, 'pgn':bool, 'cpu':bool}
    context_label: Optional[str]
    message: Optional[str]
    is_end: bool
    game_over: bool


class Session:
    def __init__(self, gs: Optional[GameState] = None,
                 white_cpu: bool = False, black_cpu: bool = False):
        self.gs = gs or GameState()
        self.white_cpu = white_cpu
        self.black_cpu = black_cpu
        self.analyze = True              # default: locked board (analysis)
        self.show_book = False
        self.show_pgn = False
        self.show_cpu = False
        self.white_up = False            # White at the bottom
        self.selected: Optional[Tuple[int, int]] = None
        self._clicks: List[Tuple[int, int]] = []
        self.validMoves = self.gs.stdValidMoves()
        self.message: Optional[str] = None
        self.context_label: Optional[str] = None
        self.running = True

    # ---- internal ----
    def _is_analysis(self) -> bool:
        return not self.white_cpu and not self.black_cpu

    def _reorient(self) -> None:
        # Outside analysis the board follows the side to move (like the real loop).
        if self._is_analysis() and not self.analyze:
            self.white_up = (self.gs.board().turn == chess.BLACK)

    def _refresh(self) -> None:
        self.validMoves = self.gs.stdValidMoves()
        self._reorient()

    # ---- commands (mutations) ----
    def click(self, row: int, col: int) -> None:
        """Board click: select a piece, or complete a move on the 2nd click."""
        self.message = None
        if self.selected == (row, col):
            self.selected = None
            self._clicks = []
            return
        self.selected = (row, col)
        self._clicks.append((row, col))
        if len(self._clicks) == 2:
            mv = Move(self._clicks[0], self._clicks[1], self.gs)
            if mv in self.validMoves:
                self.gs.makeMove(mv)
                self._refresh()
            self.selected = None
            self._clicks = []

    def do(self, cmd: Optional[str]) -> None:
        """Run a keyboard-style command (see KEY_COMMANDS)."""
        if cmd == "undo":
            self.gs.undoMove(); self._refresh()
        elif cmd == "next":
            mv = self.gs.getNextMainMove()
            if mv is not None:
                self.gs.makeChessMove(mv); self._refresh()
        elif cmd == "truncate":
            if not self.gs.truncateAfterCurrent():
                self.message = "Nothing to truncate"
        elif cmd == "delete":
            if self.gs.deleteCurrentVariation():
                self._refresh()
            else:
                self.message = "No move to delete"
        elif cmd == "analyze":
            self.analyze = not self.analyze; self._reorient()
        elif cmd == "book":
            self.show_book = not self.show_book
        elif cmd == "pgn":
            self.show_pgn = not self.show_pgn
        elif cmd == "flip":
            self.white_up = not self.white_up

    # ---- queries (the data the panels would show) ----
    def book_view(self) -> List[str]:
        board = self.gs.board()
        try:
            entries = self.gs.getMovesFromBook()
        except Exception:
            return []
        out = []
        for entry in entries:
            try:
                out.append(board.san(entry.move))
            except Exception:
                out.append(entry.move.uci())
        return out

    def view_model(self) -> ViewModel:
        board = self.gs.board()
        targets: List[Tuple[int, int]] = []
        if self.selected is not None:
            sr, sc = self.selected
            targets = [(m.stopRow, m.stopCol) for m in self.validMoves
                       if m.startRow == sr and m.startCol == sc]
        return ViewModel(
            white_up=self.white_up,
            turn=("w" if board.turn == chess.WHITE else "b"),
            selected=self.selected,
            move_targets=targets,
            book=self.book_view() if self.show_book else [],
            notation=self.gs.to_PgnString(),
            panels={"book": self.show_book, "pgn": self.show_pgn, "cpu": self.show_cpu},
            context_label=self.context_label,
            message=self.message,
            is_end=self.gs.is_end(),
            game_over=self.gs.checkMate() or self.gs.staleMate(),
        )
