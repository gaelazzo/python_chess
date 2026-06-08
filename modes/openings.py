import os
import re
import sys
import random
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List, Dict


def _get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))


# Dedicated folder for opening repertoire PGNs. Mirrors `endgames/`:
# keep here only the model lines you want to use in Study Openings, without
# mixing them with the PGNs of your games stored in `pgn/`. Created
# automatically on first import if it does not already exist.
BASE_PATH = _get_base_path()
OPENINGS_FOLDER = os.path.join(BASE_PATH, "openings")
if not os.path.exists(OPENINGS_FOLDER):
    os.makedirs(OPENINGS_FOLDER)

import chess
import chess.pgn
import chess.polyglot
import pygame as p
import pygame_menu

from app_context import app
import game_loop_common as glc
import state
from state import playParameters, positionParameters, CIRCLE_COLOR
from GameState import Move, GameState
from modes.board_session import BoardSession, ModePolicy
import UCIEngines
import BoardScreen as BS
from toolbar import Toolbar, ToolbarAction
import analyzer
import BrainMaster
from BrainMaster import AnswerData, QuestionData, give_answers, ask_for_quiz, unlock_new_lesson
import Quiz
import pgngamelist
from LearningBase import LearningBase, LearnPosition, learningBases
from save_load import save_menu, load_menu
from modes.common import show_message, setAlfa


# Heuristic: in opening repertoire PGNs, the side being trained follows
# fixed mainline moves while the opponent has alternative variations.
#   (N... move -> BLACK variation (user plays White)
#   (N.  move  -> WHITE variation (user plays Black)
# We decide by majority across all variations in the file: a single
# "anomalous" variation (e.g. an exploratory branch for the other side)
# does not override the decision as the old first-match approach did.
_VARIATION_RE = re.compile(r'\(\s*(\d+)\s*(\.\.\.|\.)\s*[A-Za-z]')


def detect_user_color_from_pgn(pgn_path: str) -> Optional[str]:
    """Detect the user's color by counting variations per side in the PGN
    and taking the majority.

    Returns 'w' / 'b' / None (no variation found or exact tie).
    """
    try:
        with open(pgn_path, encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError:
        return None
    matches = _VARIATION_RE.findall(text)
    if not matches:
        return None
    black_variations = sum(1 for _num, sep in matches if sep == '...')
    white_variations = len(matches) - black_variations
    if black_variations == white_variations:
        return None  # tie: ambiguous, let the caller decide the fallback
    # more Black variations -> opponent is Black -> user plays White
    return 'w' if black_variations > white_variations else 'b'


# Uniform severity for opening errors (equivalent centipawn drop);
# used for practice prioritization in Solve Positions
# (see analyzer.getPositions).
OPENING_ERROR_SEVERITY = 100


def _get_or_create_opening_base(filename: str) -> Optional[LearningBase]:
    """Retrieve or create the learning base associated with the repertoire PGN file.

    Naming convention: `openings_<filename>` (mirror of `endgames_<filename>`).
    This way, the base appears in `Solve positions` like any other training base,
    and the user can review mistakes from the repertoire using the same workflow
    as tactics/endgame training.
    """
    base_name = f"openings_{filename}"
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
        print(f"openings: could not create base '{base_name}': {e}")
        return None


def _log_user_move_to_base(lb: Optional[LearningBase], game: chess.pgn.Game,
                           board: chess.Board, played_uci: str,
                           correct_uci: Optional[str], ok: bool) -> None:
    """Update the opening error learning base.

    - Error: adds (or updates) the position with the correct move
    (PGN mainline), severity=OPENING_ERROR_SEVERITY.
    - Success on a previously tracked position: updates stats reusing
    `position.ok` -- avoids recomputing the correct move on the happy path.
    - Success on a previously unseen position: no-op (we avoid polluting the base).
    """
    if lb is None:
        return
    zobrist = chess.polyglot.zobrist_hash(board)
    if not ok:
        if correct_uci is None:
            return
        try:
            lb.updatePosition(played_uci, correct_uci, game, board,
                              severity=OPENING_ERROR_SEVERITY)
            lb.save()
        except Exception as e:
            print(f"openings: failed to save mistake: {e}")
    elif zobrist in lb.positions:
        try:
            stored_ok = lb.positions[zobrist].ok
            lb.updatePosition(played_uci, stored_ok, game, board)
            lb.save()
        except Exception as e:
            print(f"openings: update stats failed: {e}")


# "Study openings": you must always play the best move while the computer replies
# with one of the lines stored in the PGN (typically an opening repertoire).
def playOpening():
    filename = positionParameters.get("filename")
    if filename is None:
        return
    # Automatically detects the user's color from the PGN content. Defaults to White
    # if the file does not contain variations (e.g. a single line, nothing to infer).
    pgn_path = os.path.join(OPENINGS_FOLDER, filename + ".pgn")
    detected = detect_user_color_from_pgn(pgn_path)
    human_color = detected or "w"

    app.main_menu.disable()
    app.main_menu.full_reset()
    if detected is None:
        # informational: no variation found, default to White
        app.main_background()
        BS.drawEndGameText(app.screen, None,
                           f"Color not detectable from PGN -- defaulting to White", size=18)
        BS.update()
        app.delay(2)
    playOpeningLine(filename, human_color)
    return

def playOpeningLine(filename, humanColor):
    '''
        Play one line from the PGN: the trainee must always play the best move,
        while the computer answers with one of the lines stored in the game
        (typically an opening repertoire).
    '''
    # Clean state for the E toggle: if a previous mode left analysis running,
    # the first E here would incorrectly trigger the "stop" branch instead of
    # starting it.
    UCIEngines.stop_analysis()

    gamelist = pgngamelist.PgnGameList(filename, folder=OPENINGS_FOLDER)

    # Learning base for errors in this repertoire file (mirror of the
    # pattern used in `Endgame Training`). Created/opened only once for
    # the entire study openings session.
    lb = _get_or_create_opening_base(filename)

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False
    BS.show_pgn = False
    BS.show_book=False
    # show_cpu must follow the actual engine state; otherwise, if analysis
    # was left running from the previous position, the CPU panel stays empty
    # while the engine is still running in the background.
    BS.show_cpu = UCIEngines.is_analysing()
    BS.clearCPU(app.screen)
    
    help_text = [
            "Instructions:",
            "- left to take back a move",
            "- right to play next move",
            "- Q to quit",
            "- H Hint (show the correct move)",
            "- C Copy FEN to clipboard",
            "- G Copy PGN to clipboard ",
            "- E Engine ON/OFF",
            "- B show/hide book",
            "- D show/hide moves"
        ]
    show_help = False
    def do_show_help():
        glc.draw_help_overlay(help_text, height=400)

    if gamelist.isEmpty():
        text = "No positions found"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        app.main_menu.enable()
        return

    color_label = {"w": "White", "b": "Black"}.get(humanColor, "?")
    BS.set_context_label(f"Opening: {filename} ({color_label})")

    # Toolbar (phase 2): same pattern as the other modes.
    def _post_key(key, mod=0):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key, mod=mod))
    # NB: Undo is NOT exposed as a button in Study Openings: the mode is a
    # "find the correct move" exercise, not free play, and gs.undoMove()
    # interacts in a non-intuitive way with the sequence (stopCondition /
    # opponent auto-moves), causing solution steps to be skipped. The
    # keyboard shortcut Z/Left remains available for manual use.
    toolbar = Toolbar([
        ToolbarAction("Flip",  "Flip board (F)",                          _post_key(p.K_f)),
        ToolbarAction("Eval",  "Evaluate position (S)",                   _post_key(p.K_s)),
        ToolbarAction("Eng",   "Engine on/off (E)",                       _post_key(p.K_e)),
        ToolbarAction("Book",  "Toggle opening book (B)",                 _post_key(p.K_b)),
        ToolbarAction("Moves", "Toggle PGN move list (D)",                _post_key(p.K_d)),
        ToolbarAction("C-FEN", "Copy FEN to clipboard (C)",               _post_key(p.K_c)),
        ToolbarAction("C-PGN", "Copy PGN to clipboard (G)",               _post_key(p.K_g)),
        ToolbarAction("Hint",  "Show next correct move (H)",              _post_key(p.K_h),
                      enabled=lambda: humanCanPlay),
        ToolbarAction("Next",  "Next game (N) -- after a correct line",   _post_key(p.K_n),
                      enabled=lambda: not humanCanPlay),
        ToolbarAction("Quit",  "Quit to menu (Q)",                        _post_key(p.K_q)),
    ])

    while running:
        gs = GameState()
        game = gamelist.chooseRandomGame()
        gs.setPgn(game)

        # Selection core: pick() builds the candidate move WITHOUT applying it, so
        # this "guess the move" mode judges it (checkNextMove) and only ever plays
        # the stored canonical move. ModePolicy is inert; the session SHARES this gs.
        session = BoardSession(ModePolicy(), gs=gs)

        if state.play_position:
            # Lead-in Skip: choose uniformly the starting depth among
            # all user turns in the line. Pre-scan the mainline starting
            # from gs.node to count N user turns, then target = randint(1, N).
            # Walk the line (user mainline, random opponent variation) and stop
            # at the target-th user move. The old version (1/3 break probability
            # at each user turn) produced a geometric distribution that heavily
            # biased early repertoire moves.
            cur_turn_is_white = gs.node.board().turn
            n_player_turns = 0
            node = gs.node
            while True:
                nxt = node.next()
                if nxt is None:
                    break
                turn_color = 'w' if cur_turn_is_white else 'b'
                if turn_color == humanColor:
                    n_player_turns += 1
                cur_turn_is_white = not cur_turn_is_white
                node = nxt
            target_idx = random.randint(1, n_player_turns) if n_player_turns > 0 else 0

            seen = 0
            moreMoves = True
            while moreMoves:
                playerTurn = gs.colorToMove() == humanColor
                if playerTurn:
                    advanced = gs.doNextMainMove()
                    if advanced:
                        seen += 1
                        if seen >= target_idx:
                            break
                    moreMoves = advanced
                else:
                    move = gs.makeNextMove()
                    moreMoves = move is not None
            # undo the last move: the user comes in and must replay it
            gs.undoMove()
        

        BS.setWhiteUp(app.screen, humanColor == "b")
        BS.drawGameState(app.screen, gs, [], [], ())
        BS.update()

        currentMove = 0
        validMoves = gs.stdValidMoves()
        engineMove = 0
        mustSkip = False
        terminated = False
        gameOver = False
        errors = 0
        stopCondition = False
        while running and not mustSkip:
            time_delta = app.clock.tick(60) / 1000.0   # pace + dt for the toolbar
            UCIEngines.poll()  # drain engine info (no-op if analysis is off)
            humanCanPlay = gs.colorToMove() == humanColor
            checkMove = False
            nextMove = gs.getNextMainMove()
            update= False
            if nextMove is None or stopCondition:  # game is over anyway
                text = "Ok"
                app.main_background()
                BS.drawEndGameText(app.screen, gs, text)
                BS.update()
                app.delay(2 )
                gameOver = True
                break

            if nextMove is not None and not humanCanPlay:
                    move = gs.makeNextMove()
                    moveMade = True
                    animate = True
                    validMoves = gs.stdValidMoves()
                    update = True


            for e in p.event.get():
                app.manager.process_events(e)
                glc.stop_speech_on_input(e)
                if toolbar.process_event(e):
                    update = True
                    continue
                update = True
                if e.type == p.QUIT:
                    running = False
                elif e.type == p.MOUSEBUTTONDOWN and e.button == 1 and gameOver and not toolbar.pointer_in_toolbar(e.pos):
                    # Only the left click skips: the scroll wheel (button 4/5) does NOT.
                    mustSkip = True
                    break
                elif  e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Show help when the right button is pressed
                        show_help = True
                        # play_position = 1
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Hide help when the right button is released
                        show_help = False
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay and not toolbar.pointer_in_toolbar(e.pos):

                    row, col = BS.getRowColFromLocation(p.mouse.get_pos())
                    # Selection + promotion via the BoardSession: pick() builds the
                    # candidate move WITHOUT applying it. This is a "guess" mode --
                    # the move is judged below and only the stored canonical move is
                    # ever played -- so the candidate must not be pushed.
                    validMove = session.pick(row, col,
                                             ask_promotion=lambda c: BS.choosePromotion(app.screen, c))
                    sqSelected = session.selected if session.selected is not None else ()
                    playerClicks = [session.selected] if session.selected is not None else []
                    validMoves = session.validMoves
                    if validMove is not None:
                        # Board state BEFORE the move: used for
                        # learning-base logging (key = Zobrist hash of
                        # the position where the user made the move).
                        _board_pre = gs.node.board()
                        _next_main = gs.getNextMainMove()
                        _correct_uci = _next_main.uci() if _next_main else None
                        if gs.checkNextMove(validMove.move):
                            # Correct move: update stats if the position
                            # is already in the base (no-op if not tracked).
                            _log_user_move_to_base(lb, game, _board_pre,
                                                   validMove.move.uci(),
                                                   _correct_uci, ok=True)
                            errors = 0
                            gs.doNextMainMove()
                            moveMade = True
                            animate = True
                            validMoves = gs.stdValidMoves()
                            if state.play_position:
                                stopCondition=True
                        else:
                            # Wrong move: added or updated in the base.
                            _log_user_move_to_base(lb, game, _board_pre,
                                                   validMove.move.uci(),
                                                   _correct_uci, ok=False)
                            errors += 1
                            msg = "Not the right move"
                            if errors >= 3:
                                rightMove = Move.fromChessMove(_next_main, gs)
                                msg = f"hint:{rightMove.uci[:2]}"
                            show_message(gs,msg)
                            app.delay(1)

                elif e.type == p.KEYDOWN:
                    if e.key == p.K_z or e.key == p.K_LEFT:
                        gs.undoMove()
                        validMoves = gs.stdValidMoves()
                        moveMade = True
                        animate = False
                        gameOver = False

                    if e.key == p.K_LESS and (e.mod & p.KMOD_SHIFT):
                        BS.setFactor( BS.getFactor()*1.2)

                    if e.key == p.K_LESS and ((e.mod & p.KMOD_SHIFT) == 0):
                        BS.setFactor( BS.getFactor() / 1.2)

                    if e.key == p.K_c:
                        # copy position to clibboard
                        glc.copy_to_clipboard(gs.node.board().fen(), "Position copied to clipboard", gs)
                    
                    if e.key == p.K_g:
                        # copy position to clibboard
                        glc.copy_to_clipboard(gs.to_PgnString(), "Game copied to clipboard", gs)

                    if e.key == p.K_s:  # evaluate score
                        gs.setEvaluation(analyzer.evaluatePosition(gs.node.board(), 5))

                    if e.key == p.K_q:
                        running = False

                    if e.key == p.K_n and not humanCanPlay:
                        mustSkip = True
                        break
                    if e.key == p.K_b:
                        glc.toggle_book(gs)

                    if e.key == p.K_d:
                        glc.toggle_pgn(gs)

                    if e.key == p.K_e:  # Engine on /off
                        glc.toggle_engine(gs)

                    if e.key == p.K_f:
                        # Bugfix: previously this branch used "whiteUp = not whiteUp"
                        # but whiteUp was not a local variable -> UnboundLocalError at runtime.
                        # Now it uses BS.flipBoard like the other modes.
                        BS.flipBoard(app.screen)
                        animate = False

                    if e.key == p.K_h and humanCanPlay:
                        # Hint: show in SAN the move expected from the mainline.
                        next_main = gs.getNextMainMove()
                        if next_main is not None:
                            try:
                                san = gs.node.board().san(next_main)
                            except Exception:
                                san = next_main.uci()
                            show_message(gs, f"Hint: {san}")
                            app.delay(2)
               
            toolbar.update(time_delta)

            if not update:
                # Idle frame: redraw the toolbar (for the tooltips) and flip.
                toolbar.draw(app.screen)
                p.display.update()
                continue

            if show_help:
                do_show_help()
                continue

            if moveMade and not mustSkip:
                moveMade = False
                # If analysis is active, attach the new position (no-op if off).
                UCIEngines.update_board(gs.board(), glc.engine_callback)
                lastMove = gs.moveLog[-1] if len(gs.moveLog) > 0 else None
                if animate and lastMove:
                    BS.animateMove(lastMove, app.screen, gs)
                    app.delay(0.1)
                    animate = False

            if humanCanPlay and not moveMade:
                toHighlightSquares = []
                toHighlightCircle = []
                if len(playerClicks) == 1:
                    mm = [m for m in validMoves if m.startRow == sqSelected[0] and m.startCol == sqSelected[1]]
                    toHighlightCircle = [(m.stopRow, m.stopCol, CIRCLE_COLOR) for m in mm]

                if len(playerClicks) == 0 and len(gs.moveLog) > 0:
                    lastMove = gs.moveLog[-1]
                    toHighlightSquares = [(lastMove.stopRow, lastMove.stopCol, setAlfa(p.Color("yellow"), 150)),
                                          (lastMove.startRow, lastMove.startCol, setAlfa(p.Color("yellow"), 150))]

                BS.drawGameState(app.screen, gs, toHighlightCirclesColor=toHighlightCircle,
                                 toHighlightSquareColor=toHighlightSquares,
                                 sqSelected=sqSelected)

            toolbar.draw(app.screen)
            BS.update()

    toolbar.kill()
    BS.set_context_label(None)
    p.event.clear()
    UCIEngines.stop_analysis()
    app.main_menu.enable()
