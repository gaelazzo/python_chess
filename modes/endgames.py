"""Modalita' 'Allena finali'.

Selezione: l'utente sceglie un file PGN dalla cartella `endgames/`. Il programma
estrae una partita random e usa la sua posizione iniziale (header FEN se
presente) come finale da risolvere -- la mainline del PGN e' ignorata: il
giudice e' la TB Syzygy (per posizioni con <=7 pezzi) o Stockfish in fallback.

Loop di gioco:
- l'utente gioca dal lato al tratto nella posizione iniziale;
- per ogni sua mossa, si confronta WDL(prima)/WDL(dopo) via Syzygy:
  - WDL invariato (o migliorato) -> OK, l'avversario risponde;
  - WDL peggiorato -> take-back, lampeggia "mossa sbagliata, riprova";
- se la posizione e' fuori range TB, si usa Stockfish: confronto eval prima/dopo,
  drop > BLUNDER_CP -> errore;
- l'avversario sceglie la mossa TB-ottima quando possibile, altrimenti Stockfish.
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
import UCIEngines
import BoardScreen as BS
from toolbar import Toolbar, ToolbarAction
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


# Soglia di blunder per il giudizio engine-based (centipawns).
BLUNDER_CP = 100
# Tempo di pondering per le risposte engine (secondi).
ENGINE_REPLY_TIME = 0.5
# Tempo di analisi per il giudizio engine-based (secondi).
ENGINE_JUDGE_TIME = 2
# Severity uniforme per errori TB-based (gli errori engine-based usano il drop in cp).
TB_ERROR_SEVERITY = 100


def _get_or_create_endgame_base(filename: str) -> Optional[LearningBase]:
    """Recupera o crea la learning base associata al file PGN di finali.

    Naming convention: `endgames_<filename>`. Cosi' la base appare in
    `Solve positions` come una qualsiasi altra learning base, e l'utente
    puo' ripassare gli errori commessi nei finali con lo stesso flusso
    della tattica/aperture.
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
        print(f"endgames: impossibile creare la base '{base_name}': {e}")
        return None


def _best_move_for_position(board: chess.Board) -> Optional[chess.Move]:
    """Migliore mossa: TB ottima se in range, altrimenti Stockfish."""
    mv = sh.best_tb_move(board)
    if mv is not None:
        return mv
    return _engine_reply(board)


def _log_user_move_to_base(lb: Optional[LearningBase], game: chess.pgn.Game,
                           board: chess.Board, played_uci: str, ok: bool) -> None:
    """Aggiorna la learning base degli errori per i finali.

    - Errore: aggiunge (o aggiorna) la posizione con la mossa giusta calcolata
      al volo (TB ottima o fallback engine), severity=TB_ERROR_SEVERITY.
    - Successo su posizione gia' tracciata: aggiorna stats riusando `position.ok`
      gia' memorizzata -- evita un probe TB/engine sulla via felice.
    - Successo su posizione mai vista: no-op (non spammiamo la base).
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
            print(f"endgames: errore salvataggio posizione: {e}")
    elif zobrist in lb.positions:
        stored_ok = lb.positions[zobrist].ok
        try:
            lb.updatePosition(played_uci, stored_ok, game, board)
            lb.save()
        except Exception as e:
            print(f"endgames: errore aggiornamento stats: {e}")


def _load_games(pgn_path: str) -> List[chess.pgn.Game]:
    """Carica tutte le partite dal file PGN."""
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
    """Score in centipawns dal punto di vista di `turn`, mate-adjusted."""
    if score is None:
        return None
    pov = score.pov(turn)
    if pov.is_mate():
        # Mate per noi: +30000; subito mate: -30000 (mate counter ridotto = piu' grave).
        m = pov.mate()
        if m is None:
            return None
        return 30000 - m if m > 0 else -30000 - m
    return pov.score(mate_score=30000)


def _engine_eval_cp(board: chess.Board, turn: chess.Color) -> Optional[int]:
    """Eval in cp di `board` dal POV di `turn`; None se motore non disponibile."""
    if UCIEngines.engine is None:
        return None
    try:
        info = UCIEngines.engine.analyse(
            board, chess.engine.Limit(time=ENGINE_JUDGE_TIME),
            info=chess.engine.INFO_SCORE,
        )
        return _format_score_cp(info.get("score"), turn)
    except Exception as e:
        print(f"endgames: engine analyse fallito: {e}")
        return None


def _engine_reply(board: chess.Board) -> Optional[chess.Move]:
    """Mossa di risposta scelta dal motore."""
    if UCIEngines.engine is None:
        return None
    try:
        result = UCIEngines.engine.play(board, chess.engine.Limit(time=ENGINE_REPLY_TIME))
        return result.move
    except Exception as e:
        print(f"endgames: engine play fallito: {e}")
        return None


def _effective_wdl(wdl: Optional[int], dtz: Optional[int], halfmove_clock: int) -> Optional[int]:
    """WDL effettivo dato il clock reale del 50-move rule.

    probe_wdl di Syzygy assume `halfmove_clock=0` (clean clock). Per sapere
    quanto la vincita e' realmente convertibile bisogna combinare WDL+DTZ con
    il clock attuale: se manca budget per arrivare alla prossima mossa zeroing
    (cattura o spinta di pedone), la partita finisce in patta per 50-move
    rule e l'WDL "vero" e' 0.

    Mapping:
      wdl == +2 e clock + |DTZ| <= 100 -> +2
      wdl == +2 e clock + |DTZ| >  100 ->  0  (patta forzata dal 50-move)
      wdl == +1 o -1 (cursed/blessed)  ->  0  (per definizione gia' irraggiungibile)
      wdl == -2 e clock + |DTZ| <= 100 -> -2
      wdl == -2 e clock + |DTZ| >  100 ->  0  (siamo "salvati" dal 50-move)
      wdl ==  0                        ->  0
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
    """Minimo DTZ (dal nostro POV) ottenibile fra le mosse legali che
    preservano un WDL >= `min_our_wdl`. None se nessuna mossa qualificata
    o se la TB non e' disponibile.

    Serve per giudicare se la mossa dell'utente e' "ottima quanto la migliore"
    in termini di DTZ: dtz_a == best -> OK; dtz_a > best -> suboptimal.
    Nei casi di endgame "near zeroing" (es. KQ vs KP, mate forzato via
    promozione), il DTZ del figlio puo' essere == DTZ del padre per l'ottimo;
    confrontare con `best` aggira il falso negativo della rule `dtz_a < dtz_b`.
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
    """Giudica la mossa dell'utente. Ritorna (is_ok, debug_info).

    Regole (in ordine):
    1. **Patta forzata** (stallo / materiale insufficiente) data dall'utente:
       se prima eri in WDL>0, e' un errore.
    2. **Scacco matto** dato dall'utente: sempre OK.
    3. **WDL clean peggiorato**: flag.
    4. **Optimality DTZ** (solo con clean WDL=+2): se non e' una mossa zeroing,
       il DTZ post-mossa (dal nostro POV) deve essere uguale al **minimo
       ottenibile** fra le mosse legali +2-preserving. Cosi' una mossa con
       `dtz_a == dtz_b` viene accettata se e' davvero l'ottima TB (caso
       KQ vs KP nell'ultimo ply prima della promozione forzata), mentre
       una mossa "lenta" che porta a DTZ piu' alto del best disponibile
       viene flaggata.
    5. Fuori TB: fallback Stockfish, confronto eval con soglia BLUNDER_CP.
    """
    turn = board_before.turn
    # --- TB ---
    wdl_b = sh.probe_wdl(board_before)
    if wdl_b is not None:
        dtz_b = sh.probe_dtz(board_before)

        nb = board_before.copy(stack=False)
        nb.push(move)

        # Caso 1+2: posizione figlia terminale.
        if nb.is_checkmate():
            return True, f"checkmate (WDL pre {wdl_b:+d}, DTZ pre {dtz_b})"
        if nb.is_stalemate() or nb.is_insufficient_material():
            ok = wdl_b <= 0
            kind = "stallo" if nb.is_stalemate() else "materiale insufficiente"
            return ok, f"{kind} forzato (WDL pre {wdl_b:+d}) -- {'patta accettabile' if ok else 'ERRORE: stavi vincendo'}"

        if not sh.is_in_tb_range(nb):
            return True, f"TB child out of range (WDL pre {wdl_b:+d})"
        try:
            cwdl = sh.open_tablebase().probe_wdl(nb)
            cdtz = sh.open_tablebase().probe_dtz(nb)
        except (chess.syzygy.MissingTableError, KeyError, IndexError):
            return True, f"TB child probe failed (WDL pre {wdl_b:+d})"
        wdl_a = -cwdl
        dtz_a = -cdtz

        # Caso 3: WDL clean peggiorato.
        if wdl_a < wdl_b:
            return False, f"WDL drop {wdl_b:+d}->{wdl_a:+d} (DTZ {dtz_b}->{dtz_a})"

        # Caso 4: con clean WDL=+2, la mossa deve essere DTZ-ottima fra le
        # +2-preserving (non basta che il DTZ "non aumenti", e nemmeno che
        # cali strettamente: in posizioni near-zeroing l'ottima puo' avere
        # dtz_a == dtz_b).
        if wdl_b == 2:
            is_zeroing = nb.halfmove_clock == 0
            if not is_zeroing:
                best = _best_child_dtz_among(board_before, min_our_wdl=2)
                if best is not None and dtz_a > best:
                    return False, (f"non ottima: DTZ {dtz_b}->{dtz_a} "
                                   f"(ottima raggiungibile = {best})")

        return True, f"WDL {wdl_b:+d}->{wdl_a:+d}, DTZ {dtz_b}->{dtz_a}, clock {board_before.halfmove_clock}->{nb.halfmove_clock}"

    # --- Fallback Stockfish ---
    eval_before = _engine_eval_cp(board_before, turn)
    nb = board_before.copy(stack=False)
    nb.push(move)
    eval_after_opp = _engine_eval_cp(nb, not turn)
    if eval_before is None or eval_after_opp is None:
        return True, "Engine indisponibile -- non giudicato"
    eval_after = -eval_after_opp
    drop = eval_before - eval_after
    return drop <= BLUNDER_CP, f"Eng {eval_before}cp -> {eval_after}cp (drop {drop})"


def _opponent_move(board: chess.Board) -> Optional[chess.Move]:
    """Mossa dell'avversario: TB-ottima se possibile, altrimenti Stockfish."""
    mv = sh.best_tb_move(board)
    if mv is not None:
        return mv
    return _engine_reply(board)


def playEndgames() -> None:
    """Entry-point dal menu: carica le partite e cicla finche' utente non esce."""
    from state import positionParameters
    filename = positionParameters.get("filename")
    if not filename:
        return
    pgn_path = os.path.join(ENDGAMES_FOLDER, filename + ".pgn")
    games = _load_games(pgn_path)

    # Stato di partenza pulito per il toggle E: se un mode precedente aveva
    # lasciato l'analisi attiva, il primo E qui finirebbe nel ramo "stop"
    # (visualizzando 'engine stopped') invece di avviare l'analisi.
    UCIEngines.stop_analysis()

    app.main_menu.disable()
    app.main_menu.full_reset()

    if not games:
        app.main_background()
        BS.drawEndGameText(app.screen, None,
                           f"Nessuna partita in {filename}.pgn (cartella endgames/)")
        BS.update()
        app.delay(2)
        app.main_menu.enable()
        return

    # Sessione: pesca senza rimpiazzo; quando finisce, ricomincia.
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
    """Esercita una singola posizione. Ritorna 'next' o 'quit'."""
    # Stato di gioco: posizione iniziale = root del PGN (FEN header se presente).
    gs = GameState()
    gs.setPgn(game)
    start_board = gs.node.board()

    if start_board.is_game_over():
        # Posizione gia' terminale: salta.
        return "next"

    # Learning base degli errori per questo file: creata/aperta alla prima entrata.
    lb = _get_or_create_endgame_base(filename)

    human_color_chess = start_board.turn  # bool True=White
    human_color = "w" if human_color_chess else "b"
    color_label = "Bianco" if human_color_chess else "Nero"

    title = game.headers.get("White", "") + " - " + game.headers.get("Black", "")
    site = game.headers.get("Site", "")
    if not title.strip("- "):
        title = site or f"#{idx}"
    BS.set_context_label(f"Finale: {filename} -- {title} ({idx}/{total}, gioca {color_label})")

    BS.show_pgn = False
    BS.show_book = False
    BS.show_cpu = False
    BS.clearCPU(app.screen)
    BS.setWhiteUp(app.screen, not human_color_chess)
    BS.drawGameState(app.screen, gs, [], [], ())
    BS.update()

    # Info iniziale: pezzi e WDL.
    n_pieces = sh.count_pieces(start_board)
    wdl0 = sh.probe_wdl(start_board)
    wdl_txt = f"WDL={wdl0:+d}" if wdl0 is not None else "fuori TB"
    print(f"[endgames] {title}: {n_pieces} pezzi, {wdl_txt}")

    # Toolbar.
    def _post_key(key, mod=0):
        return lambda: p.event.post(p.event.Event(p.KEYDOWN, key=key, mod=mod))
    toolbar = Toolbar([
        ToolbarAction("Flip",  "Flip board (F)",               _post_key(p.K_f)),
        ToolbarAction("Hint",  "Mostra mossa corretta (H)",    _post_key(p.K_h)),
        ToolbarAction("Eng",   "Engine on/off (E)",            _post_key(p.K_e)),
        ToolbarAction("Moves", "Toggle move list (D)",         _post_key(p.K_d)),
        ToolbarAction("C-FEN", "Copy FEN (C)",                 _post_key(p.K_c)),
        ToolbarAction("Next",  "Prossimo finale (N)",          _post_key(p.K_n)),
        ToolbarAction("Quit",  "Torna al menu (Q)",            _post_key(p.K_q)),
    ])

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
        "Istruzioni:",
        "- click per muovere",
        "- H mossa corretta (hint)",
        "- N prossimo finale",
        "- Q torna al menu",
        "- F flip board",
        "- D toggle move list",
        "- E engine on/off",
    ]

    while not must_skip and not quit_flag:
        time_delta = app.clock.tick(60) / 1000.0
        UCIEngines.poll()  # drena gli info engine (no-op se analisi off)
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
            # Auto-avanza al prossimo finale (come Study openings). Q durante il delay
            # interrompe; il prossimo giro del while esterno pesca un'altra partita.
            break

        # --- Mossa avversario ---
        if not gameOver and not humanCanPlay and not moveMade:
            mv = _opponent_move(board)
            if mv is None:
                # Patta forzata o errore: mostra un messaggio e termina.
                show_message(gs, "Nessuna mossa avversario (TB+engine ko)")
                app.delay(1)
                break
            gs.makeMove(Move.fromChessMove(mv, gs))
            moveMade = True
            animate = True
            validMoves = gs.stdValidMoves()
            update = True

        # --- Eventi ---
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
                if sqSelected == (row, col) or col >= 8 or row >= 8:
                    sqSelected = ()
                    playerClicks = []
                else:
                    sqSelected = (row, col)
                    playerClicks.append(sqSelected)

                if len(playerClicks) == 2:
                    move = Move(playerClicks[0], playerClicks[1], gs)
                    # Promozione
                    if move.pieceMoved[1] == "P" and (row == 0 or row == 7):
                        promos = [m for m in validMoves
                                  if m.startRow == playerClicks[0][0] and m.startCol == playerClicks[0][1]
                                  and m.stopRow == playerClicks[1][0] and m.stopCol == playerClicks[1][1]]
                        if promos:
                            piece = BS.choosePromotion(app.screen, move.pieceMoved[0])
                            move = move.promoteToPiece(piece)
                    validMove = next((m for m in validMoves if move == m), None)
                    if validMove is not None:
                        # --- Giudizio ---
                        ok, why = _judge_user_move(board, validMove.move)
                        print(f"[endgames] mossa {validMove.move.uci()}: {'OK' if ok else 'ERR'} | {why}")
                        # Logging in learning base: errore -> aggiunge/aggiorna;
                        # successo -> aggiorna stats solo se gia' tracciata.
                        _log_user_move_to_base(lb, game, board, validMove.move.uci(), ok)
                        if ok:
                            gs.makeMove(validMove)
                            moveMade = True
                            animate = True
                            validMoves = gs.stdValidMoves()
                        else:
                            # Take-back implicito: NON pushiamo la mossa, l'utente puo' riprovare.
                            short = why.split(' (')[0] if why else "errore"
                            # show_message default = font 32: troppo grande per messaggi >20 char.
                            # Usiamo drawEndGameText con size piu' piccola e delay piu' lungo.
                            BS.drawEndGameText(app.screen, gs, f"Mossa errata: {short}", size=20)
                            app.delay(2.5)
                            update = True
                        sqSelected = ()
                        playerClicks = []
                    else:
                        sqSelected = (row, col)
                        playerClicks = [sqSelected]

                if len(playerClicks) == 1 and gs.colorAt(row, col) != gs.colorToMove():
                    sqSelected = ()
                    playerClicks = []

            elif e.type == p.KEYDOWN:
                if e.key == p.K_q:
                    quit_flag = True
                elif e.key == p.K_n:
                    must_skip = True
                elif e.key == p.K_h:
                    # Hint: mostra la mossa TB-ottima (o engine se fuori TB).
                    suggestion = sh.best_tb_move(board) or _engine_reply(board)
                    if suggestion is not None:
                        show_message(gs, f"Hint: {board.san(suggestion)}")
                    else:
                        show_message(gs, "Nessun hint disponibile")
                    app.delay(1)
                elif e.key == p.K_f:
                    BS.flipBoard(app.screen)
                    animate = False
                elif e.key == p.K_c:
                    glc.copy_to_clipboard(board.fen(), "FEN copiata", gs)
                elif e.key == p.K_d:
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
            # Se l'analisi e' attiva, aggancia la nuova posizione (no-op se off).
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
    """Messaggio finale a partire dal risultato PGN e dal lato umano."""
    if result == "1/2-1/2":
        return "Patta"
    if result == "1-0":
        return "Vittoria" if human_is_white else "Sconfitta"
    if result == "0-1":
        return "Vittoria" if not human_is_white else "Sconfitta"
    return "Fine"
