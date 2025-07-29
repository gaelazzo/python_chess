from __future__ import annotations 
from typing import Optional,List
import chess
import os
from chess.pgn import ChildNode, Game,read_game,read_headers,FileExporter
import chess.polyglot
from chess.engine import Cp, Mate, MateGiven
from GameState import GameState, Move
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
        self.fName:str = os.path.join(BASE_PATH, "pgn", filename)+".pgn"
        self.games:Optional[List[Game]] = []
        if os.path.exists(self.fName):
            pgn = open(self.fName, encoding='utf-8')
            while True:
                game:chess.pgn.Game = read_game(pgn)
                if game is None:
                    break
                self.games.append(game)

            pgn.close()

        # first char is the color, second char the piece, -- is empty

   

    def load_game(self, gs:GameState, N: int) -> bool:
        """
        Load the game at index N from the list of games
        """
        if N < 0 or N >= len(self.games):
            return False
        game = self.games[N]
        
        gs.setPgn(game)      
        return True

    def chooseRandomGame(self)->Game:
        if self.isEmpty():
            return None
        return random.choice(self.games)


    def save_game(self, gs:GameState,  N: Optional[int] = None)->int:
        new_game  = gs.getPgn()
        
        if N is None:
            self.games.append(new_game)
            N = len(self.games) - 1
        else:
            if N < len(self.games):
                self.games[N] = new_game
            else:
                # Aggiungi partite vuote fino a N, poi inserisci la nuova
                while len(self.games) < N:
                    self.games.append(chess.pgn.Game())  # placeholder vuoto
                self.games.append(new_game)

            # Rewrite all games
            with open(self.fName, "w", encoding="utf-8") as f:
                for game in self.games:
                    exporter = FileExporter(f)
                    game.accept(exporter)

        return N