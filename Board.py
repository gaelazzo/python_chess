"""
Stores current state of game
Determines valid moves
Keeps a move log
"""
from __future__ import annotations 
from typing import Optional,List
import chess




class GameState:

    def __init__(self):
        # first char is the color, second char the piece, -- is empty
        self.board:Optional[chess.Board] = chess.Board()
        self.moveLog:Optional[List[Move]] = []
        self.header = []
        self.evaluation = None

    def setHeader(self, header):
        self.header = header

    def setEvaluation(self, evaluation:float):
        '''
        sets the evaluation associated to current position
        '''
        self.evaluation = evaluation

    def getEvaluation(self)->float:
        '''
        gets the evaluation associated to current position
        '''
        return self.evaluation

    def getHeader(self):
        return self.header

    
    def setFen(self, fen:str):
        '''
            Sets the board as stated by the fen str, resetting move log
        '''
        self.moveLog = []
        self.board = chess.Board(fen)

    def makeMove(self, move:Move):
        """
        Takes a move and executes it. Does not work for special moves
        param move: Move
        return:
        """
        if hasattr(move, "move"):
            self.board.push(move.move)
        else:
            self.board.push(move)
        self.moveLog.append(move)

    def undoMove(self):
        '''
        Rethreat last move
        '''
        self.board.pop()
        if len(self.moveLog) > 0:
            del self.moveLog[-1]

    def whiteToMove(self)->chess.Color:
        return self.board.turn

    def colorToMove(self)->str:
        return "w" if self.board.turn else "b"

    def colorAt(self, row:int, col:int)->str:
        """
         Color of the piece in a board position
        :param row:int
        :param col:int
        return:string
            w or b

        """
        p = self.board.piece_at((7-row)*8+col)
        if p is None:
            return "-"
        if p.color:
            return "w"
        return "b"

    def getValidMoves(self)->List[Move]:
        return [m for m in self.board.legal_moves]


    def stdValidMoves(self)->List[Move]:
        dest = []
        for m in self.board.legal_moves:
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

        moved = self.board.piece_at((7-r)*8+c)
        if moved is None:
            return "--"

        moved = moved.symbol().upper()
        color = self.colorAt(r, c)
        return color + moved

    def inCheck(self)->bool:
       return self.board.is_check()

    def checkMate(self)->bool:
        return self.board.is_checkmate()

    def staleMate(self)->bool:
        return self.board.is_stalemate()

class Move:
    ranksToRows = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}
    rowsToRanks = {v: k for k, v in ranksToRows.items()}
    filesToCols = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7}
    colsToFiles = {v: k for k, v in filesToCols.items()}


    @classmethod
    def fromChessMove(cls, m:chess.Move,board:chess.Board)->Move:
        return cls([7-chess.square_rank(m.from_square),chess.square_file(m.from_square)],
                    [7 - chess.square_rank(m.to_square), chess.square_file(m.to_square)],
                    board
                    )

    def __init__(self, startSq, stopSq, board):
        '''
        Creates a chess move from a user move made on board
        '''
        self.startRow = startSq[0]
        self.startCol = startSq[1]
        self.stopRow = stopSq[0]
        self.stopCol = stopSq[1]

        self.uci:Optional[str] = self.getRankFile(startSq[0], startSq[1]) + \
              self.getRankFile(stopSq[0], stopSq[1])
        self.move:Optional[chess.Move] = chess.Move.from_uci(self.uci)
        self.board:Optional[chess.Board] = board
        self.pieceMoved = board.piece_at(self.startRow, self.startCol)
        self.pieceCaptured = board.piece_at(self.stopRow, self.stopCol)
        self.prettyPrint = self.board.board.san(self.move)
        self.enPassant = self.board.board.is_en_passant(self.move)


    def promoteToPiece(self, p:chess.PieceType)->chess.Move:
        self.move = chess.Move.from_uci(self.move.uci()+chess.piece_symbol(p))
        return self.move

    def getChessNotation(self)->str:
        #uci move, example a7a8 or a7a8q
        return self.move.uci()

    def prettyChessNotation(self)->str:
        return self.prettyPrint


    def getRankFile(self, r, c):
        '''
        gives a string represantition of a board square
        '''
        return self.colsToFiles[c] + self.rowsToRanks[r]

    def __eq__(self, other):
        if not isinstance(other, Move):
            return False
        return self.getChessNotation() == other.getChessNotation()
