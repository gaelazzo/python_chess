from __future__ import annotations 
from typing import Optional,List
import chess
import os
from chess.pgn import ChildNode, Game,read_game,read_headers
import chess.polyglot
from chess.engine import Cp, Mate, MateGiven
from Board import GameState, Move
import io
import sys
import random

def get_base_path():
    if getattr(sys, 'frozen', False):  # Se è un eseguibile PyInstaller
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
PGN_FOLDER = os.path.join(BASE_PATH, "pgn")






class PgnGameList:

    def isEmpty(self):
        return len(self.games) == 0

    def __init__(self, filename):
        fName = os.path.join(BASE_PATH, "pgn", filename)+".pgn"
        self.games:Optional[List[Game]] = []
        pgn = open(fName, encoding='utf-8')
        while True:
            game:chess.pgn.Game = read_game(pgn)
            if game is None:
                break
            self.games.append(game)

        pgn.close()

        # first char is the color, second char the piece, -- is empty
        self.gs:Optional[GameState] = GameState()
        self.game:Optional[chess.pgn.Game] = None
        self.node = None

    def undoMove(self):
        self.gs.undoMove()
        self.node = self.node.parent if self.node is not None else None


    def makeNextMove(self):
        '''
            Make a random move from the variations stored in the game
        '''
        if self.node is None:
            return None
        if self.is_end():
            return None
        nVariations = len(self.node.variations)
        if nVariations == 0:
            return None
        idx = random.randint(0, nVariations-1)

        self.node = self.node.variations[idx]
        if self.node.comment:
            print(self.node.comment)

        result:Move = Move.fromChessMove(self.node.move, self.gs)

        self.gs.makeMove(result)

        return result

    def getNextMainMove(self):
        '''
            Get the next move in the main line
        '''
        if self.node is None:
            return None
        nextNode:ChildNode = self.node.next()
        return None if nextNode is None else nextNode.move


    def chooseRandomGame(self):
        if self.isEmpty():
            return False
        self.game = random.choice(self.games)
        self.node:Game = self.game
        self.gs:GameState = GameState()
        return True


    def is_end(self):
        return True if self.game is None else self.game.is_end()

    def checkNextMove(self, move:Move)->bool:
        """
        Check if the input move is the next main move in the current variation

        params:
            move:Move   move to check

         Returns:
             boolean
            
        """
        newNode:Optional[ChildNode] = self.node.next()
        if newNode is None:
            return False

        return self.gs.board.san(move) == newNode.san()

    def doNextMainMove(self)->bool:
        '''
            do next main move
            returns:
                true of there was some move to do
        
        '''
        newNode = self.node.next()
        if newNode is None:
            return False
        self.node = newNode
        self.gs.makeMove(Move.fromChessMove(newNode.move, self.gs))
        return True

