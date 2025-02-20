import asyncio
# [m for m in g.mainline_moves()]
import chess
import chess.pgn
import chess.polyglot
from chess.engine import Cp, Mate, MateGiven
import random
from UCIEngines import engine

from datetime import datetime, timedelta, date
import csv

learningBases = {
    "blunders": {
        "data": {},
        "filename": "data/tacticalerrors.csv",
        "movesToAnalyse": 200,
        "blunderValue": 200,
        "ponderTime": 0.2,
        "useBook": False
    },
    "openings": {
        "data": {},
        "filename": "data/openingerrors.csv",
        "movesToAnalyse": 16,
        "blunderValue": 80,
        "ponderTime": 0.1,
        "useBook": True
    }
}

book = None

book = chess.polyglot.MemoryMappedReader("./books/Perfect2021.bin")


def close():
    book.close()


# zobrist,skip,fen,eco,lastTry,firstTry,ok,move,moves,ntry,successful


def saveInfo(learningBase):
    with open(learningBase["filename"], 'w', newline="") as csvfile:
        fieldnames = ['zobrist', 'skip', 'fen', 'eco', 'lastTry', 'firstTry', 'ok', 'move', "moves", "successful",
                      "ntry",
                      "white", "black", "date"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for row in learningBase["data"].values():
            rr = dict(
                (k, v) for k, v in row.items() if k in fieldnames
            )
            if rr["lastTry"] is not None:
                rr["lastTry"] = datetime.strftime(rr["lastTry"], "%d/%m/%Y")
            if rr["firstTry"] is not None:
                rr["firstTry"] = datetime.strftime(rr["firstTry"], "%d/%m/%Y")
            writer.writerow(rr)

    if len(learningBase["data"]) % 50 == 0:
        print(f"{learningBase['filename']}: {len(learningBase['data'])} positions found")


def updateInfoStats(board, learningBase):
    move = board.pop()
    zobrist = chess.polyglot.zobrist_hash(board)
    if zobrist not in learningBase["data"]:
        return False
    item = learningBase["data"][zobrist]
    item["ntry"] = item["ntry"] + 1
    item["lastTry"] = datetime.now().date()
    if item["firstTry"] is None:
        item["firstTry"] = item["lastTry"]
    if item["ok"] == board.uci(move):
        item["successful"] = item["successful"] + 1
        if item["successful"] >= 5:
            item["skip"] = "S"  # mark as learned
    else:
        item["successful"] = 0
    saveInfo(learningBase)
    board.push(move)
    return item["ok"] == board.uci(move)


def getRandomPositions(learningBase, filter=None):
    l = []
    for row in learningBase["data"].values():
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


def reloadLearningBases():
    for learn in learningBases.values():
        reloadLearned(learn)


# zobrist;fen;eco;lastTry;firstTry;move;ok;bad;moves,ntry,successful,ntry,white,black,date
def reloadLearned(learningBase):
    learningBase["data"].clear()
    with open(learningBase["filename"]) as csv_file:
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

            learningBase["data"][zobrist] = row

    line_count = len(learningBase["data"])
    print(f'{learningBase["filename"]}: Processed {line_count} lines.')


def isInBook(board):
    m = book.get(board, minimum_weight=0)
    if m is None:
        return False
    return True


nAdditions = 0

def evaluatePosition(board, ponderTime=3):
    # engine = chess.engine.SimpleEngine.popen_uci(r"D:\progetti\python\chess\engines\stockfish-17-avx2.exe")
    res = engine.analyse(board, chess.engine.Limit(time=ponderTime))
    # engine.close()
    return res["score"].relative

def recalcLearningBases():
    for learn in learningBases.values():
        recalcLearned(learn)


# zobrist;fen;eco;lastTry;firstTry;move;ok;bad;moves,ntry,successful,ntry,white,black,date
def recalcLearned(learningBase):
    # engine = chess.engine.SimpleEngine.popen_uci(r"D:\progetti\python\chess\engines\stockfish-17-avx2.exe")
    for pos in learningBase["data"].values():
        board = chess.Board(pos["fen"])
        res = engine.analyse(board, chess.engine.Limit(time=3), info=chess.engine.INFO_PV)
        goodMove = board.uci(res["pv"][0])
        if goodMove == pos["ok"]:
            continue
        print(res)
        print(f"Position {pos['fen']}: move {pos['ok']} recalculated to {goodMove}")
        pos['ok'] = goodMove
        saveInfo(learningBase)

    # engine.close()


def addInfoError(game, board, engine, learningBase):
    badMove = board.pop()  # evaluate a good move

    zobrist = chess.polyglot.zobrist_hash(board)
    if zobrist in learningBase["data"]:
        return

    res = engine.analyse(board, chess.engine.Limit(time=0.4), info=chess.engine.INFO_PV)
    goodMove = res["pv"][0]

    moves = " ".join([board.uci(m) for m in board.move_stack])
    r = {
        "zobrist": zobrist,
        "fen": board.fen(),
        "eco": game.headers["ECO"] if "ECO" in game.headers else None,
        "lastTry": None,
        "firstTry": None,
        "ok": board.uci(goodMove),
        "move": board.uci(badMove),
        "moves": moves,
        "skip": "S" if board.uci(goodMove) == board.uci(badMove) else "N",
        "successful": 0,
        "ntry": 0,
        "white": game.headers["White"],
        "black": game.headers["Black"],
        "date": game.headers["Date"] if "Date" in game.headers else None
    }
    learningBase["data"][zobrist] = r
    saveInfo(learningBase)

    # global nAdditions
    # nAdditions += 1
    # if nAdditions == 5:
    #     saveInfos(info, filename)
    #     nAdditions = 0


def checkInfo(pgnFileName, learningBase):
    engine = chess.engine.SimpleEngine.popen_uci(r"D:\progetti\python\chess\engines\stockfish-17-avx2.exe")
    pg = PgnAnalyzer("Hires", pgnFileName, learningBase)
    pg.setEngine(engine)
    pg.analyzeDataBase()
    engine.quit()


class PgnAnalyzer:

    def __init__(self, playerName, filename, learningBase):
        self.pgn = open(filename, encoding='utf-8')
        self.colorToPlay = "White"
        self.player = playerName
        self.positions = {}
        self.movesToAnalyse = learningBase["movesToAnalyse"]
        self.engine = None
        self.blunderValue = learningBase["blunderValue"]
        self.ponderTime = learningBase["ponderTime"]
        self.learningBase = learningBase
        pass

    def setEngine(self, engine):
        self.engine = engine

    def analyzeDataBase(self):
        while True:
            game, colorToAnalyze = self.loadNextGame()
            if game is None:
                break
            board = self.analyzeGame(game, colorToAnalyze)
            if board is not None:
                addInfoError(game, board, self.engine, self.learningBase)

        self.pgn.close()
        saveInfo(self.learningBase)

    def loadNextGame(self):
        while True:
            game = chess.pgn.read_game(self.pgn)
            if game is None:
                return None, None
            if game.headers["White"] == self.player:
                return game, True
            if game.headers["Black"] == self.player:
                return game, False

    def analyzeGame(self, game, colorToAnalyze):
        board: chess.Board = game.board()
        nmoves = 0
        prevScore = 0

        for node in game.mainline():
            move = node.move
            nmoves += 1
            if nmoves > self.movesToAnalyse:
                return None
            board.push(move)

            eval = node.eval()
            if board.turn != colorToAnalyze and eval is not None:  # this refers to previous move!!!
                if eval < (prevScore - self.blunderValue):
                    return board

            if self.learningBase["useBook"]:
                if chess.pgn.NAG_MISTAKE in node.nags or \
                        chess.pgn.NAG_BLUNDER in node.nags:
                    return board
                if chess.pgn.NAG_DUBIOUS_MOVE in node.nags:
                    return board

            if board.turn == colorToAnalyze:
                continue

            if self.learningBase["useBook"] and isInBook(board):
                continue

            zobrist = chess.polyglot.zobrist_hash(board)
            if zobrist in self.learningBase["data"]:
                return board
            try:
                infoAfter = self.engine.analyse(board, chess.engine.Limit(time=self.ponderTime))
            except:
                return None
            pvsAfter = infoAfter["score"].pov(colorToAnalyze)
            if pvsAfter.is_mate():
                if pvsAfter < Cp(0):  # will get mated
                    return board
                return None  # will give mate
            currScore = pvsAfter.score()
            if currScore < (prevScore - self.blunderValue):
                return board
            prevScore = currScore


reloadLearningBases()

if __name__ == "__main__":
    # checkGameOpenings()
    print(f"Start analyzing")
    checkInfo("game1.pgn", learningBases["blunders"])
    close()
    print(f"Analyzing Done")
