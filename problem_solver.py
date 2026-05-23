from __future__ import annotations
from fileinput import filename 
import UCIEngines
import GameState
import re
import os
import chess.engine

def extract_section_name(text: str):
    match = re.search(r"\\mysection\{([^}]*)\}", text)
    if match:
        return match.group(1).strip()
    return None


def format_line(board, san_string):
    moves = san_string.split()

    move_number = board.fullmove_number
    is_white = board.turn

    result = []
    i = 0

    if not is_white:
        result.append(f"{move_number}...")
        result.append(moves[0])
        i = 1
        move_number += 1

    while i < len(moves):
        result.append(f"{move_number}.")
        result.append(moves[i])

        if i + 1 < len(moves):
            result.append(moves[i + 1])

        i += 2
        move_number += 1

    return " ".join(result)

def format_latex_problem(fen, formatted_line):
    return (
        f"\\item\n"
        f"\\newchessgame[setfen={fen}]\n"
        f"\\variation{{ {formatted_line} }}\n"
    )

def process_fen_file(input_file, output_file, depth=26, multipv=8):
    state = GameState.GameState()

    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    section_name = extract_section_name(text)

    if not section_name:
        section_name = os.path.basename(input_file)  # fallback

    # Estrazione FEN
    fens = re.findall(r"setfen=([^\n,]+)", text)

    with open(output_file, "w", encoding="utf-8") as out:
        out.write(f"\\mysection{{{section_name}}}\n\n")
        out.write("\\begin{enumerate}\n\n")

        for idx, fen in enumerate(fens, start=1):
            try:
                state.setFen(fen)
                board = state.board()
                print(f"Analyzing: {fen} ->")

                lines = UCIEngines.solve_position(
                    board,
                    depth=depth,
                    multipv=multipv
                )

                if not lines:
                    print("  No solution found.\n")
                    out.write(f"Problema {idx}) Nessuna soluzione\n")
                    continue
                print(f"{lines[0]}\n")
                # prendi SOLO la prima linea (come hai richiesto)
                main_line = lines[0]

                # formattazione numerata
                formatted = format_line(board, main_line)

                latex_block = format_latex_problem( fen, formatted)

                out.write(f"{latex_block}\n")                
            except Exception as e:
                out.write(f"Problema {idx}) ERRORE: {e}\n")
            
        out.write("\\end{enumerate}\n\n\n")




def solve_single_position(fen,depth=None,multipv=None,time=None, root_moves=None, mate=None):
    state = GameState.GameState() 
    state.setFen(fen)
    board = state.board()
    print(state) 
    if root_moves is not None:
        root_moves = [board.parse_san(r) for r in root_moves]
    lines = UCIEngines.solve_position(board, depth,multipv,time, root_moves, mate) 
    for main_line in lines:
        formatted = format_line(board, main_line)
        print (formatted)

    print("Output:\n")
    formatted = format_line(board, lines[0])
    latex_block = format_latex_problem( fen, formatted)
    print(latex_block)

if __name__ == "__main__":
    UCIEngines.engine_open()
#
#
    try:       
        #res = solve_single_position("r4rk1/1bpR2pp/p3Pp2/1pb2P1Q/5B1N/1P2p1PK/P6P/q7 w - - 0 2", depth=40, multipv=1, time=None)
        #print(res)  
        res = solve_single_position("2r2rk1/1b1nqpp1/pp6/2ppN2P/2PPpPP1/4P3/PPQ5/2KR1B1R w - - 0 1", root_moves=["Ng6"], multipv=1, time=60)
        print(res)  
    except Exception as e:
        print(e)
    
    UCIEngines.engine_close()




    # ["ultimatraversa","inchiodatura","scoperta","attaccodoppio","diversione","sgombero", ["sovraccarico","forchetta_cavallo","attrazione","interferenza"]

    # for filename in ["sgombero"]:
    #     print(f"Processing {filename}\n")
    #     process_fen_file(
    #         f"D:\\cloud\\One Drive\\Documenti\\corso scacchi latex\\{filename}.tex",
    #         "output.txt",
    #         depth=26,
    #         multipv=1
    #     )