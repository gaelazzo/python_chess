"""
Stores current state of game
Determines valid moves
Keeps a move log
"""
from __future__ import annotations 
from re import S
from typing import Optional,List
import sys
import chess 
from chess.pgn import ChildNode, Game
import chess.polyglot
import random
import threading
import queue
import pyttsx3
import book
from move_speech import expand_moves_for_speech


class Voce:
    """Asynchronous TTS.

    Architecture: a single persistent worker thread owns the pyttsx3 engine
    and consumes a queue of requests. The voice is selected ONCE by the worker
    (not by the main thread). This avoids the SAPI5 apartment-threading problem
    on Windows: a `setProperty('voice', ...)` executed on a COM thread
    different from the one that runs `say()` is silently ignored, causing the
    reading to fall back to the system default voice (e.g. Italian if that is
    what the system is set to).
    """

    def __init__(self, lang_prefix="en"):
        self._lang_prefix = lang_prefix
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._engine = None  # created in the worker
        self._voice_id = None  # populated by _apply_voice
        self._engine_ready = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._worker, name="TTSWorker", daemon=True
        )
        self._worker_thread.start()
        # We briefly wait for initialization, so the first leggi() does not
        # start before the engine and voice are ready.
        self._engine_ready.wait(timeout=3.0)

    def _find_target_voice_id(self, voices):
        """Returns the voice.id to set, or None if no English voice was found.
        Precedence order identical to `_select_voice`."""
        try:
            from config import config as _cfg
            target = (getattr(_cfg, 'tts_voice', '') or '').strip().lower()
        except Exception:
            target = ''
        if target:
            for v in voices:
                hay = ((v.name or '') + ' ' + (v.id or '')).lower()
                if target in hay:
                    return v.id, f"config '{target}'"
        name_hints = ('english', 'en-', 'en_', 'zira', 'david', 'mark', 'hazel',
                      'eva', 'james', 'susan')
        for v in voices:
            name_l = (v.name or '').lower()
            if any(h in name_l for h in name_hints):
                return v.id, "name-hint"
        for v in voices:
            try:
                for lang in (v.languages or []):
                    if isinstance(lang, bytes):
                        lang = lang.decode('utf-8', errors='replace')
                    if self._lang_prefix in str(lang).lower():
                        return v.id, "lang-prefix"
            except Exception:
                continue
        return None, None

    def _apply_rate_from_config(self):
        """Sets the rate of the TTS engine.

        On Windows we use the SAPI5 driver directly; on other systems we let
        the pyttsx3 driver handle the property.
        """
        try:
            from config import config as _cfg
            wpm = int(getattr(_cfg, 'tts_rate', 150) or 150)
        except Exception:
            wpm = 150
        if sys.platform != 'win32':
            try:
                self._engine.setProperty('rate', wpm)
            except Exception:
                pass
            return
        # Conversion wpm -> SAPI5 rate (-10..+10). 200 wpm = 0 (Windows default).
        if wpm < 100:
            sapi_rate = -10
        elif wpm > 350:
            sapi_rate = 10
        else:
            sapi_rate = int(round((wpm - 200) / 15))
        driver = getattr(getattr(self._engine, 'proxy', None), '_driver', None)
        sapi = getattr(driver, '_tts', None)
        if sapi is None:
            return
        try:
            sapi.Rate = sapi_rate
            print(f"TTS: rate={wpm}wpm -> SAPI5 Rate={sapi_rate}")
        except Exception as e:
            print(f"TTS apply rate failed: {e}")

    def _apply_voice(self, voice_id, source):
        """Sets the voice of the TTS engine."""
        if sys.platform != 'win32':
            try:
                self._engine.setProperty('voice', voice_id)
                self._voice_id = voice_id
                print(f"TTS: voice applied (source={source}) -> {voice_id}")
                return True
            except Exception as e:
                print(f"TTS apply voice failed: {e}")
                return False

        # Canonical path to SAPI5 in modern pyttsx3
        driver = getattr(getattr(self._engine, 'proxy', None), '_driver', None)
        sapi = getattr(driver, '_tts', None)
        if sapi is None:
            print("TTS: SAPI5 driver not found (unexpected pyttsx3 version)")
            return False
        try:
            voices = sapi.GetVoices()
            n = voices.Count
            for i in range(n):
                token = voices.Item(i)
                if token.Id == voice_id:
                    sapi.Voice = token
                    self._voice_id = voice_id
                    # Direct verification on the COM object
                    actual = sapi.Voice.Id if sapi.Voice else None
                    print(f"TTS: voice applied (source={source}) "
                          f"actual={actual} -> "
                          f"{'OK' if actual == voice_id else 'MISMATCH'}")
                    return actual == voice_id
        except Exception as e:
            print(f"TTS apply voice failed: {e}")
        return False

    def _select_voice(self):
        """Chooses and applies an English voice; prints diagnostics at startup."""
        try:
            voices = list(self._engine.getProperty('voices'))
        except Exception as e:
            print(f"TTS: cannot list voices: {e}")
            return
        print(f"TTS: {len(voices)} voices available:")
        for v in voices:
            print(f"  - id={v.id!r} name={v.name!r} langs={v.languages}")
        voice_id, source = self._find_target_voice_id(voices)
        if voice_id is None:
            print(f"TTS: no voice '{self._lang_prefix}' found, OS default")
            return
        ok = self._apply_voice(voice_id, source)
        print(f"TTS: target voice id={voice_id} (source={source}) -> "
              f"{'applied' if ok else 'NOT APPLIED'}")

    def _worker(self):
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty('volume', 1.0)
            self._select_voice()
            self._apply_rate_from_config()
        except Exception as e:
            print(f"TTS init failed: {e}")
            self._engine_ready.set()
            return
        self._engine_ready.set()

        while True:
            text = self._queue.get()
            if text is None:  # sentinel (unused today: thread is a daemon)
                break
            try:
                # On Windows some pyttsx3 SAPI5 versions lose the setting
                # between consecutive say() calls and revert to the default.
                if sys.platform == 'win32' and self._voice_id is not None:
                    try:
                        driver = getattr(getattr(self._engine, 'proxy', None),
                                         '_driver', None)
                        sapi = getattr(driver, '_tts', None)
                        if sapi is not None:
                            voices = sapi.GetVoices()
                            for i in range(voices.Count):
                                token = voices.Item(i)
                                if token.Id == self._voice_id:
                                    sapi.Voice = token
                                    break
                    except Exception:
                        pass
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                # Typically "run loop already started" if stop() arrives
                # while say() is queued: no-op.
                print(f"TTS warning: {e}")

    def leggi(self, testo: str):
        """Queues a text to read; any reading in progress is interrupted.
        Returns immediately (does not block)."""
        if self._engine is None:
            return
        self._drain_queue()
        self._engine_stop_safe()
        testo = testo.replace("0-0-0", "long castle").replace("0-0", "castle")
        self._queue.put(testo)

    def stop(self):
        """Interrupts the TTS reading in progress (no-op if none is in progress)."""
        self._drain_queue()
        self._engine_stop_safe()

    def refresh_rate(self):
        """Re-applies the rate from the current `config.tts_rate`. To be called
        after an onchange of the TTS speed slider in the Setup menu."""
        if self._engine is None:
            return
        self._apply_rate_from_config()

    def _drain_queue(self):
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

    def _engine_stop_safe(self):
        if self._engine is None:
            return
        try:
            self._engine.stop()
        except Exception:
            pass


voce = Voce()


# --- Standard PGN annotation glyphs (NAGs) ---------------------------------
# Uses the actual Unicode symbols on screen (a few may not render if the
# move-log font lacks the glyph). The PGN file always stores the numeric NAG,
# so the canonical glyph survives save/load regardless of the font.
NAG_SYMBOL = {
    1: "!", 2: "?", 3: "!!", 4: "??", 5: "!?", 6: "?!", 7: "□",
    10: "=", 13: "∞", 14: "⩲", 15: "⩱", 16: "±", 17: "∓",
    18: "+−", 19: "−+", 22: "⨀", 23: "⨀",
}
# Ordered (nag, label) choices shown in the annotation menu.
NAG_CHOICES = [
    (1, "!  good move"), (2, "?  mistake"), (3, "!! brilliant move"),
    (4, "?? blunder"), (5, "!? interesting move"), (6, "?! dubious move"),
    (7, "□  only move"),
    (10, "=  equal position"), (13, "∞  unclear position"),
    (14, "⩲  White slightly better"), (15, "⩱  Black slightly better"),
    (16, "±  White better"), (17, "∓  Black better"),
    (18, "+−  White winning"), (19, "−+  Black winning"),
    (22, "⨀  zugzwang"),
]


class GameState:

     


    def __init__(self):
        # first char is the color, second char the piece, -- is empty
        self.pgn = Game()        
        self.moveLog:List[Move] = []
        self.header = []
        self.evaluation:Optional[float] = None
        self.node = self.pgn
        
    def get_hash(self):
        """
        Returns the hash of the current position
        """
        if self.node is None:
            return None
        return chess.polyglot.zobrist_hash(self.board())

    def board(self) -> chess.Board:
        """
        Returns the current board
        """
        if self.node is None:
            return None
        return self.node.board()


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
            voce.leggi(expand_moves_for_speech(self.node.comment))
    
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
        # Set headers, if available
        if header:
            headers = dict(zip(header[::2], header[1::2]))
            for key, value in headers.items():
                self.pgn.headers[key] = value
        return self.pgn


    def to_PgnString(self) -> str:
        '''Export the whole game to a PGN string (headers, variations and
        comments included).'''
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        return self.getPgn().accept(exporter)

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
        self.pgn.variations = []  # removes all previous moves
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
     
       # Check whether the move is already present among the variations
       for idx, child in enumerate(self.node.variations):
            existing_move = child.move
            if existing_move == move:
                self.node = child
                self.leggiCommentoCorrente()
                return False

       # Otherwise: create a new variation
       new_node = self.node.add_variation(move)  # creates and adds
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


    

    @staticmethod
    def count_leaves(node) -> int:
        '''
        Number of leaf nodes (terminal lines) in `node`'s subtree; a node with no
        variations counts as a single leaf. Used to weight the random choice of
        the next move so that every leaf line is equiprobable -- only the number
        of branches matters, not their depth.
        '''
        if not node.variations:
            return 1
        return sum(GameState.count_leaves(child) for child in node.variations)

    def makeNextMove(self):
        '''
        Play a random move among the stored variations, weighting each candidate
        by the number of leaf lines below it, so that every terminal line is
        equally likely to be reached (e.g. a branch with 3 leaves is chosen 3/5
        of the time against a sibling with 2 leaves).
        '''
        if self.node is None or self.is_end():
            return None
        children = self.node.variations
        if not children:
            return None
        weights = [GameState.count_leaves(child) for child in children]
        node = random.choices(children, weights=weights, k=1)[0]
        if node.comment:
            print(node.comment)

        move: Move = Move.fromChessMove(node.move, self)
        self.makeMove(move)
        return move

    def gotoFirstMove(self) -> bool:
            """
            Go to the first move in the current game
            """
            if self.node is None:
                return False
    
            while self.node.parent is not None:
                self.node = self.node.parent
                if len(self.moveLog) > 0:
                    del self.moveLog[-1]
    
            return True

     
    def goToLastMove(self)->bool:
         """
         Go to the last move in the current game
         """
         if self.node is None:
             return False
    
         while self.node.variations:
             node = self.node.variations[0]  # Follow only the main line
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

    def getMovesFromBook(self)->List[chess.polyglot.Entry]:
        """
        Returns a list of moves from the book for the current position
        """
        if self.node is None:
            return []
        return book.getMovesFromBook(self.board())
        
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
        

    def truncateAfterCurrent(self) -> bool:
        '''
        Delete every move/variation that follows the current position
        (the current node is kept). Returns True if something was removed.
        '''
        if self.node is None or not self.node.variations:
            return False
        self.node.variations = []
        self.evaluation = None
        return True

    def deleteCurrentVariation(self) -> bool:
        '''
        Remove the current move (and everything after it) from the game tree and
        step back to the parent node. Returns False on the start position
        (there is no move to delete).
        '''
        if self.node is None or self.node.parent is None:
            return False
        parent = self.node.parent
        parent.remove_variation(self.node.move)
        self.node = parent
        if self.moveLog:
            del self.moveLog[-1]
        self.evaluation = None
        return True

    def setMoveNag(self, nag: int) -> bool:
        '''
        Set the (single) annotation glyph on the current move, REPLACING any
        previous one -- a move's assessment is unique. A falsy nag (0/None)
        just clears the annotation. No-op (returns False) on the start position,
        which has no move to annotate.
        '''
        if self.node is None or self.node.parent is None:
            return False
        self.node.nags.clear()
        if nag:
            self.node.nags.add(nag)
        return True

    def clearMoveNags(self) -> bool:
        '''Remove every annotation glyph from the current move.'''
        if self.node is None or self.node.parent is None:
            return False
        self.node.nags.clear()
        return True

    def getMoveGlyphs(self) -> List[str]:
        '''
        Glyph string for EACH move in moveLog (same length, aligned by index);
        '' means no annotation. Covers the whole current line (not just the last
        move) so the move list can show the marks next to every move.
        '''
        line = []
        n = self.node
        while n is not None and n.parent is not None:
            line.append(n)
            n = n.parent
        line.reverse()
        glyphs = ["".join(NAG_SYMBOL[x] for x in sorted(node.nags) if x in NAG_SYMBOL)
                  for node in line]
        while len(glyphs) < len(self.moveLog):
            glyphs.append("")
        return glyphs[:len(self.moveLog)]

    def setMoveComment(self, text: str) -> bool:
        '''
        Set the text comment (PGN comment) on the current move; an empty string
        clears it. No-op (returns False) on the start position.
        '''
        if self.node is None or self.node.parent is None:
            return False
        self.node.comment = text or ""
        return True

    def getMoveComment(self) -> str:
        '''Text comment attached to the current move ('' if none).'''
        if self.node is None:
            return ""
        return self.node.comment or ""

    def goToNode(self, node) -> bool:
        '''
        Position the game on `node` (anywhere in the tree, including inside a
        variation), rebuilding moveLog along the path from the root. Used to
        jump straight to a move clicked in the notation view.
        '''
        if node is None:
            return False
        path = []
        n = node
        while n is not None and n.parent is not None:
            path.append(n)
            n = n.parent
        path.reverse()
        self.moveLog = []
        self.evaluation = None
        # Rebuild moveLog directly. We deliberately do NOT replay via
        # makeChessMove/_pgnMakeMove: that reads every move's comment aloud (TTS,
        # blocking), making navigation take seconds when moves are annotated.
        for nd in path:
            self.node = nd.parent          # board context before this move
            self.moveLog.append(Move.fromChessMove(nd.move, self))
        self.node = node
        return True

    def whiteToMove(self)->chess.Color:
        return self.board().turn

    def colorToMove(self)->str:
        return "w" if self.board().turn else "b"

    def colorAt(self, row:int, col:int)->str:
        """
         Color of the piece in a board position
        :param row:int
        :param col:int
        return:string
            w or b

        """
        p = self.board().piece_at((7-row)*8+col)
        if p is None:
            return "-"
        if p.color:
            return "w"
        return "b"

    def getValidMoves(self)->List[Move]:
        return [Move.fromChessMove(m, self) for m in self.node.board().legal_moves]


    def stdValidMoves(self)->List[Move]:
        dest = []
        for m in self.board().legal_moves:
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

        moved = self.board().piece_at((7-r)*8+c)
        if moved is None:
            return "--"

        movedColor  = moved.symbol().upper()
        color = self.colorAt(r, c)
        return color + movedColor

    def inCheck(self)->bool:
       return self.board().is_check()

    def checkMate(self)->bool:
        return self.board().is_checkmate()

    def staleMate(self)->bool:
        return self.board().is_stalemate()

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
            self.prettyPrint = game.board().san(self.move)
        except Exception as e:
            print('Conversion error:', str(e))
            self.prettyPrint = self.move.uci()

        self.enPassant = game.board().is_en_passant(self.move)


    def promoteToPiece(self, p) -> "Move":
        """Adds the promotion suffix and returns `self`.

        Accepts as input two forms historically passed by callers:
        - `chess.PieceType` (int 1..6), used by internal code (e.g. stdValidMoves).
        - A string ending with the piece symbol ('q'/'Q'/'wQ'/'bN'/...) as
          returned by `BoardScreen.choosePromotion` (format "<color><piece>").
        None / empty string / non-promotable piece -> no-op.

        Returns `self` (Move) -- not `self.move` (chess.Move) -- so that
        `move = move.promoteToPiece(piece)` keeps holding a Move and the
        `__eq__` against the validMoves entries keeps working.
        """
        if not p:
            return self
        if isinstance(p, int):
            symbol = chess.piece_symbol(p)
        else:
            symbol = str(p).strip()[-1:].lower()
        if symbol not in {"q", "r", "b", "n"}:
            return self
        if not self.uci.endswith(symbol):
            self.uci = self.uci + symbol
        self.move = chess.Move.from_uci(self.uci)
        return self

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
