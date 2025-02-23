from __future__ import annotations 
import asyncio
# [m for m in g.mainline_moves()]
import chess
import chess.pgn
import chess.polyglot
from chess.engine import Cp, Mate, MateGiven
import random
from Board import GameState
from UCIEngines import engine
from typing import Optional,List,Dict,Tuple,Dict
from LearningBase import LearningBase, learningBases
from datetime import datetime, timedelta, date
import csv



book:Optional[chess.polyglot.MemoryMappedReader] = chess.polyglot.MemoryMappedReader("./books/Perfect2021.bin")


def close():
    book.close()


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
            board:chess.Board current position
            learningBase: learning base to update
        Returns: 
            True if response was right

    """    
    moveMade:Optional[chess.Move] = board.pop()
    zobrist:Optional[int] = chess.polyglot.zobrist_hash(board)
    if zobrist not in learningBase.positions:
        return False
    # {zobrist,skip,fen,eco,lastTry,firstTry,ok,move,moves,successful,ntry,white,black,date}
    position = learningBase.positions[zobrist]
    res:Optional[bool] = LearningBase.updatePositionStats(position, moveMade, board, datetime.now().date())

    learningBase.save()
    board.push(moveMade)  # redo the move
    return res


def getRandomPositions(learningBase:LearningBase, filter=None):
    """
        Gets a randomized filtered subset of the given learning base
        Args:
            leaningBase: the database of positions
            filter: an object with the fields to match
        Returns: 
            List of positions
    """
    l = []
    for row in learningBase.positions.values():
        if filter is not None:
            if filter["eco"] is not None and row["eco"]!=filter["eco"].upper():
                continue
            if filter["color"] is not None:
                colorToMove = row["fen"].split(" ")[1]
                if colorToMove != filter["color"]:
                    continue

        if row["skip"] == "S":
            continue
        l.append(row)
    random.shuffle(l)
    return l





def isInBook(board:chess.Board)->bool:
    """
        Check if a board position is in current book
        Returns 
            True if board is in book
    """
    m = book.get(board, minimum_weight=0)
    if m is None:
        return False
    return True


nAdditions = 0

def evaluatePosition(board:chess.Board, ponderTime=3):
    """
        Gives an evaluation of the given position
        Returns:
            Number
    """
    # engine = chess.engine.SimpleEngine.popen_uci(r"D:\progetti\python\chess\engines\stockfish-17-avx2.exe")
    res = engine.analyse(board, chess.engine.Limit(time=ponderTime))
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
        board = chess.Board(pos["fen"])
        res = engine.analyse(board, chess.engine.Limit(time=3), info=chess.engine.INFO_PV)
        goodMove = board.uci(res["pv"][0])
        if goodMove == pos["ok"]:
            continue
        print(res)
        print(f"Position {pos['fen']}: move {pos['ok']} recalculated to {goodMove}")
        pos['ok'] = goodMove
    
    learningBase.save()

    # engine.close()

def assume_good_move(game:chess.pgn.Game, board:chess.Board,  learningBase:LearningBase):
    """
        Analyze last move made in a game
    """
    moveMade:Optional[chess.Move] = board.pop()  
    zobrist:Optional[int] = chess.polyglot.zobrist_hash(board)        
    goodMove = moveMade # the move choosen by the engine

    learningBase.updatePosition(moveMade, goodMove, game,board)
    
    board.push(moveMade) # restores the move
    
def updatePosition(game:chess.pgn.Game, board:chess.Board,  learningBase:LearningBase):
    """
        Analyze last move made in a game
    """
    moveMade:Optional[chess.Move] = board.pop()  
    zobrist:Optional[int] = chess.polyglot.zobrist_hash(board)    

    res = engine.analyse(board, chess.engine.Limit(time=0.4), info=chess.engine.INFO_PV)
    goodMove = res["pv"][0] # the move choosen by the engine

    learningBase.updatePosition(moveMade, goodMove, game,board)
    
    board.push(moveMade) # restores the move
    
    
   


def analyzePgn(pgnFileName:str, learningBase:LearningBase):    
    pg = PgnAnalyzer("hires", pgnFileName, learningBase)
    pg.analyzeDataBase()
    


class PgnAnalyzer:
    '''
        Analyze games of  a player, using and updating a specified learningBase, that contains positions found
    '''

    def __init__(self, playerName:str, filename:str, learningBase:LearningBase):
        '''
            Args:
            playerName:
        '''
        self.pgn = open(filename, encoding='utf-8')
        self.colorToPlay = "White"
        self.player = playerName
        self.positions = {}
        self.movesToAnalyse = learningBase.movesToAnalyse
        self.engine = None
        self.blunderValue = learningBase.blunderValue
        self.ponderTime = learningBase.ponderTime
        self.learningBase = learningBase
        pass


    def analyzeDataBase(self):
        while True:
            game, colorToAnalyze = self.loadNextGame()
            if game is None:
                break
            self.analyzeGame(game, colorToAnalyze)
            
            

        self.pgn.close()
        self.learningBase.save()

    def loadNextGame(self)->Tuple[chess.pgn.Game,bool]:
        while True:
            game = chess.pgn.read_game(self.pgn)
            if game is None:
                return None, None
            if game.headers["White"] == self.player:
                return game, True
            if game.headers["Black"] == self.player:
                return game, False

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

        for node in game.mainline():
            move:Optional[chess.Move] = node.move
            nmoves += 1

            if nmoves > self.movesToAnalyse:
                return None  #truncate analysis, nothing found

            board.push(move)

            eval = node.eval() # book could contain an evaluation for some reason
            if board.turn != colorToAnalyze and eval is not None:  # this refers to previous move!!!
                if eval < (prevScore - self.blunderValue):
                    updatePosition(game, board, self.learningBase)
                    return board  # score has dropped more than the threeshold, the stats are to be reevaluated

            if self.learningBase.useBook:
                # check book annotations
                if chess.pgn.NAG_MISTAKE in node.nags or \
                        chess.pgn.NAG_BLUNDER in node.nags or \
                        chess.pgn.NAG_DUBIOUS_MOVE in node.nags:
                    updatePosition(game, board, self.learningBase)
                    return board

            if board.turn == colorToAnalyze:
                continue

            if self.learningBase.useBook and isInBook(board):
                # book position, no need to analyze, but we update the stats
                assume_good_move(game, board, self.learningBase)
                continue

            zobrist = chess.polyglot.zobrist_hash(board)
            
            #Evaluate score after made move
            try:
                infoAfter = engine.analyse(board, chess.engine.Limit(time=self.ponderTime))
            except:
                return None

            pvsAfter = infoAfter["score"].pov(colorToAnalyze)
            if pvsAfter.is_mate():
                if pvsAfter < Cp(0):  # will get mated
                    updatePosition(game, board, self.learningBase)
                    return board
                return None  # will give mate
            currScore = pvsAfter.score()

            if currScore < (prevScore - self.blunderValue):
                updatePosition(game, board, self.learningBase) #blunder made
                return board

            if zobrist in self.learningBase.positions:
                # updates also if not a blunder, then go on
                updatePosition(game, board, self.learningBase)
                 
            prevScore = currScore




if __name__ == "__main__":
    # checkGameOpenings()
    print(f"Start analyzing")
    analyzePgn("all_pgn.pgn", learningBases["openings"])
    close()
    print(f"Analyzing Done")
