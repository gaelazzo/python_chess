import os
import re
import sys
import random
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List, Dict

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


# Euristica: nelle PGN di repertorio d'apertura il lato che si esercita ha le
# proprie mosse fisse (mainline) mentre l'opponente ha varianti.
#   (N... mossa  -> variante del NERO (utente gioca Bianco)
#   (N.  mossa   -> variante del BIANCO (utente gioca Nero)
# Decidiamo per maggioranza su tutte le varianti del file: una singola
# variante "anomala" (es. ramo esplorativo nell'altro lato) non ribalta la
# scelta come faceva il vecchio first-match.
_VARIATION_RE = re.compile(r'\(\s*(\d+)\s*(\.\.\.|\.)\s*[A-Za-z]')


def detect_user_color_from_pgn(pgn_path: str) -> Optional[str]:
    """Rileva il colore dell'utente contando le varianti per lato nel PGN
    e prendendo la maggioranza.

    Ritorna 'w' / 'b' / None (nessuna variante trovata o pareggio esatto).
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
        return None  # pareggio: ambiguo, lascia al chiamante decidere il fallback
    # piu' varianti del Nero -> opponente e' Nero -> utente gioca Bianco
    return 'w' if black_variations > white_variations else 'b'


# Severity uniforme per errori di apertura (cp di calo "equivalente"); usata
# per la priorita' di pratica in Solve positions (vedi analyzer.getPositions).
OPENING_ERROR_SEVERITY = 100


def _get_or_create_opening_base(filename: str) -> Optional[LearningBase]:
    """Recupera o crea la learning base associata al file PGN del repertorio.

    Naming convention: `openings_<filename>` (mirror di `endgames_<filename>`).
    Cosi' la base appare in `Solve positions` come una qualsiasi altra base,
    e l'utente puo' ripassare gli errori commessi nel repertorio con lo stesso
    flusso della tattica/finali.
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
        print(f"openings: impossibile creare la base '{base_name}': {e}")
        return None


def _log_user_move_to_base(lb: Optional[LearningBase], game: chess.pgn.Game,
                           board: chess.Board, played_uci: str,
                           correct_uci: Optional[str], ok: bool) -> None:
    """Aggiorna la learning base degli errori per le aperture.

    - Errore: aggiunge (o aggiorna) la posizione con la mossa giusta
      (mainline del PGN), severity=OPENING_ERROR_SEVERITY.
    - Successo su posizione gia' tracciata: aggiorna stats riusando
      `position.ok` -- evita di ricalcolare la mossa giusta sulla via felice.
    - Successo su posizione mai vista: no-op (non spammiamo la base).
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
            print(f"openings: salvataggio errore fallito: {e}")
    elif zobrist in lb.positions:
        try:
            stored_ok = lb.positions[zobrist].ok
            lb.updatePosition(played_uci, stored_ok, game, board)
            lb.save()
        except Exception as e:
            print(f"openings: update stats fallito: {e}")


# "Study openings": you must always play the best move while the computer replies
# with one of the lines stored in the PGN (typically an opening repertoire).
def playOpening():
    filename = positionParameters.get("filename")
    if filename is None:
        return

    # Auto-rileva il colore dell'utente dal contenuto del PGN. Fallback a Bianco
    # se il file non contiene varianti (es. una sola linea, niente da dedurre).
    pgn_path = os.path.join(pgngamelist.PGN_FOLDER, filename + ".pgn")
    detected = detect_user_color_from_pgn(pgn_path)
    human_color = detected or "w"

    app.main_menu.disable()
    app.main_menu.full_reset()
    if detected is None:
        # informativa: nessuna variante trovata, parto da Bianco di default
        app.main_background()
        BS.drawEndGameText(app.screen, None,
                           f"Colore non rilevabile dal PGN -- gioco Bianco di default", size=18)
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
    # Stato pulito per il toggle E: se un mode precedente aveva lasciato
    # l'analisi attiva, il primo E qui finirebbe nel ramo "stop" invece di
    # avviarla.
    UCIEngines.stop_analysis()

    gamelist = pgngamelist.PgnGameList(filename)

    # Learning base degli errori per questo file di repertorio (mirror del
    # pattern usato in `Allena finali`). Creata/aperta una sola volta per
    # tutta la sessione di study openings.
    lb = _get_or_create_opening_base(filename)

    running = True
    sqSelected = ()
    playerClicks = []
    moveMade = False
    animate = False
    BS.show_pgn = False
    BS.show_book=False
    # show_cpu deve seguire lo stato reale dell'engine, altrimenti se l'analisi
    # era rimasta attiva dalla posizione precedente il pannello CPU resta vuoto
    # mentre il motore gira in background.
    BS.show_cpu = UCIEngines.is_analysing()
    BS.clearCPU(app.screen)
    
    help_text = [
            "Istruzioni:",
            "- left to take back a move",
            "- right to play next move",
            "- Q per uscire",
            "- H Hint (mostra la mossa corretta)",
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

    color_label = {"w": "Bianco", "b": "Nero"}.get(humanColor, "?")
    BS.set_context_label(f"Apertura: {filename} ({color_label})")

    # Toolbar (fase 2): stesso pattern degli altri mode.
    def _post_key(key, mod=0):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key, mod=mod))
    # NB: Undo NON e' esposto come pulsante in Study openings: il mode e' un
    # esercizio "trova-la-mossa-giusta", non free play, e gs.undoMove()
    # interagisce in modo non intuitivo con la sequenza (stopCondition / auto-
    # moves dell'avversario), facendo "saltare" passi della soluzione. La
    # scorciatoia tastiera Z/Left resta disponibile per uso volontario.
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

        if state.play_position:
            # Lead-in Skip: scegli uniformemente la profondita' di partenza tra
            # tutti i turni utente della linea. Pre-scan della mainline a partire
            # da gs.node per contare N turni utente, poi target = randint(1, N).
            # Camminiamo la linea (mainline per l'utente, variante random per il
            # computer) e ci fermiamo al target-esimo turno utente. La vecchia
            # versione (1/3 di break ad ogni turno utente) dava una distribuzione
            # geometrica che privilegiava fortemente le prime mosse del repertorio.
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
            # undo dell'ultima mossa: arriva l'utente che deve rigiocarla
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
            time_delta = app.clock.tick(60) / 1000.0   # pace + dt per la toolbar
            UCIEngines.poll()  # drena gli info engine (no-op se analisi off)
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
                    # Solo click sinistro skippa: la rotellina (button 4/5) NO.
                    mustSkip = True
                    break
                elif  e.type == p.MOUSEBUTTONDOWN and e.button == 3:
                        # Mostra aiuto quando il tasto destro è premuto
                        show_help = True
                        # play_position = 1
                elif e.type == p.MOUSEBUTTONUP and e.button == 3:
                        # Nasconde aiuto quando il tasto destro è rilasciato
                        show_help = False
                elif e.type == p.MOUSEBUTTONDOWN and not gameOver and humanCanPlay and not toolbar.pointer_in_toolbar(e.pos):

                    row, col = BS.getRowColFromLocation(p.mouse.get_pos())

                    if sqSelected == (row, col) or col >= 8 or row>=8: # user clicked same square or in move log
                        sqSelected = ()
                        playerClicks = []
                    else:
                        sqSelected = (row, col)
                        playerClicks.append(sqSelected)

                    if len(playerClicks) == 2:
                        move = Move(playerClicks[0], playerClicks[1], gs)

                        if (move.pieceMoved[1] == "P") and (row == 0 or row == 7):
                            validPromotions = [m for m in validMoves if m.startRow == playerClicks[0][0] and
                                               m.startCol == playerClicks[0][1] and
                                               m.stopRow == playerClicks[1][0] and
                                               m.stopCol == playerClicks[1][1]
                                               ]

                            if len(validPromotions) > 0:
                                piece = BS.choosePromotion(app.screen, move.pieceMoved[0])
                                move = move.promoteToPiece(piece)

                        # print(move.getChessNotation())
                        validMove = next((m for m in validMoves if move == m), None)
                        if validMove is not None:
                            # Stato della board PRIMA della mossa: serve per il
                            # logging in learning base (chiave = zobrist della
                            # posizione dove l'utente ha mosso).
                            _board_pre = gs.node.board()
                            _next_main = gs.getNextMainMove()
                            _correct_uci = _next_main.uci() if _next_main else None
                            if gs.checkNextMove(validMove.move):
                                # Mossa corretta: aggiorna stats se la posizione
                                # e' gia' nella base (no-op se non tracciata).
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
                                # Mossa errata: aggiunta o aggiornata nella base.
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
                            sqSelected = ()
                            playerClicks = []
                        else:
                            sqSelected = (row, col)
                            playerClicks = [sqSelected]

                    if len(playerClicks) == 1 and gs.colorAt(row, col) != gs.colorToMove():
                        sqSelected = ()
                        playerClicks = []

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
                        # Bugfix: prima questa branca scriveva "whiteUp = not whiteUp"
                        # ma whiteUp non era una locale -> UnboundLocalError al runtime.
                        # Ora usa BS.flipBoard come gli altri mode.
                        BS.flipBoard(app.screen)
                        animate = False

                    if e.key == p.K_h and humanCanPlay:
                        # Hint: mostra in SAN la mossa attesa dalla mainline.
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
                # Frame idle: ridisegniamo la toolbar (per i tooltip) e flippiamo.
                toolbar.draw(app.screen)
                p.display.update()
                continue

            if show_help:
                do_show_help()
                continue

            if moveMade and not mustSkip:
                moveMade = False
                # Se l'analisi e' attiva, aggancia la nuova posizione (no-op se off).
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
