#isready

# setoption name UCI_Elo value 1800   su STOCKFISH

# ucinewgame  per iniziare una nuova partita

#position [fen  | startpos ]  moves  ....

#go inizia a pensare
#
# * searchmoves  ....
# 	restrict search to this moves only
# 	Example: After "position startpos" and "go infinite searchmoves e2e4 d2d4"
# 	the engine should only search the two moves e2e4 and d2d4 in the initial position.
# * ponder
# 	start searching in pondering mode.
# 	Do not exit the search in ponder mode, even if it's mate!
# 	This means that the last move sent in in the position string is the ponder move.
# 	The engine can do what it wants to do, but after a "ponderhit" command
# 	it should execute the suggested move to ponder on. This means that the ponder move sent by
# 	the GUI can be interpreted as a recommendation about which move to ponder. However, if the
# 	engine decides to ponder on a different move, it should not display any mainlines as they are
# 	likely to be misinterpreted by the GUI because the GUI expects the engine to ponder
#    on the suggested move.
# * wtime
# 	white has x msec left on the clock
# * btime
# 	black has x msec left on the clock
# * winc
# 	white increment per move in mseconds if x > 0
# * binc
# 	black increment per move in mseconds if x > 0
# * movestogo
#   there are x moves to the next time control,
# 	this will only be sent if x > 0,
# 	if you don't get this and get the wtime and btime it's sudden death
# * depth
# 	search x plies only.
# * nodes
#    search x nodes only,
# * mate
# 	search for a mate in x moves
# * movetime
# 	search exactly x mseconds
# * infinite
# 	search until the "stop" command. Do not exit the search without being told so in this mode!
from __future__ import annotations 
from re import I
from typing import Optional,List
# from pickle import NONE
import chess
import chess.engine
import atexit
import os
import sys
import Board
engineFileName: Optional[str] = None
engine:chess.engine.SimpleEngine =None
from  config import config
import time



def get_base_path():
    """Restituisce il percorso della cartella dove si trova l'eseguibile o lo script"""
    if getattr(sys, 'frozen', False):  # Se è un eseguibile PyInstaller
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
ENGINE_FOLDER = os.path.join(BASE_PATH, "engines")



if not os.path.exists(ENGINE_FOLDER):
    os.makedirs(ENGINE_FOLDER)  # crea la cartella (e tutte le sottocartelle necessarie)        


def engine_open():
    global engine
    try:
        engine = chess.engine.SimpleEngine.popen_uci(os.path.abspath(os.path.join(ENGINE_FOLDER,config.engine)))
        print(f"Engine {config.engine} opened successfully.")
        print(f"Engine ID: {engine.id["name"]}")
    except FileNotFoundError:
        print(f"Engine file {config.engine} not found. Please check the configuration.")        
    except Exception as e:
        print(f"An error occurred while opening the engine: {e}")




already_closing = False

def engine_close():
    
    global engine, already_closing
    if already_closing:
        return
    already_closing = True

    if engine is not None:
        try:
            print(f"Closing engine...{engine.id}")
            engine.close()
            time.sleep(0.1)
            print(f"engine closed.\n")
        except chess.engine.EngineTerminatedError:
            print("Engine already terminated.")
        except Exception as e:
            print(f"An error occurred while closing the engine: {e}")
        finally:
            engine = None
            # del engine 
            already_closing = False

atexit.register(engine_close)
time.sleep(0.1)

def bestMove(board, validMoves:List[Board.Move], time=0.1, elo= None)->chess.Move:
    if elo is None:
        res:chess.engine.PlayResult = engine.play(board.board,
                          limit = chess.engine.Limit(time=time),
                          info = chess.engine.INFO_BASIC,
                          #options = {"UCI_Elo": 1600}
                          )
    else:
        res = engine.play(board.board,
                          limit=chess.engine.Limit(time=time),
                          info=chess.engine.INFO_BASIC,
                          options = {"UCI_Elo": elo}
                          )
    # assert(res.move is not None)
    return res.move


if __name__ == "__main__":
    engine_open()
    engine_close()
    