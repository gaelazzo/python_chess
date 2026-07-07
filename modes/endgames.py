"""'Endgame Training' mode.

Selection: the user chooses a PGN file from the `endgames/` folder. The program
extracts a random game and uses its starting position (the FEN header, if
present) as the endgame to solve -- the PGN mainline is ignored; the judge is
the Syzygy tablebase (for positions with <=7 pieces) or Stockfish as a fallback.

Gameplay loop:
- the user plays the side to move in the starting position;
- after each move, WDL(before)/WDL(after) is compared using Syzygy:
  - unchanged (or improved) WDL -> OK, the opponent replies;
  - worsened WDL -> takeback, flashes "wrong move, try again";
- if the position is outside the tablebase range, Stockfish is used instead:
  compare the evaluation before/after the move; a drop > BLUNDER_CP is
  considered an error;
- the opponent chooses the tablebase-optimal move whenever possible,
  otherwise Stockfish.
"""
from __future__ import annotations

import os
import random
import sys
from typing import List, Optional

import chess
import chess.engine
import chess.pgn
import chess.polyglot
import pygame as p
import pygame_menu

from app_context import app
import game_loop_common as glc
from state import CIRCLE_COLOR
from GameState import Move, GameState
from modes.board_session import BoardSession, ModePolicy
import UCIEngines
import BoardScreen as BS
from toolbar import IconToolbar, ToolbarAction
import syzygy_helper as sh
from LearningBase import LearningBase, learningBases
from modes.common import show_message, setAlfa


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))


BASE_PATH = get_base_path()
ENDGAMES_FOLDER = os.path.join(BASE_PATH, "endgames")
if not os.path.exists(ENDGAMES_FOLDER):
    os.makedirs(ENDGAMES_FOLDER)


# Blunder threshold for engine-based evaluation (centipawns).
BLUNDER_CP = 100

# Pondering time for engine replies (seconds).
ENGINE_REPLY_TIME = 0.5

# Analysis time for engine-based evaluation (seconds).
ENGINE_JUDGE_TIME = 2

# Uniform severity for tablebase-based errors (engine-based errors use cp drop).
TB_ERROR_SEVERITY = 100


def _get_or_create_endgame_base(filename: str) -> Optional[LearningBase]:
    """
    Retrieve or create the learning base associated with the endgame PGN file.
    Naming convention: `endgames_<filename>`. This way the base appears in
    `Solve positions` like any other learning base, and the user can review
    mistakes from endgames using the same workflow as tactics/openings.
    """

    base_name = f"endgames_{filename}"
    if base_name in learningBases:
        return learningBases[base_name]
    try:
        lb = LearningBase(
            movesToAnalyze=20,
            blunderValue=100,
            ponderTime=0.5,
            useBook=False,
        )
        lb.setFileName(base_name)
        learningBases[base_name] = lb
        lb.save()
        return lb
    except Exception as e:
        print(f"endgames: could not create base '{base_name}': {e}")
        return None


def _best_move_for_position(board: chess.Board) -> Optional[chess.Move]:
    """Best move: TB-optimal if in range, otherwise Stockfish."""
    mv = sh.best_tb_move(board)
    if mv is not None:
        return mv
    return _engine_reply(board)


def _log_user_move_to_base(lb: Optional[LearningBase], game: chess.pgn.Game,
                           board: chess.Board, played_uci: str, ok: bool) -> None:
    """Update the endgame learning base.

    - Error: adds (or updates) the position with the correct move computed on
      the fly (tablebase-optimal or engine fallback), severity=TB_ERROR_SEVERITY.
    - Success on a previously tracked position: updates stats reusing
      `position.ok` already stored -- avoids an unnecessary TB/engine probe on
      the happy path.
    - Success on a previously unseen position: no-op (we avoid polluting the base).
    """

    if lb is None:
        return
    zobrist = chess.polyglot.zobrist_hash(board)
    if not ok:
        correct = _best_move_for_position(board)
        if correct is None:
            return
        try:
            lb.updatePosition(played_uci, correct.uci(), game, board,
                              severity=TB_ERROR_SEVERITY)
            lb.save()
        except Exception as e:
            print(f"endgames: error saving position: {e}")
    elif zobrist in lb.positions:
        stored_ok = lb.positions[zobrist].ok
        try:
            lb.updatePosition(played_uci, stored_ok, game, board)
            lb.save()
        except Exception as e:
            print(f"endgames: error updating stats: {e}")


def _load_games(pgn_path: str) -> List[chess.pgn.Game]:
    """Load all games from the PGN file."""
    games: List[chess.pgn.Game] = []
    if not os.path.exists(pgn_path):
        return games
    with open(pgn_path, encoding='utf-8', errors='replace') as f:
        while True:
            g = chess.pgn.read_game(f)
            if g is None:
                break
            games.append(g)
    return games


def _format_score_cp(score: chess.engine.PovScore, turn: chess.Color) -> Optional[int]:
    """Score in centipawns from `turn`'s point of view, mate-adjusted."""
    if score is None:
        return None
    pov = score.pov(turn)
    if pov.is_mate():
        # Mate for us: +30000; getting mated: -30000 (lower mate counter = more severe).
        m = pov.mate()
        if m is None:
            return None
        return 30000 - m if m > 0 else -30000 - m
    return pov.score(mate_score=30000)


def _engine_eval_cp(board: chess.Board, turn: chess.Color) -> Optional[int]:
    """Eval in cp of `board` from `turn`'s POV; None if engine fails or returns no score."""
    if UCIEngines.engine is None:
        return None
    try:
        info = UCIEngines.engine.analyse(
            board, chess.engine.Limit(time=ENGINE_JUDGE_TIME),
            info=chess.engine.INFO_SCORE,
        )
        return _format_score_cp(info.get("score"), turn)
    except Exception as e:
        print(f"endgames: engine analyse failed: {e}")
        return None


def _engine_reply(board: chess.Board) -> Optional[chess.Move]:
    """Response move from the engine; None if engine fails or returns no move."""
    if UCIEngines.engine is None:
        return None
    try:
        result = UCIEngines.engine.play(board, chess.engine.Limit(time=ENGINE_REPLY_TIME))
        return result.move
    except Exception as e:
        print(f"endgames: engine play failed: {e}")
        return None


def _effective_wdl(wdl: Optional[int], dtz: Optional[int], halfmove_clock: int) -> Optional[int]:
    """Effective WDL given the real 50-move rule clock.

        Syzygy probe_wdl assumes `halfmove_clock=0` (clean clock). To determine how
        convertible a win actually is, WDL+DTZ must be combined with the current
        clock: if there is not enough budget left to reach the next pawn move or
        capture (resetting the clock), the game is drawn by the 50-move rule and the
        "true" WDL becomes 0.

        Mapping:
        wdl == +2 and clock + |DTZ| <= 100 -> +2
        wdl == +2 and clock + |DTZ| >  100 ->  0  (forced draw by 50-move rule)
        wdl == +1 or -1 (cursed/blessed)   ->  0  (already effectively unreachable)
        wdl == -2 and clock + |DTZ| <= 100 -> -2
        wdl == -2 and clock + |DTZ| >  100 ->  0  (saved by 50-move rule)
        wdl ==  0                          ->  0
    """

    if wdl is None:
        return None
    if wdl == 0 or wdl == 1 or wdl == -1:
        return 0
    if dtz is None:
        return wdl
    if halfmove_clock + abs(dtz) <= 100:
        return wdl
    return 0


def _best_child_dtz_among(board: chess.Board, min_our_wdl: int) -> Optional[int]:
    """Minimum DTZ (from our POV) achievable among legal moves that preserve a
    WDL >= `min_our_wdl`. None if no qualifying move exists or if the tablebase
    is unavailable.

    Used to determine whether the user's move is "as good as the best possible"
    in terms of DTZ: dtz_a == best -> OK; dtz_a > best -> suboptimal.
    In near-zeroing endgames (e.g. KQ vs KP, forced mate via promotion), the
    child DTZ may equal the parent DTZ for optimal play; comparing against `best`
    avoids false negatives from the naive rule `dtz_a < dtz_b`.
    """
    tb = sh.open_tablebase()
    if tb is None or not sh.is_in_tb_range(board):
        return None
    best = None
    for mv in board.legal_moves:
        nb = board.copy(stack=False)
        nb.push(mv)
        if not sh.is_in_tb_range(nb):
            continue
        try:
            cw = tb.probe_wdl(nb)
            cd = tb.probe_dtz(nb)
        except (chess.syzygy.MissingTableError, KeyError, IndexError):
            continue
        our_wdl = -cw
        if our_wdl >= min_our_wdl:
            our_dtz = -cd
            if best is None or our_dtz < best:
                best = our_dtz
    return best


def _judge_user_move(board_before: chess.Board, move: chess.Move) -> tuple[bool, str]:
    """Judge the user's move. Returns (is_ok, debug_info).

    Rules (in order):
    1. **Forced draw** (stalemate / insufficient material) caused by the user:
    if the position was WDL > 0, this is an error.
    2. **Checkmate delivered by the user**: always OK.
    3. **Clean WDL deterioration**: flagged as error.
    4. **DTZ optimality** (only with clean WDL=+2): if the move is not a
    zeroing move, the post-move DTZ (from our POV) must be equal to the
    **minimum achievable DTZ** among all legal +2-preserving moves. This way,
    a move with `dtz_a == dtz_b` is accepted if it is truly TB-optimal (e.g.
    KQ vs KP in the last ply before forced promotion), while a "slow" move
    that leads to a higher DTZ than the best available is flagged.
    5. Outside TB: Stockfish fallback, evaluation comparison with BLUNDER_CP threshold.
    """
    turn = board_before.turn
    # --- TB ---
    wdl_b = sh.probe_wdl(board_before)
    if wdl_b is not None:
        dtz_b = sh.probe_dtz(board_before)

        nb = board_before.copy(stack=False)
        nb.push(move)

        # Case 1+2: terminal child position.
        if nb.is_checkmate():
            return True, f"checkmate (WDL pre {wdl_b:+d}, DTZ pre {dtz_b})"
        if nb.is_stalemate() or nb.is_insufficient_material():
            ok = wdl_b <= 0
            kind = "stalemate" if nb.is_stalemate() else "insufficient material"
            return ok, f"{kind} forced (WDL pre {wdl_b:+d}) -- {'draw acceptable' if ok else 'ERROR: you were winning'}"

        if not sh.is_in_tb_range(nb):
            return True, f"TB child out of range (WDL pre {wdl_b:+d})"
        try:
            cwdl = sh.open_tablebase().probe_wdl(nb)
            cdtz = sh.open_tablebase().probe_dtz(nb)
        except (chess.syzygy.MissingTableError, KeyError, IndexError):
            return True, f"TB child probe failed (WDL pre {wdl_b:+d})"
        wdl_a = -cwdl
        dtz_a = -cdtz

        # Case 3: clean WDL worsened.
        if wdl_a < wdl_b:
            return False, f"WDL drop {wdl_b:+d}->{wdl_a:+d} (DTZ {dtz_b}->{dtz_a})"

        # Case 4: with clean WDL=+2, the move must be DTZ-optimal among the
        # +2-preserving moves (it is not enough that DTZ does not increase,
        # nor that it strictly decreases: in near-zeroing positions the
        # optimal line may have dtz_a == dtz_b).
        if wdl_b == 2:
            is_zeroing = nb.halfmove_clock == 0
            if not is_zeroing:
                best = _best_child_dtz_among(board_before, min_our_wdl=2)
                if best is not None and dtz_a > best:
                    return False, (f"not optimal: DTZ {dtz_b}->{dtz_a} "
                                   f"(optimal reachable = {best})")

        return True, f"WDL {wdl_b:+d}->{wdl_a:+d}, DTZ {dtz_b}->{dtz_a}, clock {board_before.halfmove_clock}->{nb.halfmove_clock}"

    # --- Fallback Stockfish ---
    eval_before = _engine_eval_cp(board_before, turn)
    nb = board_before.copy(stack=False)
    nb.push(move)
    eval_after_opp = _engine_eval_cp(nb, not turn)
    if eval_before is None or eval_after_opp is None:
        return True, "Engine unavailable -- unjudged"
    eval_after = -eval_after_opp
    drop = eval_before - eval_after
    return drop <= BLUNDER_CP, f"Eng {eval_before}cp -> {eval_after}cp (drop {drop})"


def _opponent_move(board: chess.Board) -> Optional[chess.Move]:
    """Opponent's move: TB-optimal if possible, otherwise Stockfish."""
    mv = sh.best_tb_move(board)
    if mv is not None:
        return mv
    return _engine_reply(board)


def playEndgames() -> None:
    """Entry-point from the menu: load the games and loop until the user exits."""
    from state import positionParameters
    filename = positionParameters.get("endgames_filename")
    if not filename:
        return
    pgn_path = os.path.join(ENDGAMES_FOLDER, filename + ".pgn")
    games = _load_games(pgn_path)

    # Clean starting state for the E toggle: if a previous mode had left
    # analysis active, the first E here would land in the "stop" branch
    # (showing 'engine stopped') instead of starting analysis.
    UCIEngines.stop_analysis()

    app.main_menu.disable()
    app.main_menu.full_reset()

    # Endgame training needs an engine (opponent replies / judging): stop here with
    # a readable message instead of flashing "TB+engine failed" inside the loop.
    if not UCIEngines.is_engine_ready():
        app.main_background()
        BS.drawEndGameText(app.screen, None,
                           "Configure an engine first: Tools > Setup > Choose engine",
                           size=20)
        BS.update()
        app.delay(3)
        app.main_menu.enable()
        return

    if not games:
        app.main_background()
        BS.drawEndGameText(app.screen, None,
                           f"No games in {filename}.pgn (endgames/ folder)")
        BS.update()
        app.delay(2)
        app.main_menu.enable()
        return

    # Session: draw without replacement; when it runs out, start over.
    pool: List[chess.pgn.Game] = list(games)
    random.shuffle(pool)

    running = True
    while running:
        if not pool:
            pool = list(games)
            random.shuffle(pool)
        game = pool.pop()
        action = _playOneEndgame(game, filename, len(games) - len(pool), len(games))
        if action == "quit":
            running = False

    BS.set_context_label(None)
    p.event.clear()
    UCIEngines.stop_analysis()
    app.main_menu.enable()


def _playOneEndgame(game: chess.pgn.Game, filename: str, idx: int, total: int) -> str:
    """Practice a single position. Returns 'next' or 'quit'."""
    # Game state: initial position = PGN root (FEN header if present).
    gs = GameState()
    gs.setPgn(game)
    start_board = gs.node.board()

    # Selection core: pick() builds the candidate move WITHOUT applying it, so this
    # mode can validate (Syzygy/engine) before deciding to play it. ModePolicy is
    # inert (pick() touches no policy hook); the session SHARES this gs.
    session = BoardSession(ModePolicy(), gs=gs)

    if start_board.is_game_over():
        # Position already terminal: skip.
        return "next"

    # Learning base for errors in this file: created/opened on first entry.
    lb = _get_or_create_endgame_base(filename)

    human_color_chess = start_board.turn  # bool True=White
    human_color = "w" if human_color_chess else "b"
    color_label = "White" if human_color_chess else "Black"

    title = game.headers.get("White", "") + " - " + game.headers.get("Black", "")
    site = game.headers.get("Site", "")
    if not title.strip("- "):
        title = site or f"#{idx}"
    BS.set_context_label(f"Endgame: {filename} -- {title} ({idx}/{total}, playing {color_label})")

    BS.show_pgn = False
    BS.show_book = False
    # Follow the E toggle across positions: the panel is visible iff analysis
    # is actually running, and a running analysis is re-attached to the new
    # endgame (no-op if off) instead of being left on the previous position.
    BS.show_cpu = UCIEngines.is_analysing()
    BS.engine.clear(app.screen)
    UCIEngines.update_board(gs.board(), glc.engine_callback)
    BS.setWhiteUp(app.screen, not human_color_chess)
    BS.drawGameState(app.screen, gs, [], [], ())
    BS.update()

    # Initial info: pieces and WDL.
    n_pieces = sh.count_pieces(start_board)
    wdl0 = sh.probe_wdl(start_board)
    wdl_txt = f"WDL={wdl0:+d}" if wdl0 is not None else "outside TB"
    print(f"[endgames] {title}: {n_pieces} pieces, {wdl_txt}")

    # Toolbar.
    def _post_key(key, mod=0):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key, mod=mod))
    # Icon toolbar: only the buttons that apply to this mode (Copy FEN stays on
    # the keyboard, C). Each button posts its keyboard shortcut, as before.
    toolbar = IconToolbar([
        ToolbarAction("Hint",  "Show correct move (H)",        _post_key(p.K_h), icon="hint"),
        ToolbarAction("Next",  "Next endgame (N)",             _post_key(p.K_n), icon="nextitem"),
        ToolbarAction("CopyFEN", "Copy FEN (Shift+F)",         _post_key(p.K_f, p.KMOD_SHIFT), icon="copyfen"),
        ToolbarAction("PGN",   "Toggle move list (M)",         _post_key(p.K_m), icon="pgn"),
        ToolbarAction("Engine", "Engine on/off (E)",           _post_key(p.K_e), icon="engine"),
        ToolbarAction("Flip",  "Flip board (F)",               _post_key(p.K_f), icon="flip"),
        ToolbarAction("Menu",  "Back to menu (Q)",             _post_key(p.K_q), icon="home"),
    ], y=0, height=BS.TOOLBAR_HEIGHT)

    sqSelected: tuple = ()
    playerClicks: list = []
    validMoves = gs.stdValidMoves()
    moveMade = False
    animate = False
    gameOver = False
    show_help_panel = False
    must_skip = False
    quit_flag = False

    help_text = [
        "Instructions:",
        "- click to move",
        "- H correct move (hint)",
        "- N next endgame",
        "- Q back to menu",
        "- F flip board",
        "- M toggle move list",
        "- E engine on/off",
    ]

    while not must_skip and not quit_flag:
        time_delta = app.clock.tick(60) / 1000.0
        UCIEngines.poll()  # drain engine info (no-op if analysis off)
        humanCanPlay = gs.colorToMove() == human_color and not gameOver
        update = False

        # --- Game over check ---
        board = gs.node.board()
        if board.is_game_over(claim_draw=True):
            res = board.result(claim_draw=True)
            text = _result_message(res, human_color_chess)
            app.main_background()
            BS.drawEndGameText(app.screen, gs, text)
            BS.update()
            app.delay(2)
            # Auto-advance to the next endgame (like Study openings). Q during the delay
            # interrupts; the next iteration of the outer while loop selects another game.            
            break

        # --- Opponent move ---
        if not gameOver and not humanCanPlay and not moveMade:
            mv = _opponent_move(board)
            if mv is None:
                # Forced draw or error: show a message and end.
                show_message(gs, "No opponent move (TB+engine failed)")
                app.delay(1)
                break
            gs.makeMove(Move.fromChessMove(mv, gs))
            moveMade = True
            animate = True
            validMoves = gs.stdValidMoves()
            update = True

        # --- Events ---
        for e in p.event.get():
            app.manager.process_events(e)
            glc.stop_speech_on_input(e)
            if toolbar.process_event(e):
                update = True
                continue
            update = True
            if e.type == p.QUIT:
                quit_flag = True
            elif e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                show_help_panel = True
            elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                show_help_panel = False
            elif (e.type == p.MOUSEBUTTONDOWN and humanCanPlay
                  and not toolbar.pointer_in_toolbar(e.pos)):
                row, col = BS.getRowColFromLocation(p.mouse.get_pos())
                # Selection + promotion via the BoardSession: pick() builds the
                # candidate move WITHOUT applying it (validate-before-play). The
                # selection is mirrored back for the renderer; a wrong move, judged
                # below, is never pushed.
                validMove = session.pick(row, col,
                                         ask_promotion=lambda c: BS.choosePromotion(app.screen, c))
                sqSelected = session.selected if session.selected is not None else ()
                playerClicks = [session.selected] if session.selected is not None else []
                validMoves = session.validMoves
                if validMove is not None:
                    # --- Judgment ---
                    ok, why = _judge_user_move(board, validMove.move)
                    print(f"[endgames] move {validMove.move.uci()}: {'OK' if ok else 'ERR'} | {why}")
                    # Logging in learning base: error -> add/update;
                    # success -> update stats only if already tracked.
                    _log_user_move_to_base(lb, game, board, validMove.move.uci(), ok)
                    if ok:
                        gs.makeMove(validMove)
                        moveMade = True
                        animate = True
                        validMoves = gs.stdValidMoves()
                    else:
                        # Implicit take-back: we do NOT push the move, the user can retry.
                        short = why.split(' (')[0] if why else "error"
                        # show_message default = font 32: too large for messages >20 chars.
                        # We use drawEndGameText with a smaller size and a longer delay.
                        BS.drawEndGameText(app.screen, gs, f"Wrong move: {short}", size=20)
                        app.delay(2.5)
                        update = True

            elif e.type == p.KEYDOWN:
                if e.key == p.K_q:
                    quit_flag = True
                elif e.key == p.K_n:
                    must_skip = True
                elif e.key == p.K_h:
                    # Hint: show the TB-optimal move (or engine if outside TB).
                    suggestion = sh.best_tb_move(board) or _engine_reply(board)
                    if suggestion is not None:
                        show_message(gs, f"Hint: {board.san(suggestion)}")
                    else:
                        show_message(gs, "No hint available")
                    app.delay(1)
                elif e.key == p.K_f and not (e.mod & p.KMOD_SHIFT):
                    BS.flipBoard(app.screen)
                    animate = False
                elif e.key == p.K_f and (e.mod & p.KMOD_SHIFT):  # Shift+F: copy FEN
                    glc.copy_to_clipboard(board.fen(), "FEN copied", gs)
                elif e.key == p.K_m:
                    glc.toggle_pgn(gs)
                elif e.key == p.K_e:
                    glc.toggle_engine(gs)

        toolbar.update(time_delta)

        if not update:
            toolbar.draw(app.screen)
            p.display.update()
            continue

        if show_help_panel:
            glc.draw_help_overlay(help_text, height=300)
            continue

        if moveMade:
            moveMade = False
            # If analysis is active, attach the new position (no-op if disabled).
            UCIEngines.update_board(gs.board(), glc.engine_callback)
            lastMove = gs.moveLog[-1] if gs.moveLog else None
            if animate and lastMove:
                BS.animateMove(lastMove, app.screen, gs)
                app.delay(0.1)
                animate = False

        if humanCanPlay:
            toHighlightSquares = []
            toHighlightCircle = []
            if len(playerClicks) == 1:
                mm = [m for m in validMoves
                      if m.startRow == sqSelected[0] and m.startCol == sqSelected[1]]
                toHighlightCircle = [(m.stopRow, m.stopCol, CIRCLE_COLOR) for m in mm]
            if len(playerClicks) == 0 and gs.moveLog:
                lm = gs.moveLog[-1]
                toHighlightSquares = [
                    (lm.stopRow, lm.stopCol, setAlfa(p.Color("yellow"), 150)),
                    (lm.startRow, lm.startCol, setAlfa(p.Color("yellow"), 150)),
                ]
            BS.drawGameState(app.screen, gs,
                             toHighlightCirclesColor=toHighlightCircle,
                             toHighlightSquareColor=toHighlightSquares,
                             sqSelected=sqSelected)

        toolbar.draw(app.screen)
        BS.update()

    toolbar.kill()
    return "quit" if quit_flag else "next"


def _result_message(result: str, human_is_white: bool) -> str:
    """Final message based on the PGN result and the human side."""
    if result == "1/2-1/2":
        return "Draw"
    if result == "1-0":
        return "Win" if human_is_white else "Defeat"
    if result == "0-1":
        return "Win" if not human_is_white else "Defeat"
    return "end"
