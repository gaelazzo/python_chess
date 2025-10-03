#isready
'''
{'Debug Log File': Option(name='Debug Log File', type='string', default='<empty>', min=None, max=None, var=[]),
 'NumaPolicy': Option(name='NumaPolicy', type='string', default='auto', min=None, max=None, var=[]),
 'Threads': Option(name='Threads', type='spin', default=1, min=1, max=1024, var=[]), 
 'Hash': Option(name='Hash', type='spin', default=16, min=1, max=33554432, var=[]), 
 'Clear Hash': Option(name='Clear Hash', type='button', default=None, min=None, max=None, var=[]),
 'Ponder': Option(name='Ponder', type='check', default=False, min=None, max=None, var=[]),
 'MultiPV': Option(name='MultiPV', type='spin', default=1, min=1, max=256, var=[]),
 'Skill Level': Option(name='Skill Level', type='spin', default=20, min=0, max=20, var=[]),
 'Move Overhead': Option(name='Move Overhead', type='spin', default=10, min=0, max=5000, var=[]), 
 'nodestime': Option(name='nodestime', type='spin', default=0, min=0, max=10000, var=[]), 
 'UCI_Chess960': Option(name='UCI_Chess960', type='check', default=False, min=None, max=None, var=[]),
 'UCI_LimitStrength': Option(name='UCI_LimitStrength', type='check', default=False, min=None, max=None, var=[]),
 'UCI_Elo': Option(name='UCI_Elo', type='spin', default=1320, min=1320, max=3190, var=[]),
 'UCI_ShowWDL': Option(name='UCI_ShowWDL', type='check', default=False, min=None, max=None, var=[]),
 'SyzygyPath': Option(name='SyzygyPath', type='string', default='<empty>', min=None, max=None, var=[]), 
 'SyzygyProbeDepth': Option(name='SyzygyProbeDepth', type='spin', default=1, min=1, max=100, var=[]),
 'Syzygy50MoveRule': Option(name='Syzygy50MoveRule', type='check', default=True, min=None, max=None, var=[]), 
 'SyzygyProbeLimit': Option(name='SyzygyProbeLimit', type='spin', default=7, min=0, max=7, var=[]), 
 'EvalFile': Option(name='EvalFile', type='string', default='nn-1111cefa1111.nnue', min=None, max=None, var=[]), 
 'EvalFileSmall': Option(name='EvalFileSmall', type='string', default='nn-37f18f62d772.nnue', min=None, max=None, var=[])}
'''

from __future__ import annotations 
import book
from re import I
from typing import Optional,List
# from pickle import NONE
import chess
import chess.engine
import atexit
import os
import sys
engineFileName: Optional[str] = None
engine:chess.engine.SimpleEngine =None
from  config import config
import time
from queue import Queue
import threading


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


def _getEngineFileName() -> str:
    """Restituisce il nome del file dell'engine configurato."""
    if config.engine is None or config.engine == "":
        raise ValueError("Engine name is not configured.")
    return os.path.abspath(os.path.join(ENGINE_FOLDER,config.engine))

def engine_open():
    global engine
    try:
        engine = chess.engine.SimpleEngine.popen_uci(_getEngineFileName())
        engine_options = getattr(config, "engine_options", {})

        engine.configure(engine_options)
        print(f"Engine {config.engine} opened successfully. Engine ID: {engine.id["name"]}")  
    except FileNotFoundError:
        print(f"Engine file {config.engine} not found. Please check the configuration.")        
    except Exception as e:
        print(f"An error occurred while opening the engine: {e}")


stopper = None

def cpu_is_on():
    return stopper is not None

def format_engine_info_list(info_list: list[chess.engine.InfoDict], max_variants=3) -> list[str]:
    result_lines = []

    # Prendi i dati generali dal primo info (ad es. tempo e nodi)
    if info_list:
        info0 = info_list[0]
        time_str = f"Time: {info0.get('time', 0):.2f}s"
        nodes_str = f"Nodes: {info0.get('nodes', '?')}"
        result_lines.append(f"{time_str} | {nodes_str}")

    for info in info_list[:max_variants]:
        parts = []
        score = info.get("score")
        if score:
            s = score.relative
            if isinstance(s, chess.engine.Mate):
                parts.append(f"Mate in {s.ply()}")
            elif isinstance(s, chess.engine.Cp):
                parts.append(f"Eval {s.score() / 100:.2f}")

        if "depth" in info:
            parts.append(f"Depth {info['depth']}")

        if "pv" in info:
            parts.append(" ".join(str(m) for m in info["pv"]))

        result_lines.append(" | ".join(parts))

    return result_lines






analysis_results = []  # Lista di dizionari validi con score + pv
latest_status_line = ""  # Ultima riga dello stato corrente
analysis_variants = {}  # memorizza info per ogni multipv


def analyze_forever(board, callback, interval_sec=1.0):
    global stopper, engine,analysis_results,latest_status_line

    if stopper is not None:
        stop_analysis()

    stop_event = threading.Event()
    stopper = stop_event
    
    analysis_results = []  # Lista di dizionari validi con score + pv
    latest_status_line = ""  # Ultima riga dello stato corrente
    def analysis_loop():
        global analysis_results, latest_status_line
        analysis_variants = {}
        try:
            with engine.analysis(board, multipv=3) as analysis:
                print(analysis)
                last_time = time.time()
                for info in analysis:
                    now = time.time()
                   
                    try:
                        if "multipv" in info and "score" in info and "pv" in info:
                            mpv = info["multipv"]
                            analysis_variants[mpv] = info  # aggiorna la variante
                            
                        elif "currmove" in info:
                            move_san = str(info["currmove"])
                            move_num = info.get("currmovenumber", "?")
                            depth = info.get("depth", "?")
                            latest_status_line = f"Analyzing: {move_san} (#{move_num}) with depth{depth}"
                        # else:
                        #     print(info)
                        #     print("Nessun dato utile nel pacchetto info")
                    except Exception as e:
                        print(f"Errore nella callback: {e}")

                    if now - last_time >= interval_sec:
                        infos_list = [analysis_variants[i] for i in sorted(analysis_variants.keys())]                                
                        analysis_results = format_engine_info_list(infos_list)
                        merged = analysis_results+[latest_status_line]
                        callback(merged)
                        last_time = now

                    if stop_event.is_set():
                        break
        except Exception as e:
            print(f"Errore nel blocco analysis: {e}")

    thread = threading.Thread(target=analysis_loop, daemon=True)
    thread.start()


def update_board(board: chess.Board, callback, interval_sec=1.0):
    ''' Update position to analyze if analysis is running '''
    if stopper is None:
        return
    stop_analysis()
    analyze_forever(board, callback,interval_sec)

def engine_on_off(board,callback,interval_sec=1.0):
    if stopper is None:
        analyze_forever(board, callback,interval_sec)
    else:
        stop_analysis()

def stop_analysis():
    global stopper
    if not stopper:
        #print("No analysis in progress.")
        return
    stopper.set()  # Imposta l'evento per fermare l'analisi
    stopper = None  # Resetta il riferimento per evitare chiamate multiple



already_closing = False
position_queue = Queue()


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

atexit.register(stop_analysis)
atexit.register(engine_close)
time.sleep(0.1)

def bestMove(board:chess.Board, time=0.1, elo= None)->chess.Move:
    if config.engine_usebook:
        moves = book.getMovesFromBook(board)
        if moves:
            return moves[0].move

    if elo is None:
        res:chess.engine.PlayResult = engine.play(board,
                          limit = chess.engine.Limit(time=time),
                          info = chess.engine.INFO_BASIC,
                          #options = {"UCI_Elo": 1600}
                          )
    else:
        res = engine.play(board,
                          limit=chess.engine.Limit(time=time),
                          info=chess.engine.INFO_BASIC,
                          options = {"UCI_Elo": elo}
                          )
    # assert(res.move is not None)
    return res.move


if __name__ == "__main__":
    engine_open()
    engine_close()
    