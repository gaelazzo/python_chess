"""Shared helpers for the game-mode loops: the on-screen message flash and the
square-highlight colour helper. Used by every mode in this package."""
from app_context import app
import BoardScreen as BS
from GameState import GameState


def show_message(gs:GameState, text:str):
    BS.drawEndGameText(app.screen, gs, text)


def setAlfa(color, alfa):
    return [color[0],color[1],color[2], alfa]
