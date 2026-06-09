"""Tests for safe_font: the app must survive a broken Windows font registry.

The real bug (reported on the v1.2.0 exe): pygame's initsysfonts_win32 reads a
non-string value from the font registry and crashes with
``TypeError: ... not int`` on the very first SysFont call. safe_font hardens
this so the app falls back to the default font instead of dying.
"""
import sys

import pygame as p
import pytest

import pygame.sysfont  # noqa: F401  -- ensure p.sysfont is loaded
import safe_font


@pytest.fixture
def fresh_install():
    """Allow a clean (re-)install and restore the real pygame functions after."""
    real_sysfont = p.font.SysFont
    real_win32 = getattr(p.sysfont, "initsysfonts_win32", None)
    safe_font._installed = False
    yield
    p.font.SysFont = real_sysfont
    if real_win32 is not None:
        p.sysfont.initsysfonts_win32 = real_win32
    safe_font._installed = False


def test_sysfont_falls_back_when_init_crashes(fresh_install):
    """If the stock SysFont raises (corrupted registry), our wrapper returns a
    usable default font instead of propagating the crash."""
    def boom(*_a, **_k):
        raise TypeError("expected str, bytes or os.PathLike object, not int")

    p.font.SysFont = boom            # simulate the pygame bug
    safe_font.install()              # wraps `boom`
    p.font.init()

    font = p.font.SysFont("Comic Sans MS", 20, bold=True, italic=True)

    assert isinstance(font, p.font.Font)
    assert font.get_bold() is True
    assert font.get_italic() is True


def test_guarded_win32_swallows_crash(fresh_install):
    """A crashing initsysfonts_win32 is caught: the guarded version returns a
    dict (real fonts on Windows, empty elsewhere) and never raises."""
    if getattr(p.sysfont, "initsysfonts_win32", None) is None:
        pytest.skip("no initsysfonts_win32 on this pygame build")

    def boom():
        raise TypeError("not int")

    p.sysfont.initsysfonts_win32 = boom
    safe_font.install()              # wraps `boom`

    result = p.sysfont.initsysfonts_win32()

    assert isinstance(result, dict)


def test_install_is_idempotent(fresh_install):
    """Calling install() twice must not double-wrap (each call would otherwise
    capture the previous wrapper as 'original')."""
    safe_font.install()
    once = p.font.SysFont
    safe_font.install()
    assert p.font.SysFont is once


@pytest.mark.skipif(sys.platform != "win32", reason="Windows registry only")
def test_safe_init_runs_on_real_registry(fresh_install):
    """On a healthy Windows machine the fallback enumeration still works and
    finds fonts (and, by construction, skips any non-string value)."""
    result = safe_font._safe_initsysfonts_win32()
    assert isinstance(result, dict)
