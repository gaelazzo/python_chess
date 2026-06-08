"""Headless mode controller -- proof of concept (core + per-mode policy).

`BoardSession` is the shared board interaction + presentation state used by every
mode; the mode-specific rules (judging a move, the opponent's reply, hints, extra
commands, extra view fields, orientation) live in a small `ModePolicy`. It's
composition, so there is ONE core and a thin policy per mode -- not a whole
Session class per mode.

Nothing here imports pygame or draws: it is fully driven/queried by tests or a
CLI. The real game loop would only do:

    for ev in pygame.event.get():
        if ev.type == KEYDOWN:   session.do(KEYMAP.get(ev.key))
        elif click:              session.click(*BoardScreen.getRowColFromLocation(ev.pos))
    render(session.view_model())

Only that final `render` stays outside the tested surface. It depends solely on
GameState (logic) -- no class outside modes/ is modified.
"""
from dataclasses import dataclass
from typing import Optional, List, Tuple

import chess

from GameState import GameState, Move


@dataclass
class ViewModel:
    white_up: bool                       # orientation (False = White at the bottom)
    turn: str                            # 'w' / 'b'
    selected: Optional[Tuple[int, int]]  # highlighted square (row, col) or None
    move_targets: List[Tuple[int, int]]  # legal destinations of the selected piece
    book: List[str]                      # book moves (SAN) when the book panel is on
    notation: str                        # PGN text (whole game + variations)
    panels: dict                         # {'book':bool, 'pgn':bool, 'cpu':bool}
    message: Optional[str]
    is_end: bool
    game_over: bool
    extra: dict                          # mode-specific fields (from the policy)


# --------------------------------------------------------------------------- #
# Mode policies: the only thing that changes between modes.
# --------------------------------------------------------------------------- #
class ModePolicy:
    """Hooks a mode can override. Base = inert (the core does everything)."""
    name = "base"

    def on_start(self, s): ...                     # set up the initial position
    def reorient(self, s): ...                     # decide orientation after a move
    def after_user_move(self, s): ...              # judge / log the move just played
    def opponent_reply(self, s): return None       # chess.Move for the opponent, or None
    def handle_command(self, s, cmd): return False  # mode-specific cmd; True if handled
    def extra_view(self, s): return {}


class AnalysisPolicy(ModePolicy):
    """Free analysis / human play: no judging, optional side-to-move flipping."""
    name = "analysis"

    def __init__(self):
        self.locked = True            # board orientation locked by default

    def reorient(self, s):
        # Auto-flip to the side to move only in free human play: locked analysis
        # and games against a CPU keep the board fixed.
        if not self.locked and not s.white_cpu and not s.black_cpu:
            s.white_up = (s.gs.board().turn == chess.BLACK)

    def handle_command(self, s, cmd):
        if cmd == "analyze":
            self.locked = not self.locked
            self.reorient(s)
        elif cmd == "flip":
            s.white_up = not s.white_up
        elif cmd == "truncate":
            if not s.gs.truncateAfterCurrent():
                s.message = "Nothing to truncate"
        elif cmd == "delete":
            if s.gs.deleteCurrentVariation():
                s.refresh()
            else:
                s.message = "No move to delete"
        elif cmd == "delete_line":
            if s.gs.deleteCurrentVariationLine():
                s.refresh()
            else:
                s.message = "Not in a variation"
        else:
            return False
        return True

    def extra_view(self, s):
        return {"mode": self.name, "locked": self.locked}


class SolvePolicy(ModePolicy):
    """Find-the-right-move drill over [{'setup': [uci...], 'correct': uci}, ...].

    A wrong move is removed and retried; a correct one advances to the next
    problem. The board is fixed to the user's side (no flipping).
    """
    name = "solve"

    def __init__(self, problems, user_white=True):
        self.problems = list(problems)
        self.idx = 0
        self.attempts = 0
        self.solved = 0
        self.done = False
        self.user_white = user_white

    def _load(self, s):
        s.gs = GameState()
        for u in self.problems[self.idx]["setup"]:
            s.gs.makeChessMove(chess.Move.from_uci(u))
        s.refresh()
        s.white_up = not self.user_white

    def on_start(self, s):
        if self.problems:
            self._load(s)

    def reorient(self, s):
        s.white_up = not self.user_white            # fixed to the user's side

    def after_user_move(self, s):
        if not s.gs.moveLog:
            return
        played = s.gs.moveLog[-1].uci
        if played == self.problems[self.idx]["correct"]:
            self.solved += 1
            if self.idx + 1 < len(self.problems):
                self.idx += 1
                self._load(s)
                s.message = "Correct!"
            else:
                self.done = True
                s.message = "Done!"
        else:
            self.attempts += 1
            s.gs.deleteCurrentVariation()           # remove the wrong move, retry
            s.refresh()
            s.message = "Wrong move, try again"

    def handle_command(self, s, cmd):
        if cmd == "hint":
            board = s.gs.board()
            uci = self.problems[self.idx]["correct"]
            try:
                s.message = "Hint: " + board.san(chess.Move.from_uci(uci))
            except Exception:
                s.message = "Hint: " + uci
            return True
        return False

    def extra_view(self, s):
        return {"mode": self.name, "label": "Solve positions",
                "attempts": self.attempts, "solved": self.solved, "done": self.done}


# --------------------------------------------------------------------------- #
# The shared core.
# --------------------------------------------------------------------------- #
class BoardSession:
    def __init__(self, policy: Optional[ModePolicy] = None,
                 gs: Optional[GameState] = None,
                 white_cpu: bool = False, black_cpu: bool = False):
        self.policy = policy or AnalysisPolicy()
        self.gs = gs or GameState()
        self.white_cpu = white_cpu
        self.black_cpu = black_cpu
        self.show_book = False
        self.show_pgn = False
        self.show_cpu = False
        self.white_up = False
        self.selected: Optional[Tuple[int, int]] = None
        self._clicks: List[Tuple[int, int]] = []
        self.validMoves = self.gs.stdValidMoves()
        self.message: Optional[str] = None
        self.running = True
        self.policy.on_start(self)

    def refresh(self):
        self.validMoves = self.gs.stdValidMoves()

    def reorient(self):
        """Re-apply the policy's orientation rule (a no-op when the policy keeps
        the board fixed). The renderer reads `white_up` from the session."""
        self.policy.reorient(self)

    def new_game(self) -> GameState:
        """Reset to a fresh game from the initial position, keeping the same
        policy and orientation. Returns the new GameState so a caller that shares
        `gs` can rebind its own reference."""
        self.gs = GameState()
        self.refresh()
        self.reset_selection()
        return self.gs

    def reset_selection(self):
        self.selected = None
        self._clicks = []

    # ---- commands ----
    def click(self, row: int, col: int, ask_promotion=None):
        """Board click: select a piece, complete a move, or deselect.

        Returns the Move that was just made, or None. `ask_promotion(color)` is
        called when a pawn reaches the last rank and must return the promotion
        piece; it defaults to auto-queen so the controller works headless.
        """
        self.message = None
        self.validMoves = self.gs.stdValidMoves()      # validate against the live position
        # same square, or a click outside the board (move-log panel) -> deselect
        if self.selected == (row, col) or col >= 8 or row >= 8:
            self.reset_selection()
            return None
        self.selected = (row, col)
        self._clicks.append((row, col))
        moved = None
        if len(self._clicks) == 2:
            move = Move(self._clicks[0], self._clicks[1], self.gs)
            if move.pieceMoved[1] == "P" and (row == 0 or row == 7):
                promotions = [m for m in self.validMoves
                              if m.startRow == self._clicks[0][0] and m.startCol == self._clicks[0][1]
                              and m.stopRow == self._clicks[1][0] and m.stopCol == self._clicks[1][1]]
                if promotions:
                    piece = ask_promotion(move.pieceMoved[0]) if ask_promotion else chess.QUEEN
                    move = move.promoteToPiece(piece)
            if move in self.validMoves:
                self.gs.makeMove(move)
                self.refresh()
                self.policy.after_user_move(self)
                self.policy.reorient(self)
                reply = self.policy.opponent_reply(self)
                if reply is not None:
                    self.gs.makeChessMove(reply)
                    self.refresh()
                    self.policy.reorient(self)
                moved = move
                self.reset_selection()
            else:
                self.selected = (row, col)             # invalid move: keep the last square selected
                self._clicks = [(row, col)]
        if len(self._clicks) == 1 and self.gs.colorAt(row, col) != self.gs.colorToMove():
            self.reset_selection()                     # empty/opponent square -> reject selection
        return moved

    def do(self, cmd: Optional[str]):
        if cmd == "undo":
            self.gs.undoMove(); self.refresh(); self.policy.reorient(self)
        elif cmd == "next":
            self.next_move()                     # main line (no picker)
        elif cmd == "book":
            self.show_book = not self.show_book
        elif cmd == "pgn":
            self.show_pgn = not self.show_pgn
        else:
            self.policy.handle_command(self, cmd)

    def next_move(self, pick_variation=None):
        """Advance to the next move. With several continuations,
        `pick_variation(moves, board) -> chosen move | None` is called to choose
        (defaults to the main line). Returns the move played, or None.
        """
        moves = self.gs.getNextMoves()
        if not moves:
            return None
        if len(moves) == 1:
            move = moves[0]
        elif pick_variation is None:
            move = moves[0]                      # headless default: main line
        else:
            move = pick_variation(moves, self.gs.node.board())
            if move is None:
                return None                      # cancelled
        self.gs.makeChessMove(move)
        self.refresh()
        self.policy.reorient(self)
        return move

    # ---- queries ----
    def book_view(self) -> List[str]:
        board = self.gs.board()
        try:
            entries = self.gs.getMovesFromBook()
        except Exception:
            return []
        out = []
        for e in entries:
            try:
                out.append(board.san(e.move))
            except Exception:
                out.append(e.move.uci())
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
            message=self.message,
            is_end=self.gs.is_end(),
            game_over=self.gs.checkMate() or self.gs.staleMate(),
            extra=self.policy.extra_view(self),
        )
