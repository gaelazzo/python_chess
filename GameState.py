"""
Stores current state of game
Determines valid moves
Keeps a move log
"""
from __future__ import annotations 
from re import S
from typing import Optional,List
import chess 
from chess.pgn import ChildNode, Game
import chess.polyglot
import random
import pyttsx3


class Voce:
    def __init__(self,lang_prefix="en"):
        self.engine = pyttsx3.init()
        voices = self.engine.getProperty('voices')
        for i, voice in enumerate(voices):
            print(f"[{i}] ID: {voice.id}")
            print(f"    Name: {voice.name}")
            print(f"    Lang: {voice.languages}")
            print(f"    Gender (in name?): {voice.name.lower()}")
            print()

        self.engine.setProperty('rate', 160)  # velocità di lettura
        self.engine.setProperty('volume', 1.0)  # volume

        # Seleziona voce con lingua desiderata
        for voice in self.engine.getProperty('voices'):
            lang = voice.languages[0].decode('utf-8') if isinstance(voice.languages[0], bytes) else voice.languages[0]
            if lang_prefix in lang.lower():
                self.engine.setProperty('voice', voice.id)
                break

    def leggi(self, testo: str):
        testo = testo.replace("0-0-0","long castle").replace("0-0","castle")
        self.engine.say(testo)
        self.engine.runAndWait()


voce = Voce()

class GameState:

     


    def __init__(self):
        # first char is the color, second char the piece, -- is empty
        self.pgn = Game()        
        self.moveLog:List[Move] = []
        self.header = []
        self.evaluation:Optional[float] = None
        self.node = self.pgn
        

    def setPgn(self, pgn: chess.pgn.Game):
        """
        Sets the PGN game
        """
        self.pgn = pgn
        
        self.node = pgn        
        self.moveLog = []        
        self.evaluation = None

        self.header = []
        for key, value in pgn.headers.items():
            if key in ['Date','White','Black','Result']:
                self.header.append(key)
                self.header.append(value)
        # Rebuild the move log from the PGN
        # self.goToLastMove()

    def leggiCommentoCorrente(self):
        if self.node and self.node.comment:            
            voce.leggi(self.node.comment)
    
    def doNextMainMove(self)->bool:
        '''
            do next main move
            returns:
                true of there was some move to do
        
        '''
        newNode = self.node.next()
        if newNode is None:
            return False        
        self.makeChessMove(newNode.move)
        return True

	  
    def is_end(self):
        # Checks if this node is the last node in the current variation.
        return True if self.node is None else self.node.is_end()

    def checkNextMove(self, move:chess.Move)->bool:
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

          return move == newNode.move

    def getPgn(self)->chess.pgn.Game:
        """
        Returns a PGN game 
        """
        header = self.getHeader()
        # Set header, se disponibili
        if header:
            headers = dict(zip(header[::2], header[1::2]))
            for key, value in headers.items():
                self.pgn.headers[key] = value
        return self.pgn
        

    def setHeader(self, header):
        self.header = header

    def setEvaluation(self, evaluation:float):
        '''
        sets the evaluation associated to current position
        '''
        self.evaluation = evaluation

    def getEvaluation(self)->Optional[float]:
        '''
        gets the evaluation associated to current position
        '''
        # assert(self.evaluation is not None)
        return self.evaluation

    def getHeader(self):
        return self.header

    
    def setFen(self, fen:str):
        '''
            Sets the board as stated by the fen str, resetting move log
        '''
        self.pgn = chess.pgn.Game()
        self.pgn.headers["FEN"] = fen
        self.pgn.setup(fen)
        self.pgn.variations = []  # rimuove tutte le mosse precedenti
        self.node = self.pgn
        self.moveLog = []



    def _pgnMakeMove(self, move:Move)->bool:
       '''
        Make a move in the current pgn game
        Args:
             move:Move   move to make
        '''
       if self.node is None:
         return False
     
       # Verifica se la mossa è già presente tra le variazioni
       for idx, child in enumerate(self.node.variations):
            existing_move = child.move
            if existing_move == move:
                self.node = child
                self.leggiCommentoCorrente()
                return False

       # Altrimenti: crea nuova variazione
       new_node = self.node.add_variation(move)  # crea e aggiunge
       self.node = new_node
       return True
    
    def getNextMoves(self)->List[chess.Move]:
        '''
            Get the next moves in the current variation
            returns:
                a list of moves
        '''
        if self.node is None:
            return []
        nextNodes:List[ChildNode] = self.node.variations
        return [n.move for n in nextNodes]


    

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

         node = self.node.variations[idx]
         if node.comment:
             print(node.comment)

         move:Move = Move.fromChessMove(node.move, self)

         self.makeMove(move)

         return move

    
     
    def goToLastMove(self)->bool:
         """
         Go to the last move in the current game
         """
         if self.node is None:
             return False
    
         while self.node.variations:
             node = self.node.variations[0]  # Segui solo la linea principale
             move = Move.fromChessMove(node.move, self)
             self.makeMove(move)
             

         return True

    def getNextMainMove(self):
         '''
             Get the next move in the main line
         '''
         if self.node is None:
             return None
         nextNode:ChildNode = self.node.next()
         return None if nextNode is None else nextNode.move

    def makeChessMove(self, move: chess.Move):
        """
        Takes a chess move and executes it. Does not work for special moves
        param move: chess.Move
        return:
        """
        if move is None:
            return
        self.makeMove(Move.fromChessMove(move, self))


    def makeMove(self, move:Move):
        """
        Takes a move and executes it. Does not work for special moves
        param move: Move
        return:
        """
        self._pgnMakeMove(move.move)
        #self.pgn.board.push(move.move)        
        self.moveLog.append(move)
        self.evaluation = None

    def undoMove(self):
        '''
        Rethreat last move
        '''
        if len(self.moveLog) == 0:
            return

        # update pgn node
        self.node = self.node.parent if self.node is not None else None

        #self.board.pop()
        del self.moveLog[-1]
        self.evaluation = None
        

    def whiteToMove(self)->chess.Color:
        return self.node.board().turn

    def colorToMove(self)->str:
        return "w" if self.node.board().turn else "b"

    def colorAt(self, row:int, col:int)->str:
        """
         Color of the piece in a board position
        :param row:int
        :param col:int
        return:string
            w or b

        """
        p = self.node.board().piece_at((7-row)*8+col)
        if p is None:
            return "-"
        if p.color:
            return "w"
        return "b"

    def getValidMoves(self)->List[Move]:
        return [Move.fromChessMove(m, self) for m in self.node.board().legal_moves]


    def stdValidMoves(self)->List[Move]:
        dest = []
        for m in self.node.board().legal_moves:
            # if chess.square_rank(m.from_square) != fromRow:
            #     continue
            # if chess.square_file(m.from_square) != fromCol:
            #     continue
            mm = Move.fromChessMove(m, self)
            if m.promotion is not None:
                mm.promoteToPiece(m.promotion)
            dest.append(mm)

        return dest


    def piece_at(self, r:int, c:int)->str:
        '''        
        Piece in a board position

        Args:
            r: piece row
            c: piece column

        Returns:
            piece code in a format like --, wB, bN etc
        '''

        moved = self.node.board().piece_at((7-r)*8+c)
        if moved is None:
            return "--"

        movedColor  = moved.symbol().upper()
        color = self.colorAt(r, c)
        return color + movedColor

    def inCheck(self)->bool:
       return self.node.board().is_check()

    def checkMate(self)->bool:
        return self.node.board().is_checkmate()

    def staleMate(self)->bool:
        return self.node.board().is_stalemate()

class Move:
    ranksToRows = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}
    rowsToRanks = {v: k for k, v in ranksToRows.items()}
    filesToCols = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7}
    colsToFiles = {v: k for k, v in filesToCols.items()}


    @classmethod
    def fromChessMove(cls, m:chess.Move, game:GameState)->Move:
        if m is None:
            return None

        move= cls((7-chess.square_rank(m.from_square),chess.square_file(m.from_square)),
                    (7 - chess.square_rank(m.to_square), chess.square_file(m.to_square)),
                    game
                    )
        if m.promotion is not None:
            move.promoteToPiece(m.promotion)

        return move

    def __init__(self, startSq:tuple[int,int], stopSq:tuple[int,int], game:GameState):
        '''
        Creates a chess move from a user move made on board
        '''
        self.startRow = startSq[0]
        self.startCol = startSq[1]
        self.stopRow = stopSq[0]
        self.stopCol = stopSq[1]

        self.uci:str = self.getRankFile(startSq[0], startSq[1]) + \
              self.getRankFile(stopSq[0], stopSq[1])
        self.move:chess.Move = chess.Move.from_uci(self.uci)
        
        self.pieceMoved:str = game.piece_at(self.startRow, self.startCol)
        
        self.pieceCaptured:str = game.piece_at(self.stopRow, self.stopCol)
        try:
            self.prettyPrint = game.board.san(self.move)
        except:
            self.prettyPrint = self.move.uci()

        self.enPassant = game.node.board().is_en_passant(self.move)


    def promoteToPiece(self, p:chess.PieceType)->chess.Move:
        move = self.move.uci()
        if not move.endswith(chess.piece_symbol(p)):
            move += chess.piece_symbol(p)
        self.move = chess.Move.from_uci(move)
        return self.move

    def getChessNotation(self)->str:
        #uci move, example a7a8 or a7a8q
        return self.move.uci()

    def prettyChessNotation(self)->str:
        return self.prettyPrint


    def getRankFile(self, r:int, c:int):
        '''
        gives a string representation of a board square
        '''
        return self.colsToFiles[c] + self.rowsToRanks[r]

    def __eq__(self, other):
        if not isinstance(other, Move):
            return False
        return self.getChessNotation() == other.getChessNotation()
