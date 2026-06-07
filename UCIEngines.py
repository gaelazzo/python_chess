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
from calendar import c 
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
    """Return the path of the folder where the executable or script is located"""
    if getattr(sys, 'frozen', False):  # If it is a PyInstaller executable
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
ENGINE_FOLDER = os.path.join(BASE_PATH, "engines")



if not os.path.exists(ENGINE_FOLDER):
    os.makedirs(ENGINE_FOLDER)  # create the folder (and all necessary subfolders)


def _getEngineFileName() -> str:
    """Return the file name of the configured engine."""
    if config.engine is None or config.engine == "":
        raise ValueError("Engine name is not configured.")
    return os.path.abspath(os.path.join(ENGINE_FOLDER,config.engine))

def engine_open():
    global engine, already_closing
    # Reset the "already_closing" flag: without this, after the first close
    # the flag stayed True and a subsequent engine_close was ignored.
    already_closing = False
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

    # Take the general data from the first info (e.g. time and nodes)
    if info_list:
        info0 = info_list[0]
        time_str = f"Time: {info0.get('time', 0):.2f}s"
        nodes_str = f"Nodes: {info0.get('nodes', '?')}"
        result_lines.append(f"{time_str} | {nodes_str}")

    for info in info_list[:max_variants]:
        parts = []
        score = info.get("score")
        if score:
            # White's point of view (absolute), like lichess/chess.com: positive =
            # White is better, negative = Black is better. This way the engine's
            # best line (always shown first) has the highest value when White is to
            # move and the lowest (most negative) when Black is to move.
            s = score.white()
            if isinstance(s, chess.engine.Mate):
                # White's POV: positive = White delivers mate, negative = Black does.
                parts.append(f"Mate in {s.mate()}")
            elif isinstance(s, chess.engine.Cp):
                parts.append(f"Eval {s.score() / 100:.2f}")

        if "depth" in info:
            parts.append(f"Depth {info['depth']}")

        if "pv" in info:
            parts.append(" ".join(str(m) for m in info["pv"]))

        result_lines.append(" | ".join(parts))

    return result_lines






analysis_results = []  # List of valid dictionaries with score + pv
latest_status_line = ""  # Last line of the current status


# "single-engine-thread, polling from main" architecture.
# We do not spawn our own analysis thread: python-chess's SimpleEngine
# already keeps a dedicated asyncio thread that receives updates from the
# Stockfish process and populates `SimpleAnalysisResult.multipv` (and .info) in a
# thread-safe way. The program's MainThread calls `poll()` every frame, reads
# a snapshot of the multipv (atomic via GIL) and invokes the callback to redraw
# the CPU panel.
#
# Advantages:
# - No additional thread: only MainThread + SimpleEngine (internal).
# - No race with rapid start/stop: everything sequential on main.
# - No join/timeout: stop_analysis() is truly immediate.
_active_analysis: Optional["chess.engine.SimpleAnalysisResult"] = None
_active_callback = None
_active_interval = 1.0
_last_callback_time = 0.0


def _engine_alive() -> bool:
    """True if the SimpleEngine and its asyncio transport are usable."""
    if engine is None:
        return False
    try:
        transport = getattr(engine, "transport", None)
        if transport is None:
            return False
        is_closing = getattr(transport, "is_closing", None)
        if callable(is_closing) and is_closing():
            return False
    except Exception:
        return False
    return True


def is_analysing() -> bool:
    """True if there is an active analysis not yet stopped."""
    return _active_analysis is not None


def stop_analysis() -> None:
    """Stop the active analysis. Idempotent. Does not raise."""
    global _active_analysis, _active_callback, stopper
    sa = _active_analysis
    _active_analysis = None
    _active_callback = None
    stopper = None  # legacy alias
    if sa is None:
        return
    try:
        # `stop()` signals the stop to the engine; the actual closing of the
        # asyncio task happens behind the scenes (SimpleEngine thread), and any
        # subsequent engine.analysis() is serialized by the internal lock.
        sa.stop()
    except Exception as e:
        print(f"stop_analysis: {e}")


def start_analysis(board, callback, interval_sec=1.0) -> None:
    """Start an analysis on the `board`. Stop the current one, if any.
    Reopen the engine if dead. Does not raise exceptions to the caller."""
    global _active_analysis, _active_callback, _active_interval, _last_callback_time
    global analysis_results, latest_status_line, stopper

    stop_analysis()
    if not _engine_alive():
        print("start_analysis: engine not alive, reopening...")
        try:
            engine_open()
        except Exception as e:
            print(f"start_analysis: engine_open failed: {e}")
            return
        if not _engine_alive():
            print("start_analysis: engine still not alive after retry, aborting")
            return

    try:
        sa = engine.analysis(board, multipv=3)
    except chess.engine.EngineError as e:
        print(f"start_analysis: EngineError {e} -- reopening")
        try:
            engine_open()
        except Exception as ee:
            print(f"start_analysis: reopen failed: {ee}")
            return
        try:
            sa = engine.analysis(board, multipv=3)
        except Exception as e2:
            print(f"start_analysis: second attempt failed: {e2}")
            return
    except Exception as e:
        print(f"start_analysis: unexpected error: {e}")
        return

    _active_analysis = sa
    _active_callback = callback
    _active_interval = interval_sec
    _last_callback_time = 0.0
    analysis_results = []
    latest_status_line = ""
    stopper = object()  # legacy: marks "something is running" for those testing truthiness


def poll() -> None:
    """To be called every frame from the MainThread.

    Reads the current state of the analysis (atomic snapshot of `multipv`),
    updates the CPU panel at most `_active_interval` times/s.
    No-op if no analysis is active.
    """
    global _active_analysis, _last_callback_time, analysis_results, latest_status_line, stopper
    sa = _active_analysis
    if sa is None or _active_callback is None:
        return

    # Detect engine crash: the transport died under us.
    if not _engine_alive():
        print("poll: engine not alive, cleanup and reopen")
        _active_analysis = None
        stopper = None
        try:
            _active_callback(["Engine crashed, next toggle restarts"])
        except Exception:
            pass
        try:
            engine_open()
        except Exception as e:
            print(f"poll: reopen failed: {e}")
        return

    # Snapshot of the multipv. The list is updated by the SimpleEngine thread; the
    # copy (`list(...)`) is atomic thanks to the GIL.
    try:
        multipv = list(sa.multipv)
    except Exception as e:
        print(f"poll: read multipv failed: {e}")
        return

    # Status line: we take it from `sa.info` (last info received, any type).
    try:
        info = sa.info
        if info and "currmove" in info:
            move_san = str(info["currmove"])
            move_num = info.get("currmovenumber", "?")
            depth = info.get("depth", "?")
            latest_status_line = f"Analyzing: {move_san} (#{move_num}) with depth{depth}"
    except Exception:
        pass

    now = time.time()
    if now - _last_callback_time < _active_interval:
        return
    _last_callback_time = now

    if not multipv:
        return
    try:
        analysis_results = format_engine_info_list(multipv)
        _active_callback(analysis_results + [latest_status_line])
    except Exception as e:
        print(f"poll: callback failed: {e}")


# Backward-compatible alias: the old modes called analyze_forever.
def analyze_forever(board, callback, interval_sec=1.0):
    start_analysis(board, callback, interval_sec)


def update_board(board: chess.Board, callback, interval_sec=1.0) -> None:
    """Re-attach the analysis to the new position ONLY if it is already running."""
    if not is_analysing():
        return
    start_analysis(board, callback, interval_sec)


def engine_on_off(board, callback, interval_sec=1.0) -> None:
    """User toggle: if analyzing then stop, otherwise start."""
    if is_analysing():
        stop_analysis()
        try:
            callback(["engine stopped"])
        except Exception:
            pass
    else:
        start_analysis(board, callback, interval_sec)



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


def extract_lines(board, depth=None, multipv=1, time=None, root_moves=None, mate=None):
    global engine

    if mate is not None:
        limit = chess.engine.Limit(mate=mate)
    elif time is not None:
        limit = chess.engine.Limit(time=time)
    elif depth is not None:
        limit = chess.engine.Limit(depth=depth)
    else:
        raise ValueError("You must specify at least one of depth, time or mate")

    infos = engine.analyse(
        board,
        limit,
        multipv=multipv,
        root_moves=root_moves
    )

    lines = []
    for info in infos:
        pv = info.get("pv", [])
        score = info.get("score")

        lines.append({
            "moves": pv,
            "score": score
        })

    return lines



def pv_to_san(board, pv):
    b = board.copy()
    san_moves = []

    for move in pv:
        san_moves.append(b.san(move))
        b.push(move)

    return san_moves


def solve_position(board, depth, multipv, time=None, root_moves=None, mate=None):
    lines = extract_lines(board, depth=depth, multipv=multipv, time=time, root_moves=root_moves, mate=mate)

    def score_key(l):
        s = l["score"].white()
        return s.score(mate_score=10000)

    # sort by descending score
    lines.sort(key=score_key, reverse=True)

    result = []

    for l in lines:
        san = pv_to_san(board, l["moves"]) #[:8]
        result.append(" ".join(san))

    return result


def analyse_chessbase_style(board, time_limit=30, max_depth=40, multipv=10):
    """
    Emulate ChessBase-like behavior:
    - iterative deepening
    - global PV accumulation
    - stable final ranking
    """
    global engine
    import time
    start = time.time()



    pv_map = {}  # pv(tuple) -> best score

    depth = 1

    while depth <= max_depth:
        elapsed = time.time() - start
        if elapsed >= time_limit:
            break

        infos = engine.analyse(
            board,
            chess.engine.Limit(depth=depth),
            multipv=multipv
        )

        for info in infos:
            pv = tuple(info.get("pv", []))
            if not pv:
                continue

            score = info["score"].white().score(mate_score=10000)

            # keep only the best for that PV
            if pv not in pv_map or score > pv_map[pv]:
                pv_map[pv] = score

        depth += 1

    # global final ranking
    sorted_lines = sorted(
        pv_map.items(),
        key=lambda x: x[1],
        reverse=True
    )

    result = []

    for pv, score in sorted_lines:
        san = pv_to_san(board, list(pv))
        result.append({
            "score": score,
            "line": " ".join(san)
        })

    return result

if __name__ == "__main__":
    engine_open()
    engine_close()
    