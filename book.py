import chess.polyglot
import os
from config import config
import sys
import atexit
from typing import Optional,List,Dict,Tuple,Dict
from chess.polyglot import zobrist_hash

def get_base_path():
    if getattr(sys, 'frozen', False):  # Se è un eseguibile PyInstaller
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
BOOKS_FOLDER = os.path.join(BASE_PATH, "books")


if not os.path.exists(BOOKS_FOLDER):
    os.makedirs(BOOKS_FOLDER)  # crea la cartella (e tutte le sottocartelle necessarie)  



book:chess.polyglot.MemoryMappedReader = None


def open_book():
    """
        Opens a book file
        Args:
            bookFileName: the name of the book file to open
        Returns:
            a MemoryMappedReader object
    """
    global book
    try:
        book = chess.polyglot.MemoryMappedReader(os.path.abspath(os.path.join(BOOKS_FOLDER,config.book)))
        num_positions  = sum(1 for _ in book)
        print(f"Book {config.book} loaded successfully. {num_positions} position found")
    except FileNotFoundError:
        print(f"Book file {config.book} not found. Please check the configuration.")        
    except Exception as e:
        print(f"An error occurred while opening the book: {e}")



def close_book():
    global book
    if book:
        book.close()
        book = None

atexit.register(close_book)


def getMovesFromBook(board: chess.Board) -> List[chess.polyglot.Entry]:
    """
        Gets all moves from the book for the given board position
        Args:
            board: chess.Board current position
        Returns:
            a chess.Move object if found, None otherwise
    """
    return [m for m in book.find_all(board,minimum_weight=0)]



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

if __name__ == "__main__":
    open_book()
    board = chess.Board("rnbqkb1r/ppp1pppp/3p1n2/8/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 1 3")
    print(hex(zobrist_hash(board)))
    close_book()