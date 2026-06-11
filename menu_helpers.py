"""Reusable menu-construction helpers for the chess trainer.

Factories that build pygame_menu onchange callbacks and file/course choosers,
plus the add*-to-menu helpers. Split out of chessMain.py so both chessMain
(mainMenu) and save_load can use them. Depends only on shared state, app and
the low-level UI/domain modules -- never on chessMain.
"""
import os
import sys
import random
from typing import Optional, List, Callable

import pygame as p
import pygame_menu
import pygame_gui
from pygame_gui.windows.ui_file_dialog import UIFileDialog
from pygame_menu.locals import ALIGN_CENTER

from app_context import app
import state
from state import playParameters, positionParameters, small_font_theme
import BoardScreen as BS
import BrainMaster
import pgngamelist
from LearningBase import DATA_FOLDER


def add_menu_intro(menu: pygame_menu.Menu, text: str) -> None:
    """Add a boxed, wrapped explanatory blurb at the TOP of a second-level menu.

    Tells the user what the mode does -- and where it leads -- before they start
    configuring it. Call this right after creating the menu, before any other
    widget, so the box sits above the menu's own controls.
    """
    menu.add.label(
        text,
        wordwrap=True,
        font_size=15,
        font_color=(35, 35, 45),
        background_color=(206, 223, 242),   # soft panel on the blue theme
        padding=(8, 12),
        margin=(0, 6),
        selectable=False,
    )
    menu.add.vertical_margin(8)


def make_updater(key, cast_type, target_dict=None, validator=None, target_module=None):
    def updater(value):
        try:
            if cast_type == str:
                casted = value if value != "" else None
            else:
                casted = cast_type(value)

            if validator is not None and not validator(casted):
                return

            if target_dict is not None:
                target_dict[key] = casted
            else:
                mod = target_module or state
                setattr(mod, key, casted)
            state.save_user_prefs()  # persist the last choice made in the menus
        except (ValueError, TypeError):
            pass
    return updater


def make_selector_updater(key, target_dict=None):
    def updater(value, _index):
        selected_value = value[0][1]
        if target_dict is not None:
            target_dict[key] = selected_value
        else:
            setattr(state, key, selected_value)
        state.save_user_prefs()
    return updater

def make_selector_updater_mapped(key, target_dict, value_map):
    def updater(selection, index):
        # The selector value has the form: [(label, selector_value)]
        selected_value = selection[0][1]
        mapped_value = value_map.get(selected_value)

        if target_dict is None:
            # If target_dict is None, the "key" is a session variable to update in state
            setattr(state, key, mapped_value)
        else:
            target_dict[key] = mapped_value
        state.save_user_prefs()
    return updater


def make_bool_selector_updater(key, target_dict):
    return make_selector_updater_mapped(key, target_dict, {1: True, 0: False})


'''
 1 if skip playing initial moves, 0 if play all moves
'''



def getCurrentColorIndex():
    if positionParameters["color"] == "w":
        return 0
    if positionParameters["color"] == "b":
        return 1
    return 2


def setPlayColor(color,index):
    myColor = color[0][0]
    if myColor == "Random":
        myColor = random.choice(["White", "Black"])
    playParameters["whiteCPU"] = myColor == "Black"
    playParameters["blackCPU"] = myColor == "White"
    state.save_user_prefs()


def make_file_selector(
    key: str,
    fileNameTranformer: Optional[Callable[[str], str]] ,
    labels: List,
    initial_folder: str = ".",
    file_type: str = ".json",
    window_title: str = "Select file",
    callback: Optional[Callable] = None,
    prefix: str = "",
    create: bool = False,
):
    def choose_file():
        background = p.Surface((app.W, app.H))
        background.fill(p.Color('#000000'))

        file_selection = UIFileDialog(
            rect=p.Rect(0, 0, app.W, app.H),
            manager=app.manager,
            allow_existing_files_only= not create,
            window_title=window_title,
            initial_file_path=initial_folder,
            allowed_suffixes=[file_type],
            allow_picking_directories=False
        )

        # try/finally guarantees kill() on every exit: without it, pygame_gui keeps
        # the dialog in app.manager and other loops that call manager.draw_ui (e.g. the
        # in-game toolbar) would repaint it as a "ghost window" over the
        # chessboard.
        try:
            while True:
                time_delta = app.clock.tick(60) / 1000.0

                for event in p.event.get():
                    if event.type == p.QUIT:
                        quit()
                    if event.type == p.WINDOWCLOSE or event.type == pygame_gui.UI_WINDOW_CLOSE:
                        return

                    if event.type == pygame_gui.UI_BUTTON_PRESSED:
                        if event.ui_element == file_selection.ok_button:
                            selected = file_selection.current_file_path
                            file_name_with_ext  = os.path.basename(selected)
                            file_name, file_extension = os.path.splitext(file_name_with_ext) # <-- NEW

                            if prefix and not file_name.startswith(prefix):
                                 # The file is not valid: we show a message and do not exit
                                # print(f"Error: The file '{file_name}' does not start with 'base_'. Select a valid file.")
                                # You could also display a popup message to the user
                                # for example with pygame_gui.windows.UIMessageWindow
                                pygame_gui.windows.UIMessageWindow(
                                    html_message=f"The selected file is not valid:<br><b>{file_name}</b><br>it must start with {prefix}.",
                                    window_title="Invalid file selection",
                                    manager=app.manager,
                                    rect=p.Rect(app.W // 4, app.H // 4, app.W // 2, app.H // 2) # Position and size of the popup
                                )
                                continue


                            file_name = fileNameTranformer(file_name) if fileNameTranformer else file_name
                            if key:
                                positionParameters[key] = file_name
                                # Also remember the source folder: the user
                                # may have navigated outside the `initial_folder`
                                # (e.g. from pgn/ to endgames/) and save_game must
                                # respect that choice instead of always writing
                                # to pgn/.
                                if key == "filename":
                                    positionParameters["filename_folder"] = os.path.dirname(selected)
                                state.save_user_prefs()

                            for label in labels:
                                if label:
                                    label.set_title(file_name)

                            if callback:
                                callback(selected)

                            return
                        elif event.ui_element == file_selection.cancel_button:
                            return

                    app.manager.process_events(event)

                app.manager.update(time_delta)
                app.screen.blit(background, (0, 0))
                app.manager.draw_ui(app.screen)
                p.display.update()
        finally:
            file_selection.kill()

    return choose_file


def make_choose_course( labels: List,
            callback: Optional[Callable] = None):


    def choose_course():
        '''
        Loads a game from a selected PGN file and lets the user choose which game to load.    
        '''

        state.courses = BrainMaster.list_courses()
        total_courses = len(state.courses)
        courses_per_page = 10
        current_page = 0
        total_pages = (total_courses + courses_per_page - 1) // courses_per_page

        menu_running = True
        surface = app.screen
        def load_course_wrapper(N):
            nonlocal menu_running, labels
            state.id_course = state.courses[N]
            if callback:
                callback(state.id_course)
            for label in labels:
                 if label:
                       label.set_title(state.id_course)

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

        _load_menu = pygame_menu.Menu('Select Course', app.W, app.H, theme=small_font_theme)
        frame_width = 4 * 80 + 3 * 10  # 4 buttons of 80px + 3 margins of 10px
        frame_height = 50

        def refresh_menu():
            _load_menu.clear()
            start = current_page * courses_per_page
            end = min(start + courses_per_page, total_courses)
            for i in range(start, end):
                course = state.courses[i]
                label = f"{i+1} {course}"
                _load_menu.add.button(label, load_course_wrapper, i)

            if total_courses > courses_per_page:
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
    
    
        if state.id_course is not None:
            app.main_background()
            BS.drawEndGameText(app.screen, None, "Course selected")
            BS.update()
            app.delay(2)

    return choose_course

def addChooseCourse(menu):
    '''
    Adds a button to the menu that allows the user to choose a BrainMaster course.
    The button will open a file selector dialog and update the positionParameters["base"] variable with the selected course.
    '''
    labels = []    
    choose_course = make_choose_course(labels)
    chooseCourse = menu.add.button('Choose BrainMaster course', choose_course)
    default_value = state.id_course
    label = menu.add.button(default_value, choose_course, font_size=20, background_color=None, 
                            selection_effect=pygame_menu.widgets.NoneSelection())
    labels.append(label)


def make_base_selector(key, labels, callback=None):
    '''
    Returns a callable that opens a small pygame_menu listing only the
    base_*.json files of DATA_FOLDER as buttons. Cleaner than an OS-style
    file dialog when only those files are valid choices (no more lessons_*
    and other files shown by mistake).
    '''
    def choose():
        try:
            entries = sorted(
                os.path.splitext(f)[0].replace("base_", "")
                for f in os.listdir(DATA_FOLDER)
                if f.startswith("base_") and f.endswith(".json")
            )
        except OSError:
            entries = []

        menu = pygame_menu.Menu("Choose base file", app.W, app.H, theme=small_font_theme)
        if not entries:
            menu.add.label("No learning base found in data/.")

        def pick(name):
            if key:
                positionParameters[key] = name
                state.save_user_prefs()
            for lbl in labels:
                if lbl:
                    lbl.set_title(name)
            if callback:
                callback(name)
            menu.disable()

        for name in entries:
            menu.add.button(name, pick, name)
        menu.add.button("Cancel", menu.disable)

        surface = app.screen
        clock = p.time.Clock()
        menu.enable()
        while menu.is_enabled():
            events = p.event.get()
            for ev in events:
                if ev.type == p.QUIT:
                    p.quit()
                    sys.exit()
                if ev.type == p.KEYDOWN and ev.key == p.K_ESCAPE:
                    menu.disable()
            menu.update(events)
            if not menu.is_enabled():
                break
            surface.fill((0, 0, 0))
            menu.draw(surface)
            p.display.flip()
            clock.tick(app.FPS or 60)

    return choose


def addChooseBaseFile(menu):
    '''
    Adds a button to the menu that allows the user to choose a base file.
    The button opens a small pygame_menu listing only base_*.json files from
    DATA_FOLDER (no more lessons_* or unrelated files) and updates
    positionParameters["base"] with the selected one.
    '''
    labels = []
    chooseBaseFile = make_base_selector("base", labels)
    menu.add.button('Choose base file', chooseBaseFile)
    default_value = str(positionParameters.get("base", "No selection"))
    label = menu.add.button(default_value, chooseBaseFile, font_size=20, background_color=None,
                            selection_effect=pygame_menu.widgets.NoneSelection())
    labels.append(label)


def make_pgn_folder_selector(key, folder, labels, window_title="Choose PGN file", callback=None):
    '''
    Returns a callable that opens a small pygame_menu listing ONLY the *.pgn files
    of `folder` as buttons. Unlike the OS file dialog it cannot navigate elsewhere,
    so the chosen name always belongs to `folder` and stays reloadable next time.
    The pick is stored under the per-mode `key` (e.g. "openings_filename").
    '''
    def choose():
        try:
            entries = sorted(
                os.path.splitext(f)[0]
                for f in os.listdir(folder)
                if f.lower().endswith(".pgn")
            )
        except OSError:
            entries = []

        menu = pygame_menu.Menu(window_title, app.W, app.H, theme=small_font_theme)
        if not entries:
            menu.add.label(f"No PGN file in {os.path.basename(folder.rstrip(os.sep))}/.")

        def pick(name):
            positionParameters[key] = name
            state.save_user_prefs()
            for lbl in labels:
                if lbl:
                    lbl.set_title(name)
            if callback:
                callback(name)
            menu.disable()

        for name in entries:
            menu.add.button(name, pick, name)
        menu.add.button("Cancel", menu.disable)

        surface = app.screen
        clock = p.time.Clock()
        menu.enable()
        while menu.is_enabled():
            events = p.event.get()
            for ev in events:
                if ev.type == p.QUIT:
                    p.quit()
                    sys.exit()
                if ev.type == p.KEYDOWN and ev.key == p.K_ESCAPE:
                    menu.disable()
            menu.update(events)
            if not menu.is_enabled():
                break
            surface.fill((0, 0, 0))
            menu.draw(surface)
            p.display.flip()
            clock.tick(app.FPS or 60)

    return choose


def addChoosePGNFromFolder(menu, folder, key, title="Choose PGN file"):
    '''
    Like addChoosePGNFile but for a mode with a FIXED folder: lists only the *.pgn
    files actually in `folder` (no OS dialog, no navigating away) and remembers the
    choice under a per-mode `key`. The shown default is validated, so it never
    displays a name that wouldn't load.
    '''
    labels = []
    chooser = make_pgn_folder_selector(key, folder, labels, window_title=title)
    menu.add.button(title, chooser)
    saved = positionParameters.get(key)
    if saved and os.path.exists(os.path.join(folder, saved + ".pgn")):
        default_value = saved
    else:
        default_value = "No selection"
    label = menu.add.button(default_value, chooser, font_size=20,
                            background_color=None,
                            selection_effect=pygame_menu.widgets.NoneSelection())
    labels.append(label)


def addChoosePGNFile(menu, folder=None, title="Choose PGN file", create=False):
    '''
    Adds a button to the menu that allows the user to choose a PGN file.
    The button will open a file selector dialog and update the positionParameters["filename"] variable with the selected file.
    `folder` defaults to `pgngamelist.PGN_FOLDER`; pass a different folder
    (e.g. the endgames/ folder) to reuse the selector in other modes.
    `create=True` lets the user type a NEW file name (not only pick an existing
    one) -- e.g. when saving a game into a brand-new PGN/opening file.
    '''
    if folder is None:
        folder = pgngamelist.PGN_FOLDER
    labels = []
    chooseModelFile = make_file_selector("filename", None , labels, folder, ".pgn", title, None, create=create)
    menu.add.button(title, chooseModelFile)
    # Only show a remembered file name if it can actually be loaded -- the file
    # exists either in this menu's folder or in the folder it was picked from.
    # Never display a name that wouldn't load (the "filename" key is shared across
    # modes, so a leftover from another folder must not look selectable here).
    _saved = positionParameters.get("filename")
    if create:
        default_value = str(_saved or "No selection")
    else:
        _folders = [folder]
        if positionParameters.get("filename_folder"):
            _folders.append(positionParameters["filename_folder"])
        _loadable = bool(_saved) and any(
            os.path.exists(os.path.join(_f, _saved + ".pgn")) for _f in _folders)
        default_value = _saved if _loadable else "No selection"
    label = menu.add.button(default_value, chooseModelFile, font_size=20,
                           background_color=None,
                           selection_effect=pygame_menu.widgets.NoneSelection())
    labels.append(label)
