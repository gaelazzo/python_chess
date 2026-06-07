"""Saving and loading games (and their selection menus).

Split out of chessMain.py. Depends on shared state, app, the PGN list helper
and the menu helpers -- never on chessMain.
"""
import sys
from datetime import datetime

import pygame as p
import pygame_menu
from pygame_menu.locals import ALIGN_CENTER

from app_context import app
from state import playParameters, positionParameters, small_font_theme
import BoardScreen as BS
import pgngamelist
from GameState import GameState
from menu_helpers import addChoosePGNFile, make_updater, make_selector_updater


def header_from_playparameters(params):
    header = []
    for key in ["White", "Black", "Event", "Site", "Result"]:
        val = params.get(key.lower(), "")
        if val:
            header.extend([key, val])
    header.extend(["Date", datetime.today().strftime("%Y.%m.%d")])
    header.extend(["Round","*"])
    return header

def save_game(gs:GameState):
    '''
    Saves the current game state to a file.
    The file name is taken from the positionParameters["filename"] variable.
    '''
    if positionParameters["filename"] is None:
        text = "Please select a PGN file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        return
    # Honor the folder chosen by the user in the file selector (e.g. endgames/);
    # if none was registered we fall back to pgn/.
    folder = positionParameters.get("filename_folder") or None
    gamelist = pgngamelist.PgnGameList(positionParameters["filename"], folder=folder)
    positionParameters["gameid"] = gamelist.save_game(gs, positionParameters["gameid"])
    
    app.main_background()
    BS.drawEndGameText(app.screen, None, "Game saved")
    BS.update()
    app.delay(2)

def load_game(gs:GameState):
    '''
    Loads a game from a selected PGN file allowing the user to choose which game to load.
    '''
    if positionParameters["filename"] is None:
        text = "Please select a PGN file"
        app.main_background()
        BS.drawEndGameText(app.screen, None, text)
        BS.update()
        app.delay(2 )
        return

    # Honor the folder chosen in the file selector (e.g. openings/ or endgames/);
    # without it the list would always be read from pgn/ and look empty for a
    # file picked elsewhere (mirror of save_game).
    folder = positionParameters.get("filename_folder") or None
    gameList = pgngamelist.PgnGameList(positionParameters["filename"], folder=folder)
    total_games = len(gameList.games)
    games_per_page = 10
    current_page = 0
    total_pages = (total_games + games_per_page - 1) // games_per_page

    menu_running = True
    surface = app.screen
    def load_game_wrapper(N):
        nonlocal menu_running
        positionParameters["gameid"] = N
        menu_running = False

    def cancel_load():
        nonlocal menu_running
        menu_running = False

    def next_page():
        nonlocal current_page
        if current_page < total_pages-1:
            current_page += 1
            refresh_menu()

    def prev_page():
        nonlocal current_page
        if current_page > 0:
            current_page -= 1
            refresh_menu()

    def first_page():
        nonlocal current_page
        current_page = 0
        refresh_menu()

    def last_page():
        nonlocal current_page
        current_page = total_pages-1
        refresh_menu()


    _load_menu = pygame_menu.Menu('Select Game', app.W, app.H, 
                             theme=small_font_theme)
    frame_width = 4 * 80 + 3 * 10  # 4 buttons of 80px + 3 margins of 10px
    frame_height = 50

    def refresh_menu():
        _load_menu.clear()
        start = current_page * games_per_page
        end = min(start + games_per_page, total_games)
        for i in range(start, end):
            game = gameList.games[i]
            white = game.headers.get("White", "?")
            black = game.headers.get("Black", "?")
            result = game.headers.get("Result", "?")
            nMoves = len(list(game.mainline_moves()))
            label = f"{i+1}. {white} vs {black} ({nMoves} moves) [{result}]"
            _load_menu.add.button(label, load_game_wrapper, i)

        if total_games > games_per_page:
            _load_menu.add.vertical_margin(10)
            nav_buttons = []
            #if current_page > 0:
            nav_buttons.append(_load_menu.add.button('|<', first_page))
            nav_buttons.append(_load_menu.add.button('<<', prev_page))

            #if current_page < total_pages :
            nav_buttons.append(_load_menu.add.button('>>', next_page))
            nav_buttons.append(_load_menu.add.button('>|', last_page))


            if nav_buttons:
                nav_frame = _load_menu.add.frame_h(frame_width, frame_height, align=ALIGN_CENTER)
                for b in nav_buttons:
                    nav_frame.pack(b, margin=(10, 0))  # horizontal margin between buttons


        _load_menu.add.vertical_margin(20)
        _load_menu.add.button('Cancel', cancel_load)

    refresh_menu()

    while menu_running:
        events = p.event.get()
        for ev in events:
            if ev.type == p.QUIT:
                p.quit()
                sys.exit()

        surface.fill((0, 0, 0))
        _load_menu.update(events)
        _load_menu.draw(surface)
        p.display.flip()
    
    
    if positionParameters.get("gameid") is not None:
        gameList.load_game(gs, positionParameters["gameid"])        
        #gs.goToLastMove()

        app.main_background()
        BS.drawEndGameText(app.screen, None, "Game selected")
        BS.update()
        app.delay(2)

def load_menu(GS:GameState):
    menu_running = True
    surface = app.screen
    def load_game_wrapper():
        nonlocal menu_running
        menu_running = False
        load_game(GS)

    def cancel_load():
        nonlocal menu_running
        menu_running = False

    _load_menu = pygame_menu.Menu('Load Game', app.W, app.H, theme=pygame_menu.themes.THEME_BLUE)
    addChoosePGNFile(_load_menu)
    _load_menu.add.button('Load', load_game_wrapper)
    _load_menu.add.button('Cancel', cancel_load)

    while menu_running:
        events = p.event.get()
        for ev in events:
            if ev.type == p.QUIT:
                p.quit()
                sys.exit()

        surface.fill((0, 0, 0))
        _load_menu.update(events)
        _load_menu.draw(surface)
        p.display.flip()


def save_menu(GS:GameState):
    menu_running = True
    surface = app.screen
    prev_pgn = positionParameters["filename"]
    def save_game_wrapper():
        nonlocal menu_running
        GS.setHeader(header_from_playparameters(playParameters))
        today_str = datetime.today().strftime("%Y.%m.%d")
        if prev_pgn != positionParameters["filename"]:
            positionParameters["gameid"]= None
        save_game(GS)
        menu_running = False

    def cancel_save():
        nonlocal menu_running
        menu_running = False

    _save_menu = pygame_menu.Menu('Save Game', app.W, app.H,
                             theme=pygame_menu.themes.THEME_BLUE)
    # create=True: the file dialog lets you type a NEW file name (e.g. to start a
    # new opening file), not only pick an existing PGN.
    addChoosePGNFile(_save_menu, title="Choose or create PGN file", create=True)
    _save_menu.add.text_input('White:', default=playParameters["white"] or "", onchange=make_updater("white",str,playParameters))
    _save_menu.add.text_input('Black:', default=playParameters["black"] or "", onchange=make_updater("black",str,playParameters))
    _save_menu.add.text_input('Event:', default=playParameters["event"] or "", onchange=make_updater("event",str,playParameters))
    _save_menu.add.text_input('Site:', default=playParameters["site"] or "", onchange=make_updater("site",str,playParameters))
    # Result is one of the 4 standard PGN values, chosen from a selector (it was a
    # free text-input but "Result: lol" does not conform to the format and
    # confuses downstream PGN parsers).
    _result_options = [
        ("*  (in progress / unknown)",   "*"),
        ("1-0  (White wins)",            "1-0"),
        ("0-1  (Black wins)",            "0-1"),
        ("1/2-1/2  (draw)",              "1/2-1/2"),
    ]
    _result_current = playParameters.get("result") or "*"
    _result_idx = next(
        (i for i, (_, v) in enumerate(_result_options) if v == _result_current),
        0,
    )
    _save_menu.add.selector('Result: ', _result_options,
                            default=_result_idx,
                            onchange=make_selector_updater("result", playParameters))
    _save_menu.add.button('Save', save_game_wrapper)
    _save_menu.add.button('Cancel', cancel_save)

    

    
    while menu_running:
        events = p.event.get()
        for ev in events:
            if ev.type == p.QUIT:
                p.quit()
                sys.exit()

        surface.fill((0, 0, 0))
        _save_menu.update(events)
        _save_menu.draw(surface)
        p.display.flip()
