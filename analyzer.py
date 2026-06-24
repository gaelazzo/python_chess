from __future__ import annotations 
from argparse import OPTIONAL
import asyncio
from pickle import NONE
from xmlrpc.client import MAXINT
# [m for m in g.mainline_moves()]
import chess
import chess.pgn
import chess.polyglot
from chess.engine import Cp, Mate, MateGiven
import random
from UCIEngines import  engine_close, engine_open
from typing import Optional,List,Dict,Tuple,Dict
from LearningBase import LearnPosition, LearningBase, learningBases, DATA_FOLDER
from datetime import datetime, timedelta, date
import csv
import Quiz
import os
from config import config
import book
import UCIEngines
import json_helper


import os
import sys

import pgngamelist

folder = DATA_FOLDER
# zobrist,skip,fen,eco,lastTry,firstTry,ok,move,moves,ntry,successful



def updateInfoStats(board:chess.Board, learningBase:LearningBase):
    """ 
        Updates the learning base with the given Board, in particular:
            ntry = n. of attempts
            lastTry = current time    
            successful = n. of correct responses
            firstTry = current time if this is first attempt
            skip = S if answer was successful 5 times in a row
            serie = current positive or negative serie
        Args:
            board:chess.Board current position, AFTER move has been played
            learningBase: learning base to update
        Returns: 
            True if response was right

    """    
    moveMade:chess.Move = board.pop()
    zobrist:int = chess.polyglot.zobrist_hash(board)
    if zobrist not in learningBase.positions:
        return False
    # {zobrist,skip,fen,eco,lastTry,firstTry,ok,move,moves,successful,ntry,white,black,date}
    position = learningBase.positions[zobrist]
    res:bool = learningBase.updatePositionStats(position, moveMade.uci(), datetime.now().date())

    learningBase.save()
    board.push(moveMade)  # redo the move
    return res


def getPositions(learningBase:LearningBase, filter=None, order:str="priority")->List [LearnPosition]:
    """
        Returns a filtered list of positions from the learning base.

        `order`:
          - "priority" (default): the highest (ntry-successful, severity) ends up
            at the BOTTOM of the list, so that the consumer calling pop() trains
            the most recurring/serious positions first. Random tiebreak among equal priorities.
          - "random": only random.shuffle, no ordering. Suitable for freshly
            created bases where positions have the same counters and for variety.

        Args:
            learningBase: the database of positions
            filter: an object with the fields to match (eco, color)
            order: "priority" | "random"
        Returns:
            List of positions
    """
    l:List [LearnPosition] = []
    for row in learningBase.positions.values():
        if filter is not None:
            if filter["eco"] is not None and row.eco!=filter["eco"].upper():
                continue
            if filter["color"] is not None:
                colorToMove = row.fen.split(" ")[1]
                if colorToMove != filter["color"]:
                    continue

        if row.skip:
            continue
        l.append(row)
    random.shuffle(l)
    if order == "priority":
        # stable sort: the previous shuffle acts as a tiebreak among equal priorities.
        l.sort(key=lambda pos: (pos.ntry - pos.successful, pos.severity))
    return l





nAdditions = 0

def evaluatePosition(board:chess.Board, ponderTime=3):
    """
        Gives an evaluation of the given position
        Returns:
            Number
    """
    # engine = chess.engine.SimpleEngine.popen_uci(r"D:\progetti\python\chess\engines\stockfish-17-avx2.exe")
    res = UCIEngines.engine.analyse(board, chess.engine.Limit(time=ponderTime))
    # engine.close()
    return res["score"].relative

def recalcLearningBases():
    for learn in learningBases.values():
        recalcLearned(learn)


# zobrist;fen;eco;lastTry;firstTry;move;ok;bad;moves,ntry,successful,ntry,white,black,date
def recalcLearned(learningBase:LearningBase):
    """
    Evaluates the best move for each position in the learning base and saves learningBase
    """
    # engine = chess.engine.SimpleEngine.popen_uci(r"D:\progetti\python\chess\engines\stockfish-17-avx2.exe")
    for pos in learningBase.positions.values():
        board = chess.Board(pos.fen)
        res = UCIEngines.engine.analyse(board, chess.engine.Limit(time=3), info=chess.engine.INFO_PV)
        goodMove = board.uci(res["pv"][0])
        if goodMove == pos.ok:
            continue
        print(res)
        print(f"Position {pos.fen}: move {pos.ok} recalculated to {goodMove}")
        pos.ok = goodMove
    
    learningBase.save()

    # engine.close()

def assume_good_move(game:chess.pgn.Game, board:chess.Board,  learningBase:LearningBase):
    """
        Stores last response as a good try, even though it may not be the absolute best
        Args:
            game: the pgn game being played
            board: board position AFTER the move was made
            learningBase: the learning base to update            
    """
    moveMade:chess.Move = board.pop()  
    goodMove = moveMade # wa assume is a good move

    learningBase.updatePosition(moveMade.uci(), goodMove.uci(), game,board)    
    board.push(moveMade) # restores the move
    
def updatePosition(game:chess.pgn.Game, board:chess.Board,  learningBase:LearningBase, goodMove:str, severity:int=0):
    """
        Analyze last move made in a game
        Args:
            game: the pgn game being played
            board: board position AFTER the move was made
            learningBase: the learning base to update
            goodMove: the right move to do
            severity: evaluation drop (cp) of the mistake (in practice used for priority)
        Returns:
            updates the stats
    """
    moveMade:chess.Move = board.pop()

    # res = engine.analyse(board, chess.engine.Limit(time=learningBase.ponderTime), info=chess.engine.INFO_PV)
    # goodMove = res["pv"][0] # the move choosen by the engine

    learningBase.updatePosition(moveMade.uci(), goodMove, game, board, severity=severity)

    board.push(moveMade) # restores the move
    
   
def analyzePgn(pgnFileName:str, playerName:str, learningBase:LearningBase, start_from:int=0, skip_player:Optional[str]=None, progress=None, eco:Optional[str]=None, use_analyzed_range:bool=False) -> bool:
    """`eco` (e.g. "B01"): if not None, filters to only the games with that ECO header.
    `use_analyzed_range`: when True, skip games whose date is already inside the
    base's per-nick analyzed window and grow that window with the games processed
    (Study Advisor re-run dedup). Off by default -> other callers are unchanged.
    Returns True if the user interrupted the analysis (see `progress`), so a
    caller looping over focuses/nicks can stop the whole pipeline too."""
    pg = PgnAnalyzer(playerName, pgnFileName, learningBase, eco=eco, use_analyzed_range=use_analyzed_range)
    return pg.analyzeDataBase(start_from,skip_player, progress=progress)


def _same_player(header_name: Optional[str], player: Optional[str]) -> bool:
    """Case-insensitive player-name match: chess.com and lichess handles are
    case-insensitive, so the [White]/[Black] headers must be compared ignoring
    case (otherwise the Study Advisor ranking finds games the base build misses)."""
    return (header_name or "").lower() == (player or "").lower()


def _game_date(headers) -> Optional[date]:
    """Game date from the PGN headers (UTCDate preferred, then Date), or None.
    Both chess.com and lichess emit YYYY.MM.DD; '????.??.??' placeholders yield None."""
    for key in ("UTCDate", "Date"):
        raw = (headers.get(key) or "").strip()
        if raw and "?" not in raw:
            try:
                return datetime.strptime(raw, "%Y.%m.%d").date()
            except ValueError:
                continue
    return None


class PgnAnalyzer:
    '''
        Analyze games of  a player, using and updating a specified learningBase, that contains positions found
    '''

    def __init__(self, playerName:str, filename:str, learningBase:LearningBase, eco:Optional[str]=None, use_analyzed_range:bool=False):
        '''
            Args:
            playerName: the name of the player to analyze
            pgnfile: the name of the pgn file to analyze (with or without .pgn)
            learningBase: the learning base to update
            eco: if not None, filters to only the games with that ECO (case-insensitive)
            use_analyzed_range: skip games already inside the base's per-nick
                analyzed date window, and extend it with processed games
        '''
        # make_file_selector saves the filename without extension, but on disk the
        # PGN files have it -- we append .pgn if it is missing (mirroring PgnGameList,
        # openings.py, endgames.py).
        if not filename.lower().endswith(".pgn"):
            filename = filename + ".pgn"
        pathcomplete = os.path.join(pgngamelist.PGN_FOLDER, filename)
        self.pgn = open(pathcomplete, encoding='utf-8')
        self.player = playerName
        self.eco_filter = eco.upper() if eco else None
        self.use_analyzed_range = use_analyzed_range
        self.movesToAnalyze = learningBase.movesToAnalyze
        self.engine = None
        self.blunderValue = learningBase.blunderValue
        self.ponderTime = learningBase.ponderTime
        self.learningBase = learningBase
        # extract the file name without extension, it becomes the name of the lesson that will contain the pgn file
        pass

 
    def analyzeDataBase(self, start_from:int=0, skip_player:Optional[str]=None, progress=None) -> bool:
        """Returns True if interrupted by the user (the `progress` callback
        returned truthy). On interrupt the current game is finished and the base
        is saved before breaking, so nothing analyzed so far is lost."""
        n_games = 0
        if start_from>0:
            while n_games < start_from:
                game, colorToAnalyze = self.loadNextGame()                
                n_games+=1

        if skip_player is not None:
            while True:
                    game, colorToAnalyze = self.loadNextGame()      
                    assert (game is not None)          
                    n_games+=1
                    if _same_player(game.headers.get("White"), skip_player):
                        break
                    if _same_player(game.headers.get("Black"), skip_player):
                        break

        stopped = False
        while True:
            game, colorToAnalyze = self.loadNextGame()

            if game is None:
                break
            n_games +=1
            stop = bool(progress(n_games)) if progress is not None else False
            self.analyzeGame(game, colorToAnalyze)
            if self.use_analyzed_range and self.player is not None:
                gdate = _game_date(game.headers)
                if gdate is not None:
                    self.learningBase.extendAnalyzedRange(self.player, gdate)
            # Clean stop: the current game is fully analyzed and the range
            # extended above, so saving here loses nothing already processed.
            if stop:
                self.learningBase.save()
                print(f"{n_games} analyzed (stopped by user)")
                stopped = True
                break
            if n_games % 50 == 0:
                self.learningBase.save()
                print(f"{n_games} analyzed")


        self.pgn.close()
        self.learningBase.save()
        return stopped

    def loadNextGame(self)->Tuple[Optional[chess.pgn.Game],bool]:
        while True:
            game = chess.pgn.read_game(self.pgn)
            if game is None:
                return None, True
            # Optional ECO filter: skip games with an ECO different from the requested one.
            if self.eco_filter is not None:
                eco_h = (game.headers.get("ECO") or "").strip().upper()
                if eco_h != self.eco_filter:
                    continue
            if self.player is None:
                return game, True
            if _same_player(game.headers.get("White"), self.player):
                color = True
            elif _same_player(game.headers.get("Black"), self.player):
                color = False
            else:
                continue
            # Re-run dedup: skip games already inside the per-nick analyzed window
            # (inclusive), so a rebuild neither double-counts them nor revives their
            # "Learned" positions. Undated games fall through and are analyzed.
            if self.use_analyzed_range:
                gdate = _game_date(game.headers)
                if gdate is not None and self.learningBase.isInAnalyzedRange(self.player, gdate):
                    continue
            return game, color

    def getPositionEvaluation(self, board:chess.Board, colorSide:bool)->Tuple[int,Optional[str]]:
         if self.learningBase.useBook:
               # check game annotations                
               bookEntry = book.book.get(board); #, minimum_weight=0
               if bookEntry is not None: 
                        return 0, board.uci(bookEntry.move)

         res = UCIEngines.engine.analyse(board, chess.engine.Limit(time=self.ponderTime))
         pvsAfter = res["score"].pov(colorSide)
         if pvsAfter.is_mate():
                if pvsAfter < Cp(0):  # will get mated
                    return -1000, None
                return 1000, None
         else:
                pv_list = res.get("pv", [])
                best_move: Optional[chess.Move] = pv_list[0] if pv_list else None
                best_score  = pvsAfter.score()
                assert(best_score is not None)
                return best_score, board.uci(best_move) if best_move else None

    def esplora_rami(self, game: chess.pgn.Game, colorSide:bool)->List[LearnPosition]:
        """Explores all branches of a PGN game and collects the positions relevant to a specific color"""
        positions:List[LearnPosition] = []

        def esplora_nodo(nodo, board):
            if nodo.is_end():
                return

            for variation in nodo.variations:
                
                # Store only the positions of the specified color
                if board.turn == colorSide:
                    # The move to play is the next move of the current node (variation.move)
                    # The position "before" the move is the board before push, so we must pass the board "before" the move
                    # But now board is already updated with the move, so we do it like this:
                    moveMade =  variation.move.uci()  # The move to play
                    position = self.learningBase.addPosition(game, board, moveMade)
                    if position: # if it is new or needs updating
                        positions.append(position)

                board.push(variation.move)
                esplora_nodo(variation, board)
                board.pop()

        board = game.board()
        esplora_nodo(game, board)
        return positions
        
    def unrollGame(self, game: chess.pgn.Game, colorToAnalyze: bool) -> List[LearnPosition]:
        """
        Unrolls a game and adds all positions to the learning base
        Args:
            game: a game to unroll
            colorToAnalyze: True for white/ False for black
            learningBase: the learning base to update
        """
        return self.esplora_rami(game, colorToAnalyze)


    def unroll(self, colorToAnalyze:bool)->List[LearnPosition]:
        """
        Unrolls a pgn file and adds all positions to the learning base
        If the pgn contains more than one game, every game will be unrolled
        Args:
            colorToAnalyze: True for white/ False for black
        Returns:
            List of positions added
        """
        positions: List[LearnPosition] = []
        game = chess.pgn.read_game(self.pgn)
        while game is not None:
            positions.extend( self.unrollGame(game, colorToAnalyze))
            game = chess.pgn.read_game(self.pgn)
        
        self.learningBase.save()
        return positions


    def analyzeGame(self, game:chess.pgn.Game, colorToAnalyze:bool):
        """
        Analyze every move in a game until 
           a blunder or dubious move  is found in the book (if it is used in the current learning base)
        
        The assumption is that current learning base is a blunder database   

        Args:
            game: a game to analyze
            colorToAnalyze = True for white/ False for black
        Returns:
            the first blunder or dubious move found made by analyzed color
        """
        board: chess.Board = game.board()
        nmoves = 0
        prevScore = 0
        bestMove:Optional[str] = None

        for node in game.mainline():
            move: chess.Move = node.move
            moveStr :str = board.uci(move)
            
            nmoves += 1

            if nmoves > self.movesToAnalyze:
                return None  #truncate analysis, nothing found


            if board.turn != colorToAnalyze:  
                # if turn is the colorToAnalyze, then the move was made by the other one
                # so we don't care too much
                board.push(move)  # make the move on the board
                prevScore, bestMove = self.getPositionEvaluation(board, colorToAnalyze)
                continue            
            
            # we must evaluate the existing of the position before we make the move
            zobrist = chess.polyglot.zobrist_hash(board)
            position_exists = zobrist in self.learningBase.positions
            
            board.push(move)  # make the move on the board

            # this means that last move is from observed player
            # Consider annotations in the game file
            annotation = node.eval()

            
            if annotation is not None and bestMove is not None:  # this refers to previous move!!!
                if annotation.pov(colorToAnalyze) < (prevScore - self.blunderValue):
                    updatePosition(game, board, self.learningBase, bestMove, severity=self.blunderValue)
                    return board  # score has dropped more than the threeshold, the stats are to be reevaluated

            if len(node.nags)>0 and bestMove is not None:
                if chess.pgn.NAG_MISTAKE in node.nags or \
                            chess.pgn.NAG_BLUNDER in node.nags or \
                            chess.pgn.NAG_DUBIOUS_MOVE in node.nags:
                        updatePosition(game, board, self.learningBase, bestMove, severity=self.blunderValue)
                        return board


            evaluation, nextBestMove = self.getPositionEvaluation(board,colorToAnalyze)

            if evaluation < (prevScore - self.blunderValue) and bestMove is not None: # bestMove could be None if this is the start of a handicap Game
                updatePosition(game, board, self.learningBase, bestMove, severity=int(prevScore - evaluation))  # magnitude of the drop = severity
                return board
            
            prevScore = evaluation
            bestMove = nextBestMove

            

            # book position, no need to analyze, but we update the stats if in the past there have been a mistake
            if position_exists:
                assume_good_move(game, board, self.learningBase)
                continue



def unrollPgn(pgnFileName:str, learningBase:LearningBase, colorToAnalyze:bool):
    """
        Unrolls a pgn file and adds all positions to the learning base
        Args:
            pgnFileName: the name of the pgn file to unroll
            playerName: the name of the player to analyze
            learningBase: the learning base to update
    """
    pg = PgnAnalyzer("player", pgnFileName, learningBase)
    pg.unroll(colorToAnalyze) 
    pg.learningBase.save()
    Quiz.makeQuizzes_by_ECO(learningBase)


def unrollPgn_as_lesson(pgnFileName:str, learningBase:LearningBase, colorToAnalyze:bool):
    """
        Unrolls a pgn file and adds all positions to the learning base
        Args:
            pgnFileName: the name of the pgn file to unroll
            playerName: the name of the player to analyze
            learningBase: the learning base to update
    """
    lessonName, _ = os.path.splitext(pgnFileName)  
    fName = os.path.join(DATA_FOLDER, f"lessons_{learningBase.filename}.json")

    if os.path.exists(fName):
        oldQuizNames = json_helper.read_struct(fName)
        oldQuizNames = {int(k): v for k, v in oldQuizNames.items()}

        # 🔎 Check: if lessonName is already present → warn and stop
        if lessonName in oldQuizNames.values():
            print(f"[WARNING] Lesson '{lessonName}' already present, no action taken.")
            return
    else:
        oldQuizNames = {}

    pg = PgnAnalyzer("player", pgnFileName, learningBase)
    pg.unroll(colorToAnalyze) 
    pg.learningBase.save()
    Quiz.assign_unnamed_quizzes(oldQuizNames, learningBase, lessonName)
    

# skip 8600, all_pgn-pgn
if __name__ == "__main__":
    # checkGameOpenings()
    print(f"Start analyzing")
    book.open_book()
    engine_open()
    # analyzePgn("all_pgn.pgn","gaelazzo", learningBases["openings"], skip_player='FAAILIX')
    learningBases["blunders"].save()

    book.close_book()
    engine_close()
    print(f"Analyzing Done")
