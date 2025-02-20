"""
Stores current state of game
Determines valid moves
Keeps a move log
"""
from __future__ import annotations 
from typing import Optional
import chess




class GameState:

    def __init__(self):
        # first char is the color, second char the piece, -- is empty
        self.board = chess.Board()
        self.moveLog = []
        self.header = []
        self.evaluation = None

    def setHeader(self, header):
        self.header = header

    def setEvaluation(self, evaluation):
        self.evaluation = evaluation

    def getEvaluation(self):
        return self.evaluation

    def getHeader(self):
        return self.header

    def setFen(self, fen:str):
        self.moveLog = []
        self.board = chess.Board(fen)

    def makeMove(self, move):
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
        self.board.pop()
        if len(self.moveLog) > 0:
            del self.moveLog[-1]

    def whiteToMove(self):
        return self.board.turn

    def colorToMove(self):
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

    def getValidMoves(self):
        return [m for m in self.board.legal_moves]


    def stdValidMoves(self):
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


    def piece_at(self, r:int, c:int):
        '''        
        Piece in a board position

        Args:
            r: piece row
            c: piece column

        Returns:
            piece
        '''

        moved = self.board.piece_at((7-r)*8+c)
        if moved is None:
            return "--"

        moved = moved.symbol().upper()
        color = self.colorAt(r, c)
        return color + moved

    def inCheck(self):
       return self.board.is_check()

    def checkMate(self):
        return self.board.is_checkmate()

    def staleMate(self):
        return self.board.is_stalemate()

class Move:
    ranksToRows = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}
    rowsToRanks = {v: k for k, v in ranksToRows.items()}
    filesToCols = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7}
    colsToFiles = {v: k for k, v in filesToCols.items()}



    def fromChessMove(m,board)->Move:
        return Move([7-chess.square_rank(m.from_square),chess.square_file(m.from_square)],
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

        self.uci = self.getRankFile(startSq[0], startSq[1]) + \
              self.getRankFile(stopSq[0], stopSq[1])
        self.move:Optional[chess.Move] = chess.Move.from_uci(self.uci)
        self.board = board
        self.pieceMoved = board.piece_at(self.startRow, self.startCol)
        self.pieceCaptured = board.piece_at(self.stopRow, self.stopCol)
        self.prettyPrint = self.board.board.san(self.move)
        self.enPassant = self.board.board.is_en_passant(self.move)


    def promoteToPiece(self, p):
        self.move = chess.Move.from_uci(self.move.uci()+chess.piece_symbol(p))
        return self.move

    def getChessNotation(self):
        return self.move.uci()

    def prettyChessNotation(self):
        return self.prettyPrint


    def getRankFile(self, r, c):
        return self.colsToFiles[c] + self.rowsToRanks[r]

    def __eq__(self, other):
        if not isinstance(other, Move):
            return False
        return self.getChessNotation() == other.getChessNotation()
