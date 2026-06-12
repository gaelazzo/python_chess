from __future__ import annotations 
from dis import Positions
from optparse import Option
from typing import Optional,List,Dict,TypeAlias,Any
from xmlrpc.client import boolean
import json_helper
import csv
from datetime import datetime, timedelta, date
import os

from chess import polyglot,Board as ChessBoard
import chess.pgn
from chess.pgn import  Game as PgnGame
from chess.engine import Cp, Mate, MateGiven
from dataclasses import dataclass,asdict,fields
import io
import sys

from config import config   # for correctsToLearn ("Learned" threshold); config imports only stdlib, no cycle



def get_base_path():
    """Returns the path of the folder where the executable or the script is located"""
    if getattr(sys, 'frozen', False):  # If it is a PyInstaller executable
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
DATA_FOLDER = os.path.join(BASE_PATH, "data")

def parse_date(date_str: str) -> Optional[date]:
        if not date_str:
            return None
        for fmt in ("%d/%m/%Y", "%Y.%m.%d", "%Y-%m-%d"):  # Try the three formats
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unrecognized date format: {date_str}")


@dataclass
class LearnPosition:
    zobrist:int    
    fen:str    
    ok:str
    move:str
    moves:str
    successful:int
    ntry:int
    white:str
    black:str   
    eco:Optional[str]=None
    gamedate:Optional[date]=None
    lastTry:Optional[date]=None
    firstTry:Optional[date]=None
    serie:int = 0
    skip:bool    =False
    idquiz: Optional[int] = None
    severity:int = 0   # worst evaluation drop (cp) seen for this mistake

    def to_PgnString(self) -> str:
        pgn_game  =  self.to_Pgn()
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        return pgn_game.accept(exporter)
        

    def to_Pgn(self)->PgnGame:
        pgnGame = PgnGame()
        # pgnGame.setup(self.fen)
        pgnGame.headers["White"] = self.white
        pgnGame.headers["Black"] = self.black
        pgnGame.headers["ECO"] = self.eco if self.eco is not None else ""
        pgnGame.headers["Date"] = datetime.strftime(self.gamedate, "%Y.%m.%d") if self.gamedate else "????.??.??"
        pgnGame.headers["Result"] = "*"
        # pgnGame.headers["FEN"] = self.fen
        board = pgnGame.board()
        node = pgnGame
        # board = ChessBoard() # self.fen
        for uci_move in self.moves.split():
            try:
                move = board.parse_uci(uci_move)
                board.push(move)
                node = node.add_variation(move)
            except ValueError:
                print(f"Error converting UCI move: {uci_move}")
                # Optional: log or handle errors
                break
        # pgnGame.board = board
        return pgnGame


    @classmethod
    def from_dict(cls, data: dict[str,Any]) -> "LearnPosition":
        # Explicitly convert the data
        return cls(
            zobrist=int(data['zobrist']),
            fen=data['fen'],
            eco=data['eco'],
            lastTry=datetime.strptime(data["lastTry"], "%d/%m/%Y").date() if data["lastTry"] else None,
            firstTry=datetime.strptime(data["firstTry"], "%d/%m/%Y").date() if data["firstTry"] else None,
            moves=data['moves'],
            successful=int(data['successful']),

            ntry=int(data['ntry']),
            skip=data['skip'] == "S",
            serie=int(data['serie']),
            white=data['white'],
            black=data['black'],
            ok = data["ok"],
            move = data["move"],
            gamedate= parse_date(data["gamedate"]) if data["gamedate"] else None,
            idquiz=int(data["idquiz"]) if "idquiz" in data.keys()  and data["idquiz"] != "" else None,
            severity=int(data.get("severity") or 0),   # default 0 for old bases (column missing)
        )


#data structure
# fieldnames = ['zobrist', 'skip', 'fen', 'eco', 'lastTry', 'firstTry', 'ok', 'move', "moves", "successful", "ntry", "white", "black", "date"]
def string_to_date(date_string):
    try:
        # Try to convert the string into a datetime object
        return datetime.strptime(date_string, "%Y.%m.%d").date()
    except ValueError:
        # If the conversion fails, return None
        return None

@dataclass
class LearningBaseData:
    movesToAnalyze:int
    blunderValue:int
    ponderTime:float
    useBook:bool
    filename:Optional[str]=None
    # Per-nick [first, last] game-date window already analyzed into this base
    # (ISO "YYYY-MM-DD" strings). Used by the Study Advisor to skip, on a re-run,
    # the games a previous analysis already counted. Absent in old bases -> None.
    analyzedRanges:Optional[Dict[str,List[Optional[str]]]]=None

class LearningBase:
    
    def __init__(self, movesToAnalyze:int, blunderValue:int, ponderTime:float, useBook:bool):        
        self.positions:Dict[int,LearnPosition] = {}
        self.movesToAnalyze:int = movesToAnalyze
        self.filename:Optional[str] = None
        self.blunderValue:int = blunderValue
        self.ponderTime:float = ponderTime
        self.useBook:bool = useBook
        # nick(lowercased) -> [first_date, last_date] already analyzed (see LearningBaseData)
        self.analyzedRanges:Dict[str,List[Optional[date]]] = {}
    
    def setFileName(self, filename:str):
        self.filename = filename

    def _to_dict(self)->LearningBaseData:
        '''
        Convert the object to a dictionary representation.
        '''
        data_dict:LearningBaseData = LearningBaseData(
            movesToAnalyze=self.movesToAnalyze,
            blunderValue= self.blunderValue,
            ponderTime=self.ponderTime,
            useBook=self.useBook)

        if self.filename:
            data_dict.filename= self.filename

        if self.analyzedRanges:
            data_dict.analyzedRanges = {
                nick: [d.isoformat() if d is not None else None for d in pair]
                for nick, pair in self.analyzedRanges.items()
            }

        return data_dict

    @classmethod
    def _from_dict(cls, data_dict:LearningBaseData)->LearningBase:
        '''
        Create an instance using the data from the dictionary
        '''
        instance = cls(            
            movesToAnalyze=data_dict.movesToAnalyze,
            blunderValue=data_dict.blunderValue,
            ponderTime=data_dict.ponderTime,
            useBook=data_dict.useBook,            
        )
        
        if data_dict.filename is not None:
            instance.setFileName(data_dict.filename)

        ranges = getattr(data_dict, "analyzedRanges", None)
        if ranges:
            instance.analyzedRanges = {
                nick: [date.fromisoformat(s) if s else None for s in pair]
                for nick, pair in ranges.items()
            }

        return instance

    def isInAnalyzedRange(self, nick: str, d: date) -> bool:
        """True if game-date `d` falls inside the [first,last] window already
        analyzed for `nick` (INCLUSIVE on both ends). Lets a re-run skip the games
        a previous analysis of the same nick already counted, so it neither
        inflates the per-position stats nor revives 'Learned' positions."""
        pair = self.analyzedRanges.get((nick or "").lower())
        if not pair:
            return False
        first, last = pair
        if first is not None and d < first:
            return False
        if last is not None and d > last:
            return False
        return True

    def extendAnalyzedRange(self, nick: str, d: date) -> None:
        """Grow the analyzed [first,last] window for `nick` to include `d`."""
        key = (nick or "").lower()
        pair = self.analyzedRanges.get(key)
        if pair is None:
            self.analyzedRanges[key] = [d, d]
        else:
            first, last = pair
            self.analyzedRanges[key] = [
                d if first is None or d < first else first,
                d if last is None or d > last else last,
            ]


    def save(self, filename:Optional[str]=None):
        '''
        Save the learning base 
        '''
        
        filename = filename or "base_"+self.filename
        assert(filename is not None)

        # Prepare data to be saved
        learningBaseData = self._to_dict()
        class_data = asdict(learningBaseData)
        
        # Save lesson data
        #with open(class_filename, 'w', encoding="utf8") as class_file:            
            # json.dump(class_data, class_file, indent=4, separators=(",", ": "), ensure_ascii=False) # 

        json_helper.write_struct(os.path.join(DATA_FOLDER,filename)+".json", class_data)  
        self._savePositions()

    @classmethod
    def load(cls, filename:str)->LearningBase:
        '''
        Load the learning base positions
        Args:
            filename(str): File containing the learning base            
        '''        
        data = json_helper.read_struct(os.path.join(DATA_FOLDER,filename)+".json")
        
        learningBaseData = LearningBaseData(**data)
        # with open(class_filename, 'r', encoding="utf8") as class_file:
         #   json.load(class_file)
         #           
        instance = LearningBase._from_dict(learningBaseData)       
        instance._loadPositions()        
        return instance
    

    
    def _savePositions(self):
        """
            Saves the learning base positions
        """
        assert(self.filename is not None)

        with open(os.path.join(DATA_FOLDER,self.filename)+".csv", 'w', newline="") as csvfile:
            fieldnames = [f.name for f in fields(LearnPosition)]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_NONNUMERIC)

            writer.writeheader()
            for position in self.positions.values():
                rr = asdict(position)  # Converts the dataclass into a dictionary

                rr ["skip"] = "S" if rr["skip"] else "N"

                if rr["lastTry"] is not None:
                    rr["lastTry"] = datetime.strftime(rr["lastTry"], "%d/%m/%Y")

                if rr["gamedate"] is not None:
                    rr["gamedate"] = datetime.strftime(rr["gamedate"], "%d/%m/%Y")

                if rr["firstTry"] is not None:
                    rr["firstTry"] = datetime.strftime(rr["firstTry"], "%d/%m/%Y")
                
                writer.writerow(rr)


    # zobrist;fen;eco;lastTry;firstTry;move;ok;bad;moves,ntry,successful,ntry,white,black,date    
    
    def _loadPositions(self):
        self.positions.clear()
        assert(self.filename is not None)

        filepath = os.path.join(DATA_FOLDER, self.filename) + ".csv"
        if not os.path.exists(filepath):
            print(f"File {filepath} not found.")
            return

        with open(filepath) as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:                
                position = LearnPosition.from_dict(row)
                self.positions[position.zobrist] = position

        line_count = len(self.positions)
        print(f"learningBase[{self.filename}]: Processed {line_count} lines.")



    @classmethod
    def create_first_position(cls, zobrist:int,board:ChessBoard, game:PgnGame, goodMove:str, moveMade:str, severity:int=0)->LearnPosition:
        '''
            Create a position when it is not yet in the learning base
        '''
        moves = " ".join([board.uci(m) for m in board.move_stack])
        gamedate:Optional[date|None]  = string_to_date(game.headers["Date"]) if "Date" in game.headers else None


        return LearnPosition(
                zobrist=zobrist,
                fen=board.fen(),
                eco=game.headers.get("ECO"),
                lastTry=gamedate,
                firstTry=gamedate,
                ok = goodMove,
                move = moveMade,
                moves=moves,
                successful=0,
                ntry=0,
                skip=False,
                serie=0,
                white=game.headers["White"],
                black=game.headers["Black"],
                gamedate=gamedate,
                idquiz=None,
                severity=severity
            )
        
    
    @classmethod
    def maxValueDate(cls, oldTry:date|None, newValue:date)->date|None:
        if oldTry is None:
            return newValue

        if newValue is None:
            return oldTry

        if oldTry < newValue:
            return newValue
        return oldTry

    @classmethod
    def minValueDate(cls, oldTry:date|None, newValue:date)->date|None:
        if oldTry is None:
            return newValue

        if newValue is None:
            return oldTry

        if oldTry < newValue:
            return oldTry
        return newValue

    @classmethod
    def updatePositionStats(self, position:LearnPosition, moveMade:str,  date:date)->boolean:
        '''
            Updates data on a specified position. Considers the move good or bad basing on the 
                "ok" field of the position
            Args:
                position:  the chess position being played, BEFORE move is played
                moveMade: str  move played by the user  (you give board.uci(move))
                date: current date when move was played
            Returns:
                True if a good move was played, also updates the statistics on the position played.
                Side effects on skip: serie >= correctsToLearn consecutive corrects sets skip=True
                ("Learned", retired); a wrong answer on a skip=True position clears it (local revive).
        '''
        # {zobrist,skip,fen,eco,lastTry,firstTry,ok,move,moves,successful,ntry,white,black,date}        
        position.ntry += 1
        
        position.lastTry = LearningBase.maxValueDate(position.lastTry, date)  
        position.firstTry= LearningBase.minValueDate(position.firstTry, date)     
                
        if position.firstTry is None:
            position.firstTry = position.lastTry
        
        
        if position.ok == moveMade:            
            position.successful += 1
            if position.serie >0:
                position.serie += 1
            else:
                position.serie = 1

            # "Learned": after `correctsToLearn` consecutive successes (configurable
            # in Setup, default 5) the position is retired -> skip=True, excluded
            # from the base for life. Distinct from `correctsToSolve`, which only
            # governs leaving the current Solve-positions session. Fallback to 5 if
            # config is unavailable.
            learn_threshold = (config.correctsToLearn or 5) if config is not None else 5
            if position.serie >= learn_threshold:
                position.skip = True  # mark as learned
            res = True
        else:
            if position.serie > 0:
                position.serie = -1
            else:
                position. serie -= 1
            # Local "revive": a wrong answer on an already-"Learned" position
            # (skip=True) brings it back into rotation. getPositions excludes
            # skip=True positions, so without this they would never be reviewed
            # locally again even once you start failing them. `serie` is already
            # reset to negative just above, so the next correct streak must reach
            # `correctsToLearn` from scratch before it is retired again -- no extra
            # reset needed. NB: in *Solve positions* a skip=True position is never
            # proposed, so this only fires when the position is re-encountered in
            # the PGN-driven modes (Study openings / Endgame) or re-analysed by
            # Update learning base. This is a LOCAL heuristic only; BrainMaster
            # keeps its own, far richer scheduling over the full proposal history.
            if position.skip:
                position.skip = False
            res =  False

        #print("Moves: ",position.moves, "stored:",position.move, "made:",moveMade, "ok is :", position.ok)

        return res

    def addPosition(self, game:PgnGame, board:ChessBoard, goodMove:str)->LearnPosition:
        """
            Add a position to the learning base
            Args:
                game: pgn game being analyzed
                goodMove: the right move choosen by the engine
                board: current chess game (BEFORE the move is played)
            Returns:
                added position or None if already present
        """        
        zobrist:int = polyglot.zobrist_hash(board)
        if  zobrist not in self.positions:        
            position = LearningBase.create_first_position(zobrist, board, game, goodMove, goodMove)
            self.positions[zobrist] = position
            return position
        return None


    def reviveLearned(self) -> int:
        """Bring every "Learned" position back into local rotation.

        For each position with skip=True: clears skip and resets serie to 0
        (so it must earn a fresh `correctsToLearn` streak before being retired
        again). Everything else is kept -- attempt history (successful/ntry),
        dates, severity. Non-destructive: no position or stat is lost, the
        change is undone simply by re-learning. Returns how many positions were
        revived. LOCAL only -- BrainMaster keeps its own scheduling.
        """
        n = 0
        for pos in self.positions.values():
            if pos.skip:
                pos.skip = False
                pos.serie = 0
                n += 1
        if n:
            self.save()
        return n

    def updatePosition(self, moveMade: str, goodMove: str, game:PgnGame, board:ChessBoard, severity:int=0):
        """
            Analyze last move made in a game
            Args:
                moveMade:   move played by the user
                goodMove: the right move choosen by the engine
                game: pgn game being analyzed
                board: current chess game (BEFORE the move is played)
                severity: evaluation drop (cp) of this mistake; the worst one is kept
            Returns:
                True if a good move was played, also updates the statistics on the position played
        """
        zobrist:int = polyglot.zobrist_hash(board)

        if  zobrist not in self.positions:
            position = LearningBase.create_first_position(zobrist, board, game, goodMove, moveMade, severity=severity)
            self.positions[zobrist] = position
            # position["skip"] = "S" if board.uci(goodMove) == board.uci(badMove) else "N"

        else:
            position = self.positions[zobrist]
            position.severity = max(position.severity, severity)   # recurrence: keep the worst drop
            if moveMade == goodMove:
                moveMade = position.ok # assume is the right one in order to correctly update the stats

        gamedate:date  = string_to_date(game.headers["Date"]) if "Date" in game.headers else date.today()

        return LearningBase.updatePositionStats(position, moveMade, gamedate)

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)  # create the folder (and all necessary subfolders)

'''
   Get all base filename from the data folder
'''
file_json = [
     os.path.splitext(nome)[0] for nome in os.listdir(DATA_FOLDER)
    if nome.endswith('.json') and (nome.startswith('base_'))
]


def stripBaseName(filename: str) -> str:
    """
    Strips the 'base_' prefix from the filename and remove path if present.
    """
    return os.path.splitext(os.path.basename(filename))[0].replace("base_", "")

'''
    Load all learning bases from the data folder
'''
learningBases = {stripBaseName(name): LearningBase.load(name) for name in file_json}


if __name__ == "__main__":
    # checkGameOpenings()
    print(f"Start writing")
    for base in learningBases.values():
        base.save()
    print(f"Save Done")
