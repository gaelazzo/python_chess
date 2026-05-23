"""Shared test setup.

Forces pygame into headless mode (so importing the UI modules never needs a
display), and snapshots/restores the mutable session state around every test so
tests can't leak into one another.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest


@pytest.fixture(autouse=True)
def restore_state():
    """Restore state.* mutable globals after each test."""
    import state
    play = dict(state.playParameters)
    pos = dict(state.positionParameters)
    scalars = {k: getattr(state, k)
               for k in ("num_moves_to_show", "play_position", "id_course", "courses")}
    yield
    state.playParameters.clear()
    state.playParameters.update(play)
    state.positionParameters.clear()
    state.positionParameters.update(pos)
    for k, v in scalars.items():
        setattr(state, k, v)
