"""Learning-base administration actions (menu-triggered).

Create/update learning bases, unroll PGNs into positions/lessons, import
chess.com games, and register a base as a BrainMaster course. Split out of
chessMain.py; depends only on shared state, app and the domain modules.
"""
import os
import pygame as p
from app_context import app
import BoardScreen as BS
import analyzer
import chess_com_download
import lichess_download
import BrainMaster
import pgngamelist
from LearningBase import LearningBase, learningBases
from state import positionParameters


def _count_games_in_pgn(path: str) -> int:
    """Conta veloce le partite contando le righe `[Event ...]`. 0 se errore."""
    n = 0
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("[Event "):
                    n += 1
    except OSError:
        return 0
    return n


def _make_progress_cb(label: str, total: int):
    """Callback per `analyzer.analyzePgn(progress=...)`: ridisegna lo schermo
    con N/M e fa un event.pump() per evitare il "non risponde" di Windows."""
    def cb(n: int) -> None:
        app.main_background()
        msg = f"{label}: analizzo {n}/{total}" if total else f"{label}: analizzo partita {n}"
        BS.drawEndGameText(app.screen, None, msg, size=24)
        p.event.pump()
    return cb


def createLearningBase():    
    # Verifica che filename non sia vuoto
    filename = positionParameters.get("filename", "").strip()
    if not filename:
        raise ValueError("Il campo 'filename' in positionParameters è vuoto.")


    learningBase = LearningBase(movesToAnalyze=positionParameters.get("movesToAnalyze",16),
                                                               blunderValue=positionParameters.get("blunderValue", 80),
                               ponderTime=positionParameters.get("ponderTime", 0.5),
                                useBook=positionParameters.get("useBook", False))

    learningBase.setFileName(filename)
    learningBases[filename] = learningBase
    learningBase.save()

    app.main_background()
    BS.drawEndGameText(app.screen, None, f"learning base created")
    BS.update()
    app.delay(2 )
    return

# add the games in the pgn file specified in positionParameters["filename"] to the LearningBase specified in positionParameters["base"],
#  analyzing them with the parameters specified in positionParameters, and save the updated LearningBase
def updateLearningBase():
    pgnFileName = positionParameters.get("filename", None)
    learningBaseName = positionParameters.get("base", None)
    player = positionParameters.get("player", None)
    if pgnFileName is None :
        text = "Please select a PGN file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        return

    if learningBaseName is None:
        text = "Please select a base file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        return

    if player is None or player == "":
        text = "Please enter a player name"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        return

    learningBase = learningBases.get(learningBaseName, None)

    # Conteggio veloce per la barra di avanzamento (N/M durante analisi).
    pgn_path = os.path.join(pgngamelist.PGN_FOLDER, pgnFileName + ".pgn")
    total = _count_games_in_pgn(pgn_path)
    progress = _make_progress_cb(f"Aggiorno '{learningBaseName}'", total)

    analyzer.analyzePgn(pgnFileName, player, learningBase, progress=progress)
    text = f"Learning base {learningBaseName} updated with {pgnFileName}"
    app.main_background()
    BS.drawEndGameText(app.screen, None, text)
    BS.update()

#transforms a pgn file into a set of positions to use with Brainmaster
def unrollPgnAsLesson():
    pgnFileName = positionParameters.get("filename", None)
    if pgnFileName is None :
        text = "Please select a PGN file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        return

    learningBaseName = positionParameters.get("base", None)
    learningBase = learningBases.get(learningBaseName, None)
    analyzer.unrollPgn_as_lesson(pgnFileName+".pgn", learningBase, positionParameters.get("color", "w")=="w")
        
    app.main_background()
    BS.drawEndGameText(app.screen, None, f"Unroll {pgnFileName} as a lesson done")
    BS.update()
    app.delay(2)
    return

def unrollPGN():
    pgnFileName = positionParameters.get("filename", None)
    if pgnFileName is None :
        text = "Please select a PGN file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        return

    learningBaseName = positionParameters.get("base", None)
    learningBase = learningBases.get(learningBaseName, None)
    analyzer.unrollPgn(pgnFileName+".pgn", learningBase, positionParameters.get("color", "w")=="w")
        
    app.main_background()
    BS.drawEndGameText(app.screen, None, "Unroll done")
    BS.update()
    app.delay(2)
    return

def readChessComGames(): 
    '''
    Reads a file with Chess.com games and creates a LearningBase from it.
    The file must be in the format of a Chess.com export, with each game separated by a blank line.
    '''
    pgnFileName = positionParameters.get("filename", None)
    if pgnFileName is None :
        text = "Please select a PGN file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2)
        return
    
    chess_com_download.load(positionParameters.get("player", None), pgnFileName, positionParameters.get("color",None))

    app.main_background()
    BS.drawEndGameText(app.screen, None, "Games downloaded")
    BS.update()
    app.delay(2)


def readLichessGames():
    '''
    Scarica incrementalmente le partite lichess dell'utente nel PGN scelto.
    Stessi parametri di readChessComGames (filename, player, color) presi da
    positionParameters; dedup automatica nel modulo lichess_download.
    '''
    pgnFileName = positionParameters.get("filename", None)
    if pgnFileName is None:
        text = "Please select a PGN file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2)
        return

    lichess_download.load(
        positionParameters.get("player", None),
        pgnFileName,
        positionParameters.get("color", None),
    )

    app.main_background()
    BS.drawEndGameText(app.screen, None, "Games downloaded")
    BS.update()
    app.delay(2)


def createCourse():
    '''
    Registers a new BrainMaster base, which is a LearningBase with a specific name.
    The name is taken from the positionParameters["base"] variable.
    '''
    learningBaseName = positionParameters.get("base", None)
    if learningBaseName is None or learningBaseName == "":
        text = "Please select a base file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2)
        return

    if not learningBaseName in learningBases:
        text = f"Base {learningBaseName} does not exist"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2)
        return

    BrainMaster.add_to_BrainMaster(learningBaseName)
    text = f"Base {learningBaseName} added to Brainmaster"
    app.main_background()
    BS.drawEndGameText(app.screen, None, text)
    BS.update()
