"""Tests for the watch loop -- turning a stream of board images into moves.

No real screen: capture is injected. Frames are rendered by the same synthetic
renderer used for the recognition tests.
"""
import chess
import pytest

import board_vision as bv
import board_watch as bw
from test_board_vision import _render


# --- match_move: the legal-move matcher, incl. the tricky special moves ---------

def test_match_move_plain_and_castling():
    board = chess.Board()
    for uci in ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "e1g1"]:
        move = chess.Move.from_uci(uci)
        after = board.copy()
        after.push(move)
        assert bw.match_move(board, after.board_fen()) == move
        board.push(move)


def test_match_move_en_passant():
    board = chess.Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
    after = board.copy()
    after.push(chess.Move.from_uci("e5f6"))   # en passant
    assert bw.match_move(board, after.board_fen()) == chess.Move.from_uci("e5f6")


def test_match_move_promotion_picks_the_right_piece():
    board = chess.Board("8/4P3/8/8/8/8/8/k6K w - - 0 1")
    after = board.copy()
    after.push(chess.Move.from_uci("e7e8q"))
    assert bw.match_move(board, after.board_fen()) == chess.Move.from_uci("e7e8q")


def test_match_move_returns_none_for_unreachable():
    board = chess.Board()
    # a layout that no single legal move can produce (two pawns vanished)
    bogus = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/8/RNBQKBNR").board_fen()
    assert bw.match_move(board, bogus) is None


# --- WatchSession: following a game frame by frame ------------------------------

class _Feeder:
    """A grab() stand-in that returns scripted frames, then repeats the last."""
    def __init__(self, frames):
        self.frames, self.i = frames, 0

    def __call__(self):
        frame = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return frame


@pytest.fixture(scope="module")
def profile():
    return bv.calibrate_profile(_render(chess.Board()))


def _play(ucis):
    board = chess.Board()
    positions = [board.copy()]
    for uci in ucis:
        board.push(chess.Move.from_uci(uci))
        positions.append(board.copy())
    return positions


def test_watch_follows_a_game(profile):
    game = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "e1g1", "g8f6"]
    positions = _play(game)
    # each position must persist stable_frames times to commit
    frames = [_render(p) for p in positions for _ in range(2)]
    watch = bw.WatchSession(profile, grab=_Feeder(frames), stable_frames=2)

    emitted = []
    for _ in range(len(frames)):
        emitted += [m.uci() for m in watch.poll()]
    assert emitted == game
    assert watch.board.board_fen() == positions[-1].board_fen()


def test_watch_skips_a_transient_frame(profile):
    """A single mid-animation frame (a piece momentarily gone) must not fire."""
    seed = chess.Board()
    seed.push(chess.Move.from_uci("e2e4"))          # start tracking here
    after = seed.copy()
    after.push(chess.Move.from_uci("e7e5"))         # the move that will happen

    transit = seed.copy()
    transit.remove_piece_at(chess.E7)               # black e-pawn "in flight"

    frames = [_render(seed), _render(transit),
              _render(after), _render(after)]        # transit appears only once
    watch = bw.WatchSession(profile, board=seed, grab=_Feeder(frames),
                            stable_frames=2)

    emitted = []
    for _ in range(len(frames)):
        emitted += [m.uci() for m in watch.poll()]
    assert emitted == ["e7e5"]


def test_advance_to_catches_up_missed_move():
    """A clean frame that is two plies ahead (one move was missed mid-animation)
    is recovered as the two-move sequence."""
    board = chess.Board()
    board.push_san("e4")
    target = board.copy()
    target.push_san("e5")
    target.push_san("Nf3")            # two plies ahead of `board`
    seq = bw.advance_to(board, target.board_fen(), max_depth=2)
    assert seq is not None and [m.uci() for m in seq] == ["e7e5", "g1f3"]
    # unreachable within the depth -> None
    assert bw.advance_to(chess.Board(), target.board_fen(), max_depth=1) is None


def test_watch_recovers_after_skipping_a_move(profile):
    """If a whole move's frames are missed, the next stable position (two plies
    on) is caught up, emitting both moves."""
    game = ["e2e4", "e7e5", "g1f3", "b8c6"]
    positions = _play(game)
    # feed start(x2), pos1(x2), [skip pos2 entirely], pos3(x2), pos4(x2)
    frames = (
        [_render(positions[0])] * 2
        + [_render(positions[1])] * 2
        + [_render(positions[3])] * 2      # jumped past positions[2]
        + [_render(positions[4])] * 2
    )
    watch = bw.WatchSession(profile, grab=_Feeder(frames), stable_frames=2)
    emitted = []
    for _ in range(len(frames)):
        emitted += [m.uci() for m in watch.poll()]
    assert emitted == game
    assert watch.board.board_fen() == positions[4].board_fen()


def test_watch_tolerates_small_noise(profile):
    """A read a couple of squares off from the played move still matches (the move
    stays the closest), while the same noise sitting on the current position does
    NOT trigger a phantom move."""
    seed = chess.Board()
    seed.push_san("e4")                         # tracking here, black to move
    played = seed.copy()
    played.push_san("c5")
    noisy = played.copy()                        # played position + 2 misread squares
    noisy.remove_piece_at(chess.A7)
    noisy.set_piece_at(chess.H6, chess.Piece.from_symbol("p"))
    # noisy frame repeats: first commits c5, later repeats must NOT add a move
    watch = bw.WatchSession(profile, board=seed, grab=_Feeder([_render(noisy)] * 5),
                            stable_frames=2, tol=5)
    emitted = []
    for _ in range(5):
        emitted += [m.uci() for m in watch.poll()]
    assert emitted == ["c7c5"]


def test_watch_no_phantom_move_on_static_noise(profile):
    """Persistent recognition noise on a static position must never invent a move."""
    board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQ - 0 5")
    noisy = board.copy()
    noisy.remove_piece_at(chess.A2)              # one persistently misread square
    watch = bw.WatchSession(profile, board=board, grab=_Feeder([_render(noisy)] * 6),
                            stable_frames=2, tol=5)
    emitted = []
    for _ in range(6):
        emitted += [m.uci() for m in watch.poll()]
    assert emitted == []
    assert watch.board.board_fen() == board.board_fen()


def test_watch_recovers_from_drag_artifact(profile):
    """A piece dragged THROUGH an intermediate square (briefly looking like a
    move there) must be corrected once it lands on its real destination."""
    seed = chess.Board("6k1/6b1/7B/8/3P4/8/8/6K1 b - - 0 1")
    artifact = seed.copy()
    artifact.push_san("Bxh6")        # bishop paused on h6 mid-drag (a fake move)
    real = seed.copy()
    real.push_san("Bxd4")            # where it was actually dropped
    frames = [_render(artifact)] * 2 + [_render(real)] * 2
    watch = bw.WatchSession(profile, board=seed, grab=_Feeder(frames),
                            stable_frames=2, white_bottom=True)
    resynced = False
    for _ in range(len(frames)):
        watch.poll()
        resynced = watch.take_resync() or resynced
    assert resynced
    assert watch.board.board_fen() == real.board_fen()


def test_learn_highlight_reads_highlighted_square():
    """After a move, the watch learns the last-move-highlight look and reads a
    piece on a highlighted square correctly."""
    prof = bv.calibrate_profile(_render(chess.Board()))   # own profile: we mutate its highlights
    board = chess.Board()
    board.push_san("e4")                              # e2->e4, both light squares
    img = _render(board, highlight=[chess.E2, chess.E4])
    watch = bw.WatchSession(prof, board=board, grab=_Feeder([img]))
    watch.last_frame = img
    watch._learn_highlight(chess.Move.from_uci("e2e4"))
    assert (".", "l") in watch.hl_templates           # highlighted-empty learned
    assert ("P", "l") in watch.hl_templates           # highlighted pawn captured
    got = bv.recognize_board(img, prof, extra=watch.hl_templates)
    assert got.board_fen() == board.board_fen()


def test_learned_highlights_live_in_the_profile_and_persist(tmp_path):
    """What the watch learns about the highlight look accrues INTO the profile and
    survives a save/load round-trip -- so the next reuse starts already knowing it."""
    prof = bv.calibrate_profile(_render(chess.Board()))
    assert prof.hl_templates == {}                    # nothing at calibration time
    board = chess.Board(); board.push_san("e4")
    watch = bw.WatchSession(prof, board=board)
    watch.last_frame = _render(board, highlight=[chess.E2, chess.E4])
    watch._learn_highlight(chess.Move.from_uci("e2e4"))
    assert (".", "l") in prof.hl_templates            # learned straight into the profile
    path = str(tmp_path / "theme.pkl")
    bv.save_profile(prof, path)
    reloaded = bv.load_profile(path)
    assert (".", "l") in reloaded.hl_templates        # ... and it persists


def test_highlighted_squares_learned_flags_the_move_squares():
    """Once the highlight look is learned, the last move's from/to squares are
    detected -- and a plain, un-highlighted frame flags nothing."""
    prof = bv.calibrate_profile(_render(chess.Board()))
    board = chess.Board(); board.push_san("e4")
    frame = _render(board, highlight=[chess.E2, chess.E4])
    watch = bw.WatchSession(prof, board=board); watch.last_frame = frame
    watch._learn_highlight(chess.Move.from_uci("e2e4"))
    hl = bv.highlighted_squares_learned(frame, prof, white_bottom=True, trim=False)
    assert chess.E2 in hl and chess.E4 in hl
    assert bv.highlighted_squares_learned(_render(chess.Board()), prof,
                                          white_bottom=True, trim=False) == set()


def test_watch_matches_move_by_highlight_when_destination_unreadable():
    """The exact stall we are fixing: a piece lands on a highlighted square that
    the reader can't see (reads empty), so no layout matches -- but the move is
    still followed because its highlighted from/to squares pin it. Reproduces the
    real Kg6-h7 endgame case."""
    prof = bv.calibrate_profile(_render(chess.Board()))
    # teach the light-square highlight look from a prior real move (e2-e4)
    teach = chess.Board(); teach.push_san("e4")
    tw = bw.WatchSession(prof, board=teach)
    tw.last_frame = _render(teach, highlight=[chess.E2, chess.E4])
    tw._learn_highlight(chess.Move.from_uci("e2e4"))
    # Kg6-h7, but h7 renders WITHOUT the king (unreadable); both squares highlighted
    seed = chess.Board("4k3/8/p1p3K1/6P1/5p1p/1P5P/P4P2/8 w - - 0 43")
    after = seed.copy(); after.push_san("Kh7")
    blind = after.copy(); blind.remove_piece_at(chess.H7)      # destination "invisible"
    frame = _render(blind, highlight=[chess.G6, chess.H7])
    watch = bw.WatchSession(prof, board=seed, grab=_Feeder([frame] * 3),
                            stable_frames=2)
    emitted = []
    for _ in range(3):
        emitted += [m.uci() for m in watch.poll()]
    assert emitted == ["g6h7"]
    assert watch.board.board_fen() == after.board_fen()


def test_watch_jumps_when_it_falls_behind(profile):
    """Missing more moves than the catch-up depth (fast play) must NOT freeze: the
    watch jumps to the live position and signals a resync so the caller re-mirrors."""
    game = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6"]
    positions = _play(game)
    seed, far = positions[0], positions[8]          # 8 plies apart (>> max_depth=3)
    watch = bw.WatchSession(profile, board=seed, grab=_Feeder([_render(far)] * 3),
                            stable_frames=2, max_depth=3)
    resynced = False
    for _ in range(3):
        watch.poll()
        resynced = watch.take_resync() or resynced
    assert resynced
    assert watch.board.board_fen() == far.board_fen()


def test_resync_reconstructs_from_root_after_a_jump(profile):
    """After a fell-behind JUMP the watch board's ROOT is the jumped (mid-game)
    position, and root + move_stack still reconstruct the live board with only LEGAL
    moves. The app's resync replays from that root; replaying the post-jump moves on
    the standard start instead would be illegal and corrupt the PGN tree."""
    game = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6"]
    positions = _play(game)
    seed, far = positions[0], positions[8]
    followup = far.copy(); followup.push_san("O-O")          # a legal move from `far`
    frames = [_render(far)] * 2 + [_render(followup)] * 2
    watch = bw.WatchSession(profile, board=seed, grab=_Feeder(frames),
                            stable_frames=2, max_depth=3)
    for _ in range(len(frames)):
        watch.poll()
    assert watch.board.board_fen() == followup.board_fen()   # jumped + followed
    rebuilt = watch.board.root()                             # == far, not the start
    assert rebuilt.board_fen() == far.board_fen()
    for mv in watch.board.move_stack:
        assert rebuilt.is_legal(mv)                          # never corrupts the tree
        rebuilt.push(mv)
    assert rebuilt.board_fen() == watch.board.board_fen()


def test_watch_does_not_jump_on_small_noise(profile):
    """A couple of misread squares on the current position must not be mistaken for
    falling behind (no phantom jump)."""
    board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQ - 0 5")
    noisy = board.copy()
    noisy.remove_piece_at(chess.A2)                 # one persistently misread square
    watch = bw.WatchSession(profile, board=board, grab=_Feeder([_render(noisy)] * 6),
                            stable_frames=2)
    for _ in range(6):
        watch.poll()
        assert not watch.take_resync()
    assert watch.board.board_fen() == board.board_fen()


def test_reseed(profile):
    watch = bw.WatchSession(profile, grab=_Feeder([_render(chess.Board())]))
    endgame = chess.Board("8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
    watch.reseed(endgame)
    assert watch.board.board_fen() == endgame.board_fen()
