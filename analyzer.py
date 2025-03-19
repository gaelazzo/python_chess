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
from Board import GameState
from UCIEngines import engine, engine_close
from typing import Optional,List,Dict,Tuple,Dict
from LearningBase import LearnPosition, LearningBase, learningBases
from datetime import datetime, timedelta, date
import csv


print("loading book...")
book:chess.polyglot.MemoryMappedReader = chess.polyglot.MemoryMappedReader("./books/Perfect2021.bin")
print("book loaded")

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


def getRandomPositions(learningBase:LearningBase, filter=None)->List [LearnPosition]:
    """
        Gets a randomized filtered subset of the given learning base
        Args:
            leaningBase: the database of positions
            filter: an object with the fields to match
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
        board = chess.Board(pos.fen)
        res = engine.analyse(board, chess.engine.Limit(time=3), info=chess.engine.INFO_PV)
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
    
def updatePosition(game:chess.pgn.Game, board:chess.Board,  learningBase:LearningBase, goodMove:str):
    """
        Analyze last move made in a game
        Args:
            game: the pgn game being played
            board: board position AFTER the move was made
            learningBase: the learning base to update
            goodMove: the right move to do
        Returns:
            updates the stats
    """
    moveMade:chess.Move = board.pop()  

    # res = engine.analyse(board, chess.engine.Limit(time=learningBase.ponderTime), info=chess.engine.INFO_PV)
    # goodMove = res["pv"][0] # the move choosen by the engine

    learningBase.updatePosition(moveMade.uci(), goodMove, game, board)
    
    board.push(moveMade) # restores the move
    
   
def analyzePgn(pgnFileName:str, playerName:str, learningBase:LearningBase, start_from:int=0, skip_player:Optional[str]=None):    
    pg = PgnAnalyzer(playerName, pgnFileName, learningBase)
    pg.analyzeDataBase(start_from,skip_player)
    


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
        self.movesToAnalyze = learningBase.movesToAnalyze
        self.engine = None
        self.blunderValue = learningBase.blunderValue
        self.ponderTime = learningBase.ponderTime
        self.learningBase = learningBase
        pass

 
    def analyzeDataBase(self, start_from:int=0, skip_player:Optional[str]=None):
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
                    if game.headers["White"]== skip_player:
                        break
                    if game.headers["Black"]== skip_player:
                        break

        while True:
            game, colorToAnalyze = self.loadNextGame()

            if game is None:
                break
            n_games +=1            
            self.analyzeGame(game, colorToAnalyze)
            if n_games % 50 == 0:
                self.learningBase.save()
                print(f"{n_games} analyzed")
            

        self.pgn.close()
        self.learningBase.save()

    def loadNextGame(self)->Tuple[Optional[chess.pgn.Game],bool]:
        while True:
            game = chess.pgn.read_game(self.pgn)
            if game is None:
                return None, True
            if game.headers["White"] == self.player:
                return game, True
            if game.headers["Black"] == self.player:
                return game, False

    def getPositionEvaluation(self, board:chess.Board, colorSide:bool)->Tuple[int,Optional[str]]:
         if self.learningBase.useBook:
               # check game annotations                
               bookEntry = book.get(board, minimum_weight=0);
               if bookEntry is not None: 
                        return 0, board.uci(bookEntry.move)

         res = engine.analyse(board, chess.engine.Limit(time=self.ponderTime))
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
                    updatePosition(game, board, self.learningBase, bestMove)
                    return board  # score has dropped more than the threeshold, the stats are to be reevaluated

            if len(node.nags)>0 and bestMove is not None:
                if chess.pgn.NAG_MISTAKE in node.nags or \
                            chess.pgn.NAG_BLUNDER in node.nags or \
                            chess.pgn.NAG_DUBIOUS_MOVE in node.nags:
                        updatePosition(game, board, self.learningBase, bestMove)
                        return board

           
            evaluation, nextBestMove = self.getPositionEvaluation(board,colorToAnalyze)

            if evaluation < (prevScore - self.blunderValue) and bestMove is not None: # bestMove could be None if this is the start of a handicap Game
                updatePosition(game, board, self.learningBase, bestMove)  # score has dropped more than the threeshold,
                return board
            
            prevScore = evaluation
            bestMove = nextBestMove

            

            # book position, no need to analyze, but we update the stats if in the past there have been a mistake
            if position_exists:
                assume_good_move(game, board, self.learningBase)
                continue

# skip 8600, all_pgn-pgn
if __name__ == "__main__":
    # checkGameOpenings()
    print(f"Start analyzing")
    # analyzePgn("all_pgn.pgn","gaelazzo", learningBases["openings"], skip_player='FAAILIX')
    close()
    engine_close()
    print(f"Analyzing Done")
