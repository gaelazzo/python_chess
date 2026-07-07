"""board_watch.py -- follow a live game shown elsewhere on screen.

Phase 3 of the board-vision feature. A WatchSession captures a screen region
(the board of a stream / another app), recognizes it each frame, and turns the
stream of positions into a stream of MOVES by matching each change against the
legal moves of the position it is tracking.

Trusting legal moves -- not raw pixels -- is what makes this robust:
  * a frame caught mid-animation (or any misread) matches no legal move, so it
    is simply skipped;
  * the recognizer never has to be pixel-perfect, only good enough to pick which
    legal move happened;
  * castling, en passant and promotion need no special handling -- the one legal
    move that reproduces the new piece layout is the move that was played.

The capture is injectable (`grab`), so the whole thing is testable by feeding
rendered frames; the default grabs a screen region via PIL.ImageGrab.

Typical wiring (the game loop calls poll() once per frame):

    l, t, r, b = board_vision.find_board(screenshot)          # once, at setup
    profile = board_vision.calibrate_profile(first_frame_crop)
    watch = WatchSession(profile, region=(l, t, r, b))
    ...
    for move in watch.poll():        # each frame
        gs.makeMove(Move.fromChessMove(move, gs))            # analysis/book follow
"""
from __future__ import annotations

from typing import Callable, List, Optional

import chess

from board_vision import (Profile, recognize_board, tiles_by_square,
                          highlighted_squares_learned, _composite, _square_colour)


def _expand(board_fen: str) -> str:
    """A board_fen() ('rnbq.../...') expanded to 64 chars, '.' for empty."""
    out = []
    for row in board_fen.split("/"):
        for ch in row:
            out.append("." * int(ch) if ch.isdigit() else ch)
    return "".join(out)


def _placement_diff(a: str, b: str) -> int:
    """How many of the 64 squares differ between two board_fen layouts."""
    return sum(x != y for x, y in zip(_expand(a), _expand(b)))


def match_move(board: chess.Board, target_placement: str) -> Optional[chess.Move]:
    """Return the legal move from `board` reaching `target_placement`, else None.

    `target_placement` is a board_fen() (piece layout only -- an image can't give
    side to move or castling rights). We try each legal move and keep the one
    whose resulting layout matches, so castling (rook shifted), en passant (pawn
    captured off its square) and promotion (new piece) all resolve for free.
    """
    for move in board.legal_moves:
        board.push(move)
        hit = board.board_fen() == target_placement
        board.pop()
        if hit:
            return move
    return None


def advance_to(board: chess.Board, target_placement: str,
               max_depth: int = 2) -> Optional[list]:
    """Shortest legal move sequence from `board` reaching `target_placement`.

    Usually a single move. Searching a little deeper lets the watch CATCH UP when
    it missed a move -- e.g. a frame skipped during an animation leaves us a ply
    behind, so the next clean frame is two plies ahead and no single move matches.
    Returns [] if already there, None if unreachable within max_depth.
    """
    if board.board_fen() == target_placement:
        return []
    frontier = [(board, [])]
    for depth in range(max_depth):
        last = depth == max_depth - 1
        nxt = []
        for node, seq in frontier:
            for move in node.legal_moves:
                node.push(move)
                if node.board_fen() == target_placement:
                    node.pop()
                    return seq + [move]
                if not last:
                    nxt.append((node.copy(), seq + [move]))
                node.pop()
        frontier = nxt
    return None


class WatchSession:
    """Track a game shown on screen, emitting moves as they are played.

    Forward tracking (a game progressing move by move) is the rock-solid path.
    Jumps in the watched stream (the viewer scrubs a review, or you tune in mid
    game) are handled best-effort: after a stable position we cannot reach in one
    move, we re-seed onto it. The caller can also reseed() explicitly.
    """

    def __init__(self, profile: Profile, *, region=None,
                 grab: Callable[[], "object"] = None,
                 board: chess.Board = None, white_bottom: bool = None,
                 stable_frames: int = 2, reseed_after: int = 6, max_depth: int = 2,
                 tol: int = 5, jump_diff: int = 6, log: Callable[[str], None] = None,
                 frames_dir: str = None):
        self.profile = profile
        self.region = region
        self.board = board.copy() if board is not None else chess.Board()
        self.white_bottom = (profile.white_bottom if white_bottom is None
                             else white_bottom)
        self.stable_frames = stable_frames
        self.reseed_after = reseed_after
        self.max_depth = max_depth
        self.tol = tol                         # accept the closest move within this many squares
        self._jump_diff = jump_diff            # >= this many squares changed on an unmatchable
        #                                        stable read -> we fell behind; jump to it
        self.frames_dir = frames_dir           # if set, save one crop per move / per stall
        self._grab = grab or self._grab_screen
        self._log = log
        self._seq = 0
        self._resync = False                   # a rollback happened -> caller should re-mirror
        self.last_seen: Optional[str] = None   # most recent recognized layout
        self.last_frame = None                 # most recent grabbed crop (debug)
        self._last_logged: Optional[str] = None
        self._pending: Optional[str] = None
        self._pending_count = 0
        self._dead: Optional[str] = None       # a layout already found unmatchable
        # Highlighted-square templates live IN the profile, so what we learn while
        # watching accrues into it and is persisted -- next reuse starts richer.
        if getattr(profile, "hl_templates", None) is None:
            profile.hl_templates = {}
        self.hl_templates: dict = profile.hl_templates   # alias (same dict object)

    def _grab_screen(self):
        # Grab the whole virtual desktop and crop in IMAGE coordinates -- identical
        # to the setup crop by construction. (A bbox grab with virtual-screen
        # coordinates can be offset under multi-monitor/DPI, and PIL grabs the full
        # screen either way, so it wouldn't even be faster.)
        from PIL import ImageGrab
        shot = ImageGrab.grab(all_screens=True)
        return shot.crop(self.region) if self.region else shot

    def _recognize(self, frame) -> str:
        # trim=False: the board grid was fixed at setup (region already tight);
        # re-trimming each frame is content-dependent and would shift the grid.
        return recognize_board(frame, self.profile, white_bottom=self.white_bottom,
                               extra=self.hl_templates, trim=False).board_fen()

    def _learn_highlight(self, move: chess.Move) -> None:
        """Learn the highlighted-square look from a just-applied move: its from/to
        squares are highlighted on this frame, so future last-move squares read
        right. The from-square is now empty+highlighted (gives the highlight for
        that colour, from which every piece is synthesized); the to-square holds
        the moved piece on a highlighted square (captured exactly)."""
        if self.last_frame is None or self.profile.tile is None:
            return
        try:
            tiles = tiles_by_square(self.last_frame, self.profile, self.white_bottom,
                                    trim=False)
            frm, to = move.from_square, move.to_square
            fc = _square_colour(frm)
            if frm in tiles:                             # highlighted-empty -> synthesize all
                hl_empty = tiles[frm]
                self.hl_templates[(".", fc)] = hl_empty
                normal_empty = self.profile.templates.get((".", fc))
                if normal_empty is not None:
                    for (sym, colour), tmpl in self.profile.templates.items():
                        if colour == fc and sym != ".":
                            self.hl_templates[(sym, fc)] = _composite(tmpl, normal_empty, hl_empty)
            piece = self.board.piece_at(to)              # capture the moved piece exactly
            if piece is not None and to in tiles:
                self.hl_templates[(piece.symbol(), _square_colour(to))] = tiles[to]
        except Exception:
            pass

    def _snap(self, tag: str) -> None:
        """Save the current crop to frames_dir as NNN_<tag>.png (debug: one image
        per move / per stall, numbered so nothing is overwritten)."""
        if not self.frames_dir or self.last_frame is None:
            return
        try:
            import os
            os.makedirs(self.frames_dir, exist_ok=True)
            self.last_frame.save(os.path.join(self.frames_dir, f"{self._seq:03d}_{tag}.png"))
            self._seq += 1
        except Exception:
            pass

    def reseed(self, board: chess.Board) -> None:
        """Force the tracked position (e.g. the caller knows the stream jumped)."""
        self.board = board.copy()
        self._pending, self._pending_count = None, 0

    def _reseed_placement(self, placement: str) -> None:
        # A stable layout we can't reach in one move: the stream jumped. Keep the
        # side to move as our best guess (a wrong guess just makes the next real
        # move fail to match, and we re-seed again).
        board = chess.Board(placement + " w - - 0 1")
        board.turn = self.board.turn
        self.reseed(board)

    def poll(self) -> List[chess.Move]:
        """Grab one frame and return the move(s) newly detected (usually 0 or 1)."""
        self.last_frame = self._grab()          # kept for debugging (save to disk)
        placement = self._recognize(self.last_frame)
        self.last_seen = placement
        if self._log and placement != self._last_logged:   # log only on change
            self._last_logged = placement
            self._log(f"read {placement}")

        diff_stay = _placement_diff(placement, self.board.board_fen())
        if diff_stay == 0:                                # nothing changed
            self._pending, self._pending_count = None, 0
            self._dead = None
            return []

        # Cheap stall: a layout we already found unmatchable won't become matchable
        # until it changes, so skip the (expensive) searches while it persists. This
        # keeps the app responsive when stuck (e.g. a game-over overlay at mate).
        if placement == self._dead:
            return []

        # Debounce: a changed layout must persist for a couple of frames, so a
        # lone in-transit / misread frame can't trigger anything.
        if placement == self._pending:
            self._pending_count += 1
        else:
            self._pending, self._pending_count = placement, 1
        if self._pending_count < self.stable_frames:
            return []

        # First try an EXACT match (also recovers a move missed mid-animation:
        # the clean frame after is then two plies ahead -> advance_to catches up).
        # Guard: a K-move catch-up must be justified by the board change -- K real
        # moves alter at least K+1 squares. Without this, a persistent 1-square
        # misread (e.g. a piece on a highlighted square) makes advance_to invent an
        # absurd multi-move sequence to "explain" it, wrecking the game.
        moves = advance_to(self.board, placement, self.max_depth)
        if moves and diff_stay < len(moves) + 1:
            moves = None
        if moves:
            self._snap("_".join(m.uci() for m in moves))
            for move in moves:
                self.board.push(move)
            self._learn_highlight(moves[-1])       # this frame's last-move highlight
            if self._log:
                self._log(f"move {' '.join(m.uci() for m in moves)} -> {self.board.board_fen()}")
            self._pending, self._pending_count, self._dead = None, 0, None
            return moves

        # No exact match: accept the CLOSEST single legal move, but ONLY if the
        # read looks more like that move's result than like the current position
        # (diff < diff_stay) and is off by just a few squares (<= tol). This lets a
        # noisy frame (e.g. a highlight on the move squares) through, while noise
        # on the *current* position -- where no move fits better than staying --
        # never triggers a phantom move, and true garbage is far from every move.
        move, diff = self._closest_move(placement)
        if move is not None and diff <= self.tol and diff < diff_stay:
            self._snap(f"{move.uci()}_tol{diff}")
            self.board.push(move)
            self._learn_highlight(move)            # learn even from a noisy read
            if self._log:
                self._log(f"move {move.uci()} (tolerant, {diff} sq off) "
                          f"-> {self.board.board_fen()}")
            self._pending, self._pending_count, self._dead = None, 0, None
            return [move]

        # Highlight fallback: layout matching didn't pin a move, most often because
        # the piece that just LANDED reads as empty on its highlighted square (low
        # contrast). Identify the move by its highlighted from/to squares instead --
        # independent of what the destination reads as. This closes the whole class
        # of "piece on the arrival square misread" stalls (e.g. Kg6-h7, Nxe6).
        hlmove = self._match_by_highlight(placement)
        if hlmove is not None:
            self._snap(f"{hlmove.uci()}_hl")
            self.board.push(hlmove)
            self._learn_highlight(hlmove)
            if self._log:
                self._log(f"move {hlmove.uci()} (by highlight) -> {self.board.board_fen()}")
            self._pending, self._pending_count, self._dead = None, 0, None
            return [hlmove]

        # Recovery: the last committed move may have been a DRAG ARTIFACT -- a piece
        # dragged THROUGH / paused on an intermediate square, which briefly looked
        # like a move. Undo it and see if the read is reachable from before; if so
        # that move was wrong, so replace it with the real one. (A tell-tale sign is
        # that no forward move fits: the artifact would be a second move by the same
        # side, which is illegal.)
        if self._recover(placement):
            self._resync = True
            self._pending, self._pending_count, self._dead = None, 0, None
            if self._log:
                self._log(f"recovered (undid a drag artifact) -> {self.board.board_fen()}")
            return []

        # Fell behind (fast play): a stable, plausible full position we CANNOT reach
        # move-by-move (exact + catch-up + tolerant + recover all failed) means more
        # moves were missed than the catch-up depth. Rather than freeze, JUMP to it:
        # re-read the position WITH its side-to-move (from the last-move highlight)
        # and re-seed, so the board re-syncs to the live game. `diff_stay` large
        # tells a real jump apart from a 1-2 square misread sitting on the current
        # position (which must NOT reseed).
        if diff_stay >= self._jump_diff and self.last_frame is not None:
            from board_vision import recognize_position, _read_quality
            pos = recognize_position(self.last_frame, self.profile,
                                     white_bottom=self.white_bottom, trim=False)
            # Only jump to a LEGAL position: a misread (impossible material, a king
            # in an impossible check) must not seed the game -- an illegal seed lets
            # illegal moves into the PGN tree, which crashes on the next board replay.
            if (pos.board_fen() == placement and _read_quality(pos) > 0
                    and pos.is_valid()):
                self.reseed(pos)
                self._resync = True
                self._pending, self._pending_count, self._dead = None, 0, None
                if self._log:
                    self._log(f"fell behind ({diff_stay} sq changed) -> jumped to {pos.fen()}")
                return []

        # Stuck: remember this layout so we don't re-run the searches until it
        # changes (keeps the app responsive during a stall).
        self._dead = placement
        if self._pending_count == self.stable_frames:   # first stable stall: save it
            self._snap(f"STUCK_{diff}off_{diff_stay}stay")
        if self._log:
            self._log(f"stable but unmatched (x{self._pending_count}); read {diff} "
                      f"off closest move, {diff_stay} off current")
        return []

    def _closest_move(self, placement: str):
        """The legal move whose result differs least from `placement`, as
        (move, square_diff). (None, 99) if there are no legal moves."""
        best = (None, 99)
        for move in self.board.legal_moves:
            self.board.push(move)
            diff = _placement_diff(self.board.board_fen(), placement)
            self.board.pop()
            if diff < best[1]:
                best = (move, diff)
        return best

    def _match_by_highlight(self, placement: str) -> Optional[chess.Move]:
        """Identify the played move from the LAST-MOVE HIGHLIGHT: the legal move
        whose from AND to squares are both highlighted on this frame. Both squares
        are pinned by the tint regardless of what piece the read puts there, so a
        misread destination (the common failure) no longer hides the move. Only
        fires once the highlight look has been learned (fresh profile: no-op until
        the first move teaches it; a reused profile knows it from the start).
        Returns the move, or None if the highlight is absent/ambiguous."""
        if self.last_frame is None:
            return None
        hl = highlighted_squares_learned(self.last_frame, self.profile,
                                         self.white_bottom, trim=False)
        if len(hl) < 2:
            return None
        cands = [m for m in self.board.legal_moves
                 if m.from_square in hl and m.to_square in hl]
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        # Same from/to, several moves (promotion piece choice): let the read pick.
        best = None
        for move in cands:
            self.board.push(move)
            diff = _placement_diff(self.board.board_fen(), placement)
            self.board.pop()
            if best is None or diff < best[1]:
                best = (move, diff)
        return best[0]

    def _recover(self, placement: str) -> bool:
        """Undo the last committed move and try to reach `placement` from before it
        by an EXACT legal sequence. If found, the last move was a drag artifact and
        is replaced by the real move(s). Exact only -- NEVER a tolerant guess: a
        normal move merely read with noise must NOT cause the previous (correct)
        move to be rolled back and replaced with a wrong one. Returns True on fix."""
        if not self.board.move_stack:
            return False
        wrong = self.board.pop()
        seq = advance_to(self.board, placement, self.max_depth)   # exact match only
        if seq:
            for move in seq:
                self.board.push(move)
            return True
        self.board.push(wrong)                           # recovery failed: restore
        return False

    def take_resync(self) -> bool:
        """True (once) if the last poll rolled back a move; the caller should then
        re-mirror its own board from self.board (the move history changed)."""
        was, self._resync = self._resync, False
        return was
