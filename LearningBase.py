from __future__ import annotations 
from typing import Optional,List,Dict
from xmlrpc.client import boolean
import json_helper
import csv
from datetime import datetime, timedelta, date
import os
import chess.polyglot
from chess.engine import Cp, Mate, MateGiven


folder = "data"

#data structure
# fieldnames = ['zobrist', 'skip', 'fen', 'eco', 'lastTry', 'firstTry', 'ok', 'move', "moves", "successful", "ntry", "white", "black", "date"]
def string_to_date(date_string):
    try:
        # Prova a convertire la stringa in un oggetto datetime
        return datetime.strptime(date_string, "%Y.%m.%d").date()
    except ValueError:
        # Se la conversione fallisce, restituisci None
        return None

class LearningBase:
    
    def __init__(self, movesToAnalyze:int, blunderValue:int, ponderTime:float, useBook:bool):        
        self.positions = {}
        self.movesToAnalyse = movesToAnalyze
        self.filename = None
        self.blunderValue = blunderValue
        self.ponderTime = ponderTime
        self.useBook = useBook
    
    def setFileName(self, filename:str):
        self.filename = filename

    def _to_dict(self)->Dict[str,object]:
        '''
        Convert the object to a dictionary representation.
        '''
        data = {
            # "data": self.data,
            "movesToAnalyse": self.movesToAnalyse,
            "blunderValue": self.blunderValue,
            "ponderTime": self.ponderTime, 
            "useBook": self.useBook
        }    

        if self.filename:
            data["filename"]= self.filename      

        return data

    @classmethod
    def _from_dict(cls, data:Dict[int,object])->LearningBase:
        '''
        Create an instance using the data from the dictionary
        '''
        instance = cls(            
            movesToAnalyze=data["movesToAnalyse"],
            blunderValue=data["blunderValue"],
            ponderTime=data["ponderTime"],
            useBook=data["useBook"],            
        )
        
        if "filename" in data:
            instance.setFileName(data["filename"])
        
        return instance


    def save(self, filename:str=None):
        '''
        Save the learning base 
        '''
        
        filename = filename or self.filename
        
        # Prepare data to be saved
        class_data = self._to_dict()
        
        # Save lesson data
        #with open(class_filename, 'w', encoding="utf8") as class_file:            
            # json.dump(class_data, class_file, indent=4, separators=(",", ": "), ensure_ascii=False) # 

        json_helper.write_struct(os.path.join(folder,filename)+".json", class_data)  
        self._savePositions()

    @classmethod
    def load(cls, filename:str=None)->LearningBase:
        '''
        Load the learning base positions
        Args:
            filename(str): File containing the learning base            
        '''

        data = json_helper.read_struct(os.path.join(folder,filename)+".json")

        # with open(class_filename, 'r', encoding="utf8") as class_file:
         #   json.load(class_file)
         #           
        instance = LearningBase._from_dict(data)       
        instance._loadPositions()
        
        return instance
    
    
    def _savePositions(self):
        """
            Saves the learning base positions
        """
        with open(os.path.join(folder,self.filename)+".csv", 'w', newline="") as csvfile:
            fieldnames = ['zobrist', 'skip', 'fen', 'eco', 'lastTry', 'firstTry', 'ok', 'move', "moves", "successful",
                          "ntry",
                          "white", "black", "date","serie"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for row in self.positions.values():
                rr = dict(
                    (k, v) for k, v in row.items() if k in fieldnames
                )
                if rr["lastTry"] is not None:
                    rr["lastTry"] = datetime.strftime(rr["lastTry"], "%d/%m/%Y")
                if rr["firstTry"] is not None:
                    rr["firstTry"] = datetime.strftime(rr["firstTry"], "%d/%m/%Y")
                
                writer.writerow(rr)

        if len(self.positions) % 50 == 0:
            print(f"{self.filename}: {len(self.positions)} positions found")    


    # zobrist;fen;eco;lastTry;firstTry;move;ok;bad;moves,ntry,successful,ntry,white,black,date    
    def _loadPositions(self):
        self.positions.clear()
        with open(os.path.join(folder,self.filename)+".csv") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                row['zobrist'] = int(row['zobrist'])
                zobrist = row['zobrist']

                if row["lastTry"] == "":
                    row["lastTry"] = None
                else:
                    row["lastTry"] = datetime.strptime(row["lastTry"], "%d/%m/%Y")

                if row["firstTry"] == "":
                    row["firstTry"] = None
                else:
                    row["firstTry"] = datetime.strptime(row["firstTry"], "%d/%m/%Y")

                if not "successful" in row:
                    row["successful"] = 0
                else:
                    if row["successful"] is None:
                        row["successful"] = 0
                    row["successful"] = int(row["successful"])

                if not "ntry" in row:
                    row["ntry"] = 0
                else:
                    if row["ntry"] is None:
                        row["ntry"] = 0
                    row["ntry"] = int(row["ntry"])

                
                if not "serie" in row:
                    row["serie"] = 0
                else:
                    if row["serie"] is None:
                        row["serie"] = 0
                    row["serie"] = int(row["serie"])

                self.positions[zobrist] = row

        line_count = len(self.positions)
        print(f"learningBase[{self.filename}]: Processed {line_count} lines.")

    @classmethod
    def create_first_position(cls, zobrist,board:chess.Board,game:chess.pgn.Game)->Dict[str,object]:
        moves = " ".join([board.uci(m) for m in board.move_stack])
        gamedate:Optional[date|None]  = string_to_date(game.headers["Date"]) if "Date" in game.headers else None

        return  {
            "zobrist": zobrist,
            "fen": board.fen(),
            "eco": game.headers["ECO"] if "ECO" in game.headers else None,
            "lastTry": gamedate,
            "firstTry": gamedate,
            "moves": moves,
            "successful": 0,
            "ntry": 0,
            "skip":"N",
            "serie":0,
            "white": game.headers["White"],
            "black": game.headers["Black"],
            "date": gamedate
        }
    
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
            return newValue
        return oldTry

    @classmethod
    def updatePositionStats(self, position:Dict[str,object], moveMade:chess.Move, board:chess.Board, date:date)->boolean:
        '''
            Updates data on a specified position
            Args:
                position: the chess position being played
                moveMade: chessMove  move played by the user
                board: current chess game
            Returns:
                True if a good move was played, also updates the statistics on the position played
        '''        
        zobrist:Optional[int] = chess.polyglot.zobrist_hash(board)

        # {zobrist,skip,fen,eco,lastTry,firstTry,ok,move,moves,successful,ntry,white,black,date}        
        position["ntry"] = position["ntry"] + 1
        
        position["lastTry"] = LearningBase.maxValueDate(position["lastTry"], date)  
        position["firstTry"]= LearningBase.minValueDate(position["firstTry"], date)     
                
        if position["firstTry"] is None:
            position["firstTry"] = position["lastTry"]
        
        res = None
        if position["ok"] == board.uci(moveMade):            
            position["successful"] = position["successful"] + 1
            if position["serie"] >0:
                position["serie"]=position["serie"]+1
            else:
                position["serie"]=1

            if position["serie"] >= 5:
                position["skip"] = "S"  # mark as learned
            res = True
        else:            
            if position["serie"] > 0:
                position["serie"]= -1
            else:
                position["serie"]=position["serie"]-1
            res =  False

        print(position["moves"])

        return res

    def updatePosition(self, moveMade: chess.Move, goodMove: chess.Move, game:chess.pgn.Game, board:chess.Board):
        """
            Analyze last move made in a game
            Args:
                moveMade: chessMove  move played by the user
                goodMove: the right move choosen by the engine
                game: pgn game being analyzed
                board: current chess game
            Returns:
                True if a good move was played, also updates the statistics on the position played
        """        

        zobrist:Optional[int] = chess.polyglot.zobrist_hash(board)

        if  zobrist not in self.positions:        
            position = LearningBase.create_first_position(zobrist, board, game)
            position["ok"] = board.uci(goodMove)
            position["move"] = board.uci(moveMade)
            self.positions[zobrist] = position
            # position["skip"] = "S" if board.uci(goodMove) == board.uci(badMove) else "N"

        else:
            position = self.positions[zobrist]
        
        gamedate:Optional[date]  = string_to_date(game.headers["Date"]) if "Date" in game.headers else None

        return LearningBase.updatePositionStats(position, moveMade, board, gamedate)
        

        
        
    

learningBases = {
    "blunders": LearningBase.load("tacticalerrors"),
    "openings": LearningBase.load("openingerrors")
}