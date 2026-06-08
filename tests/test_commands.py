"""Input port: a scripted command stream drives the controller exactly like the
keyboard/mouse would -- the same BoardSession.apply() path, a different source.

This is the e2e shape the modes are heading toward: feed commands, assert on the
view-model. No pygame, no display.
"""
import pygame as p

from GameState import Move
from modes.board_session import BoardSession, AnalysisPolicy
from modes.commands import ScriptedInput, do, click, QUIT
from modes.pygame_input import PygameInput

_R = Move.ranksToRows
_C = Move.filesToCols


def sq(name):
    return (_R[name[1]], _C[name[0]])


def test_scripted_commands_drive_the_session():
    s = BoardSession(AnalysisPolicy())
    src = ScriptedInput([click(*sq("e2")), click(*sq("e4")), do("undo")])
    for cmd in src.poll():
        s.apply(cmd)
    assert s.gs.moveLog == []                  # e4 played, then undone
    assert src.poll() == []                    # the source drained


def test_apply_click_returns_the_move():
    s = BoardSession(AnalysisPolicy())
    assert s.apply(click(*sq("e2"))) is None   # first click just selects
    moved = s.apply(click(*sq("e4")))          # second click completes the move
    assert moved is not None and moved.uci == "e2e4"
    assert "e4" in s.view_model().notation


def test_do_command_toggles_a_panel():
    s = BoardSession(AnalysisPolicy())
    s.apply(do("book"))
    assert s.view_model().panels["book"] is True


def test_quit_command_stops_the_session():
    s = BoardSession(AnalysisPolicy())
    assert s.running is True
    s.apply(QUIT)
    assert s.running is False


def test_pygame_input_translates_keys_clicks_and_quit():
    """The mouse/keyboard arm of the port: pygame events -> the same Commands."""
    p.init()
    pi = PygameInput({p.K_LEFT: "undo", p.K_b: "book"})
    assert pi.translate(p.event.Event(p.KEYDOWN, key=p.K_LEFT)) == do("undo")
    assert pi.translate(p.event.Event(p.KEYDOWN, key=p.K_b)) == do("book")
    assert pi.translate(p.event.Event(p.KEYDOWN, key=p.K_z)) is None       # unmapped key
    assert pi.translate(p.event.Event(p.QUIT)) == QUIT
    left_click = pi.translate(p.event.Event(p.MOUSEBUTTONDOWN, button=1, pos=(10, 10)))
    assert left_click is not None and left_click.kind == "click"
    assert pi.translate(p.event.Event(p.MOUSEBUTTONDOWN, button=3, pos=(10, 10))) is None
