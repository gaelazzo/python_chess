"""
Main driver file

"""
# --- Splash screen ----------------------------------------------------------
# Apriamo la finestra pygame PRIMA degli import pesanti (GameState ->
# pyttsx3 init, LearningBase -> lettura csv, in seguito book.open_book e
# UCIEngines.engine_open in runMain): cosi' l'utente vede subito il logo
# durante i ~3-4 secondi di startup, invece di una console immobile.
# La finestra viene poi ridimensionata da p.display.set_mode in runMain.
import os as _os, sys as _sys
import pygame as _splash_p


def _show_splash():
    try:
        _splash_p.init()
        if getattr(_sys, "frozen", False):
            base = _os.path.dirname(_sys.executable)
        else:
            base = _os.path.dirname(_os.path.abspath(__file__))
        logo_path = _os.path.join(base, "pic-chess.png")
        if not _os.path.exists(logo_path):
            return
        logo = _splash_p.image.load(logo_path)
        lw, lh = logo.get_size()
        win_w = max(lw + 80, 600)
        win_h = max(lh + 120, 400)
        screen = _splash_p.display.set_mode((win_w, win_h))
        _splash_p.display.set_caption("Chess trainer -- caricamento...")
        screen.fill(_splash_p.Color(38, 38, 56))
        screen.blit(logo, ((win_w - lw) // 2, (win_h - lh) // 2 - 20))
        try:
            font = _splash_p.font.SysFont("Arial", 22, bold=True)
            txt = font.render("Caricamento in corso...", True, _splash_p.Color("white"))
            screen.blit(txt, ((win_w - txt.get_width()) // 2, win_h - 50))
        except Exception:
            pass
        _splash_p.display.flip()
        _splash_p.event.pump()
    except Exception as e:
        print(f"splash skipped: {e}")


_show_splash()


def _splash_progress(text: str) -> None:
    """Aggiorna la striscia inferiore della splash window con `text`. Usato
    dai vari step di startup (libro, motore, indicizzazione PGN) per dare
    feedback nei secondi di attesa. Errori non bloccanti."""
    try:
        screen = _splash_p.display.get_surface()
        if screen is None:
            return
        w, h = screen.get_size()
        strip = _splash_p.Rect(0, h - 80, w, 80)
        _splash_p.draw.rect(screen, _splash_p.Color(38, 38, 56), strip)
        font = _splash_p.font.SysFont("Arial", 18, bold=True)
        txt = font.render(text, True, _splash_p.Color("white"))
        screen.blit(txt, ((w - txt.get_width()) // 2, h - 40))
        _splash_p.display.update(strip)
        _splash_p.event.pump()
    except Exception:
        pass


# --- Fine splash; ora gli import pesanti possono procedere a finestra aperta.

from ast import Dict
from collections.abc import Callable
from email import headerregistry
import os.path
import random
from typing import Optional
from GameState import Move,GameState,voce
import pygame as p
import json
import BrainMaster
from LearningBase import LearningBase, LearnPosition, learningBases
import UCIEngines
import BoardScreen as BS
import analyzer
import analyzer as AN
import chess
import pygame_menu
import random
import pyperclip
import pygame_gui
from pygame_gui.windows.ui_file_dialog import UIFileDialog
import pgngamelist
from pygame_gui.elements.ui_button import UIButton
from pygame_menu.locals import ALIGN_CENTER, ORIENTATION_HORIZONTAL
import sys
from dataclasses import dataclass
from BrainMaster import AnswerData, QuestionData, give_answers, ask_for_quiz, unlock_new_lesson
from typing import Optional, Union,List,Dict, Tuple, Iterator
from datetime import datetime, date
import os
import Quiz
import chess_com_download
from config import config, load_config, save_config
import pgngamelist
import uuid
import pyttsx3
import book

from app_context import app
import game_loop_common as glc
import state
from state import playParameters, positionParameters, COLOR_MAP, REVERSE_COLOR_MAP, CIRCLE_COLOR, small_font_theme
from learningbase_admin import (
    createLearningBase, updateLearningBase, unrollPgnAsLesson,
    unrollPGN, readChessComGames, readLichessGames, createCourse,
)
from menu_helpers import (
    make_updater, make_selector_updater, make_bool_selector_updater,
    make_file_selector, setPlayColor, addChooseCourse, addChooseBaseFile,
    addChoosePGNFile,
)
from save_load import save_menu, load_menu
from modes.play_game import playGame
from modes.replay import solvePositions
from modes.brainmaster import playBrainMasterBase
from modes.openings import playOpening
from modes.improve import buildImproveMenu
from modes.study_advisor import buildAdvisorMenu
from modes.endgames import playEndgames, ENDGAMES_FOLDER

def get_base_path():
    """Restituisce il percorso della cartella dove si trova l'eseguibile o lo script"""
    if getattr(sys, 'frozen', False):  # Se è un eseguibile PyInstaller
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
DATA_FOLDER = os.path.join(BASE_PATH, "data")

def delay(unit: float) -> None:
    app.delay(unit)

def main_background() -> None:
    """
    Function used by menus, draw on background while menu is active.
    :return: None
    """
    app.main_background()


def setEloMax(value):
    playParameters["elomax"] = value

def setPlayElo(value):
    playParameters["elo"] = int(value)

def humanPlay():
    playParameters["whiteCPU"]=False
    playParameters["blackCPU"] = False
    playGame()


def setPositionEco(current_text, **kwargs):
    global positionParameters
    if current_text == "":
        positionParameters["eco"] = None
    else:
        positionParameters["eco"] = current_text.upper()

def setPlayer(current_text, **kwargs):
    global positionParameters
    if current_text == "":
        positionParameters["player"] = None
    else:
        positionParameters["player"] = current_text


def update_base_display():
    value = positionParameters.get("base", "Nessuna selezionata")
    state.current_base_label.set_title(value)
    state.current_base_label2.set_title(value)
    state.current_base_label3.set_title(value)

def update_filename_display():
    value = positionParameters.get("filename", "Nessuna selezionata")
    state.current_filename_label.set_title(value)
    state.current_filename_label3.set_title(value)
    state.current_filename_label4.set_title(value)
    state.current_ChessComFile_label.set_title(value)

def quit_program():
    print ("quit program called\n")
    app.main_running = False


def mainMenu(width,height, test: bool = False) -> None:

    app.clock = p.time.Clock()

    playParameters["elomax"] = False
    surface = app.screen
    default_color_index = REVERSE_COLOR_MAP.get(positionParameters["color"], 0)
    setColorIndex = lambda val, idx: positionParameters.__setitem__("color", COLOR_MAP[int(val[0][1])])

    value_map = {1: True, 0: False}
    reverse_value_map = {v: k for k, v in value_map.items()}
    setUseBook = lambda val, idx: positionParameters.__setitem__("useBook", COLOR_MAP[val[0][1]])

    playComputerMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Choose play params',
        width=width
    )    
    playColorSelector = playComputerMenu.add.selector('You play', [("White", 0), ("Black", 1), ("Random", 2)], onchange=setPlayColor)
    playComputerMenu.add.range_slider('ELO', range_values=(1350, 2850), onchange=setPlayElo, default=2000, increment=50)
    playComputerMenu.add.toggle_switch("ELO MAX", state_text=("Off", "On"), state_values=(False, True),
                                       onchange=make_updater("elomax",bool,playParameters))
    # playComputerMenu.add.range_slider('Num Moves to Show', range_values=(0, 10), increment = 1,
    #                                   onchange=make_updater("num_moves_to_show",int),
    #             default=state.num_moves_to_show)  # Aggiungi questa riga

    def playComputerGame():
        # onchange del selettore scatta solo quando il valore cambia: applico
        # comunque il colore corrente, altrimenti col default (o dopo "Play
        # between humans") whiteCPU/blackCPU resterebbero a False e il computer
        # non muoverebbe.
        setPlayColor(playColorSelector.get_value(), playColorSelector.get_index())
        playGame()

    playComputerMenu.add.button('Play', playComputerGame)


    solvePositionsMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Solve positions',
        width=width
    )    
    solvePositionsMenu.add.text_input('ECO (optional)', default=positionParameters["eco"] or "", onchange=setPositionEco)
    # NB: nessun selettore di colore in Solve positions. Una base ha gia' un suo
    # colore-al-tratto implicito (es. una base tattica da analyzePgn ha posizioni
    # col turno del giocatore analizzato; una base di repertorio d'apertura ha
    # posizioni col colore per cui e' stata costruita). Filtrare ulteriormente
    # qui esclude soltanto posizioni utili. Il filtro ECO resta per drillare un
    # sottoinsieme specifico.
    addChooseBaseFile(solvePositionsMenu)

    solvePositionsMenu.add.selector('Lead-in moves', [("Skip", 1), ("Replay", 0)], default=(0 if state.play_position else 1), onchange=make_selector_updater("play_position"))
    solvePositionsMenu.add.range_slider('Num Moves to Show', range_values=(0, 10), increment=1, onchange=make_updater("num_moves_to_show",int),
                                     value_format=lambda x: str(round(x, 0)),
                default=state.num_moves_to_show)  # Aggiungi questa riga
    solvePositionsMenu.add.selector('Practice order', [("Priority", "priority"), ("Random", "random")],
                                    default=(0 if state.practice_order == "priority" else 1),
                                    onchange=make_selector_updater("practice_order"))

    solvePositionsMenu.add.button('Play', solvePositions)


    openingsMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Study openings',
        width=width
    )

    # NB: nessun selettore "You play" in Study openings: il colore del lato
    # che si esercita viene RILEVATO automaticamente dal contenuto del PGN
    # (vedi detect_user_color_from_pgn in modes/openings.py). Le PGN di
    # repertorio hanno una struttura "una sola continuazione del lato proprio,
    # tante varianti del lato opponente": basta guardare la prima variante.
    openingsMenu.add.range_slider('Num Moves to Show', range_values=(0, 10), increment=1,value_format=lambda x: str(round(x, 0)),
                                       onchange=make_updater("num_moves_to_show",int),
                default=state.num_moves_to_show)  # Aggiungi questa riga
    addChoosePGNFile(openingsMenu)
    openingsMenu.add.selector('Lead-in moves', [("Skip", 1), ("Replay", 0)], default=(0 if state.play_position else 1), onchange=make_selector_updater("play_position"))
    openingsMenu.add.button('Play', playOpening)

    endgamesMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Allena finali',
        width=width
    )
    addChoosePGNFile(endgamesMenu, folder=ENDGAMES_FOLDER, title='Choose endgame PGN')
    endgamesMenu.add.button('Play', playEndgames)

    CreateCourseMenu = None
    if config.base_url:
        CreateCourseMenu = pygame_menu.Menu(
            height=height,
            theme=pygame_menu.themes.THEME_BLUE,
            title='Create course',
            width=width
        )        
        addChooseBaseFile(CreateCourseMenu)
        CreateCourseMenu.add.button('Create', createCourse)

    BrainMasterMenu = None
    if config.base_url:
        BrainMasterMenu = pygame_menu.Menu(
            height=height,
            theme=pygame_menu.themes.THEME_BLUE,
            title='Exercise with Brainmaster',
            width=width
        )        
        addChooseCourse(BrainMasterMenu)
        BrainMasterMenu.add.range_slider('Num Moves to Show', range_values=(0, 10),  onchange=make_updater("num_moves_to_show",int), value_format=lambda x: str(round(x, 0)),
                    default=state.num_moves_to_show, increment=1)  # Aggiungi questa riga
        BrainMasterMenu.add.selector('Lead-in moves', [("Skip", 1), ("Replay", 0)], default=(0 if state.play_position else 1), onchange=make_selector_updater("play_position"))
        BrainMasterMenu.add.button('Exercise', playBrainMasterBase)


    updateLearningBaseMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Update learning base',
        width=width
    )  
    labels = []
    updateLearningBaseMenu.add.text_input('player:', default=positionParameters["player"] or "", onchange=make_updater("player",str,positionParameters))
    addChoosePGNFile(updateLearningBaseMenu)
    addChooseBaseFile(updateLearningBaseMenu)
    updateLearningBaseMenu.add.button('Update Learning Base', updateLearningBase)


    createBaseMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Create empty learning base',
        width=width
    )
    createBaseMenu.add.text_input('movesToAnalyze:', default=positionParameters["movesToAnalyze"] or "",onchange=make_updater("movesToAnalyze",int,positionParameters))
    createBaseMenu.add.text_input('blunderValue:', default=positionParameters["blunderValue"] or "", onchange=make_updater("blunderValue",int,positionParameters))
    createBaseMenu.add.text_input('ponderTime:', default=positionParameters["ponderTime"] or "",onchange=make_updater("ponderTime",float,positionParameters))
    createBaseMenu.add.selector('useBook', [("Yes", 1), ("No", 0)], default= reverse_value_map[ positionParameters["useBook"] ], 
                                onchange=make_bool_selector_updater("useBook", positionParameters))
    createBaseMenu.add.text_input('filename:', default=positionParameters["filename"] or "",onchange=make_updater("filename",str,positionParameters))    
    createBaseMenu.add.button('Create learning base', createLearningBase)


    unrollPGNMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Unroll a PGN into a learning base',
        width=width
    )
    addChoosePGNFile(unrollPGNMenu)
    unrollPGNMenu.add.selector('You play', [("White", "0"), ("Black", "1")], default=default_color_index if default_color_index<2 else 0, onchange=setColorIndex) 
    addChooseBaseFile(unrollPGNMenu)

    unrollPGNMenu.add.button('Unroll', unrollPGN)


    unrollPGNMenuAsLesson = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Unroll a PGN into a learning base',
        width=width
    )  
    addChoosePGNFile(unrollPGNMenuAsLesson)
    unrollPGNMenuAsLesson.add.selector('You play', [("White", "0"), ("Black", "1")], default=default_color_index if default_color_index<2 else 0, onchange=setColorIndex) 
    addChooseBaseFile(unrollPGNMenuAsLesson)

    unrollPGNMenuAsLesson.add.button('Unroll as lesson', unrollPgnAsLesson)


    chessComMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='download chess.com games',
        width=width
    )  
    labels = []
    chooseNewPgn = make_file_selector("filename", None , labels, pgngamelist.PGN_FOLDER+"/newfile.pgn", ".pgn", "Select PGN file to create", create=True)
    chessComMenu.add.button('PGN file to create', chooseNewPgn)
    default_value = str(positionParameters.get("filename", "Nessuna selezionata"))
    label = chessComMenu.add.button(default_value,chooseNewPgn,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())
    labels.append(label)
    chessComMenu.add.text_input('player:', default=positionParameters["player"] or "", onchange=make_updater("player",str,positionParameters))
    chessComMenu.add.selector('Player color', [("White", 0), ("Black", 1), ("Any", 2)], default=default_color_index , onchange=setColorIndex)

    chessComMenu.add.button('Download games', readChessComGames)


    lichessMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='download lichess games',
        width=width
    )
    labels_l = []
    chooseNewPgn_l = make_file_selector("filename", None, labels_l, pgngamelist.PGN_FOLDER + "/newfile.pgn", ".pgn", "Select PGN file (existing or new)", create=True)
    lichessMenu.add.button('PGN file (existing or new)', chooseNewPgn_l)
    default_value_l = str(positionParameters.get("filename", "Nessuna selezionata"))
    label_l = lichessMenu.add.button(default_value_l, chooseNewPgn_l, font_size=20, background_color=None, selection_effect=pygame_menu.widgets.NoneSelection())
    labels_l.append(label_l)
    lichessMenu.add.text_input('player:', default=positionParameters["player"] or "", onchange=make_updater("player", str, positionParameters))
    lichessMenu.add.selector('Player color', [("White", 0), ("Black", 1), ("Any", 2)], default=default_color_index, onchange=setColorIndex)

    lichessMenu.add.button('Download games', readLichessGames)


    def combine_onchange(first_fn, second_fn):
        def combined(*args, **kwargs):
            first_fn(*args, **kwargs)
            second_fn()
        return combined

    configureGame = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Setup',
        width=width
    )    
    configureGame.add.text_input('base_url:', default=config.base_url or "", 
                                            onchange=combine_onchange(make_updater("base_url",str,config), save_config))
    configureGame.add.text_input('id studente:', default=config.id_student or "",
                                        onchange=combine_onchange(make_updater("id_student",str,config), save_config))

    def choose_engine(engine):
        config.engine = engine.name
        save_config()
        UCIEngines.engine_close()
        UCIEngines.engine_open()


    labels = []
    chooseEngine = make_file_selector(
         None, None , labels,UCIEngines.ENGINE_FOLDER,".exe", "Choose engine",choose_engine, None)
    configureGame.add.button('Choose engine', chooseEngine)
    default_value = config.engine or "Nessun motore selezionato"

    label = configureGame.add.button(default_value,chooseEngine,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())    
    labels.append(label)

    def choose_book(abook):
        config.book = abook.name
        save_config()
        book.close_book()
        book.open_book()
    labels = []
    chooseBook = make_file_selector(
         None, None , labels,book.BOOKS_FOLDER, ".bin", "Choose book",choose_book, None)
    configureGame.add.button('Choose book', chooseBook)
    default_value = getattr(config, 'book', None) or "Nessun libro selezionato"
    label = configureGame.add.button(default_value,chooseBook,font_size=20, background_color=None,selection_effect=pygame_menu.widgets.NoneSelection())    
    labels.append(label)

    # configureGame.add.text_input('engine:', default=config.engine or "", onchange=combine_onchange(make_updater("engine",str,config), restart_engine))

    # Parametri della sessione "Solve positions" (program-wide, salvati in config.json).
    # NB: uso target_module=config (setattr su SimpleNamespace) invece del 3o positional
    # target_dict, che con un SimpleNamespace fallirebbe silenziosamente.
    configureGame.add.range_slider('Max errors in session', range_values=(2, 30), increment=1,
                                   onchange=combine_onchange(make_updater("maxErrorsToConsider", int, target_module=config), save_config),
                                   value_format=lambda x: str(int(round(x, 0))),
                                   default=config.maxErrorsToConsider)
    configureGame.add.range_slider('Corrects to learn', range_values=(1, 10), increment=1,
                                   onchange=combine_onchange(make_updater("correctsToLearn", int, target_module=config), save_config),
                                   value_format=lambda x: str(int(round(x, 0))),
                                   default=config.correctsToLearn)
    configureGame.add.range_slider('TTS speed (wpm)', range_values=(90, 280), increment=10,
                                   onchange=combine_onchange(
                                       make_updater("tts_rate", int, target_module=config),
                                       lambda: (save_config(), voce.refresh_rate())),
                                   value_format=lambda x: str(int(round(x, 0))),
                                   default=config.tts_rate)

    # DB di riferimento per le statistiche di posizione (vedi position_stats.py).
    # Selezione tramite file selector (parte da pgn/ ma puoi navigare ovunque);
    # salva il percorso completo cosi' va a buon fine anche se il file non e' in pgn/.
    import position_stats as _pstats
    def choose_reference_db(selected_path):
        # `selected_path` e' il path COMPLETO (pathlib.Path) scelto nel dialog.
        # Salviamo l'intero path -- il PGN puo' stare fuori da pgn/.
        config.reference_db = os.fspath(selected_path)
        save_config()
        _pstats.invalidate_cache()  # forza re-build alla prossima query
        # Aggiorna label coi nome file (senza percorso).
        new_label = os.path.basename(config.reference_db) or "Nessun DB di riferimento"
        for lbl in ref_labels:
            if lbl:
                lbl.set_title(new_label)
    ref_labels = []
    chooseRefDb = make_file_selector(
        None, None, ref_labels, pgngamelist.PGN_FOLDER, ".pgn",
        "Choose reference DB", choose_reference_db, None,
    )
    configureGame.add.button('Choose reference DB (le mie partite)', chooseRefDb)
    _ref_default = os.path.basename(config.reference_db) if config.reference_db else "Nessun DB di riferimento"
    ref_label = configureGame.add.button(_ref_default, chooseRefDb, font_size=18,
                                          background_color=None,
                                          selection_effect=pygame_menu.widgets.NoneSelection())
    ref_labels.append(ref_label)

    toolsMenu = pygame_menu.Menu(
        height=height,
        theme=pygame_menu.themes.THEME_BLUE,
        title='Tools',
        width=width
    )  
    toolsMenu.add.button('Download Chess.com games', chessComMenu)
    toolsMenu.add.button('Download lichess games', lichessMenu)
    toolsMenu.add.button("Create learning base", createBaseMenu)
    toolsMenu.add.button('Update learning base', updateLearningBaseMenu)
    toolsMenu.add.button('Unroll PGN file', unrollPGNMenu)
    toolsMenu.add.button('Unroll PGN file as lesson', unrollPGNMenuAsLesson)
    if CreateCourseMenu:
        toolsMenu.add.button('Create Course for BrainMaster', CreateCourseMenu)
    toolsMenu.add.button('Setup', configureGame)


    app.main_menu = pygame_menu.Menu('Chess Python', width, height,
                                 theme=pygame_menu.themes.THEME_BLUE)
    app.main_menu.add.button('Migliora dalle tue partite', buildImproveMenu(width, height))
    app.main_menu.add.button('Cosa studio adesso?', buildAdvisorMenu(width, height))
    app.main_menu.add.button('Play against computer', playComputerMenu)
    app.main_menu.add.button('Analysis / Human Play', humanPlay)
    app.main_menu.add.button('Solve positions', solvePositionsMenu)
    if BrainMasterMenu:
        app.main_menu.add.button('BrainMaster lessons', BrainMasterMenu)
    app.main_menu.add.button('Study openings', openingsMenu)
    app.main_menu.add.button('Allena finali', endgamesMenu)
    app.main_menu.add.button('Tools', toolsMenu)
    app.main_menu.add.button('Quit', quit_program) # pygame_menu.events.EXIT

    app.main_menu.disable()
    app.main_menu.full_reset()
    app.main_menu.enable()


    while app.main_running:
        # Tick
        app.clock.tick(app.FPS)

        # Paint background
        main_background()

        events = p.event.get()
        for event in events:
            if event.type == p.QUIT:
                app.main_running = False          # chiusura finestra
            elif event.type == p.KEYDOWN and event.key == p.K_q:
                app.main_running = False          # 'q' esce dal programma


        # Main menu
        if app.main_menu.is_enabled():
            app.main_menu.update(events)   # Gestisce gli eventi del menu
            app.main_menu.draw(surface)    # Disegna il menu sulla finestra
            #app.main_menu.mainloop(surface, main_background, disable_loop=test, fps_limit=FPS)
        else:
            app.main_running = False  # Chiude il programma se il menu sparisce

        # Flip surface
        p.display.flip()

        # At first loop returns
        if test:
            break


def resource_path(relative_path):
    """Restituisce il path assoluto, compatibile con PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def runMain():
    p.init()

    app.myfont = p.font.SysFont('Comic Sans MS', 20)

    book.open_book()
    UCIEngines.engine_open()

    # Preload dell'indice del DB di riferimento (se configurato). 3 livelli di
    # cache in position_stats: RAM, disco (`<pgn>.idx` accanto al PGN, valida
    # finche' mtime/size del PGN non cambiano), rebuild. Il primo avvio costa
    # ~10-15s per 40k partite e poi salva il `.idx`; gli avvii successivi
    # caricano dal disco in ~1-3s. Su tasto Y poi le query sono O(1).
    try:
        import position_stats
        ref_db = (getattr(config, 'reference_db', '') or '').strip()
        if ref_db and os.path.exists(ref_db):
            ref_name = os.path.basename(ref_db)
            cache_exists = os.path.exists(position_stats._index_cache_path(ref_db))
            if cache_exists:
                _splash_progress(f"Carico indice di {ref_name} dal disco...")
            else:
                _splash_progress(f"Indicizzo {ref_name} (prima volta, richiede tempo)...")
            def _idx_progress(n_games):
                _splash_progress(f"Indicizzo {ref_name}: {n_games} partite...")
            position_stats.get_index(ref_db, progress=_idx_progress)
            _splash_progress(f"DB di riferimento pronto ({ref_name}).")
    except Exception as e:
        print(f"position_stats preload fallito: {e}")

    try:
        app.W, app.H = BS.init()

        app.screen = p.display.set_mode((app.W, app.H))
        app.screen.fill(p.Color("white"))

        p.display.set_caption('Chess trainer')
        Icon = p.image.load(resource_path('pic-chess.png'))
        p.display.set_icon(Icon)


        app.manager = pygame_gui.UIManager((app.W, app.H))

        mainMenu(app.W, app.H)

        p.display.quit()
        p.quit()    

    finally:
        UCIEngines.engine_close()
        book.close_book()

    sys.exit()


if __name__ == "__main__":
    runMain()
