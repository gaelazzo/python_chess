"""Make pygame's font system robust on Windows machines with a broken font
registry.

Background
----------
``pygame.font.SysFont`` loads *system* fonts. On Windows it enumerates the
values under ``HKLM/HKCU \\...\\CurrentVersion\\Fonts`` and, for each one, runs
``os.path.splitext(font_filename)``. ``winreg.EnumValue`` returns the value's
*data*, which is normally a string (``"arial.ttf"``) -- but on some installs one
of those registry values holds an int (e.g. a stray ``REG_DWORD``). Then
``splitext(<int>)`` raises ``TypeError: expected str, bytes or os.PathLike
object, not int`` and the *first* ``SysFont(...)`` call crashes the whole app.

This is a pygame bug (``initsysfonts_win32``), not a packaging issue: the fonts
come from the user's registry at runtime, so it depends on the machine, not on
the build. It reproduces from source too on an affected machine, and only on
machines whose registry has such a value -- which is why it "works on my PC".

Fix
---
``install()`` adds two layers of defense, both no-ops on healthy machines:

1. a guarded ``initsysfonts_win32`` that runs the original and, only if it
   raises, falls back to a copy that skips non-string registry values (so the
   one bad entry is ignored and the other system fonts still load);
2. a ``SysFont`` wrapper that, if font init still fails for any reason, returns
   pygame's built-in default font instead of letting the exception propagate.

The app keeps running; at worst it falls back to the default font.
"""
import os

import pygame

_installed = False


def _safe_initsysfonts_win32():
    """Copy of ``pygame.sysfont.initsysfonts_win32`` that ignores registry
    values whose data is not a string -- the cause of the crash. Used only as a
    fallback after the stock function has already raised, so on healthy machines
    this code never runs."""
    import winreg
    from os.path import join, splitext, dirname, exists

    sf = pygame.sysfont
    fontdir = join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    fonts = {}
    font_dirs = [
        "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts",
        "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Fonts",
    ]
    for domain in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for font_dir in font_dirs:
            try:
                key = winreg.OpenKey(domain, font_dir)
            except FileNotFoundError:
                continue
            for i in range(winreg.QueryInfoKey(key)[1]):
                try:
                    name, font, _ = winreg.EnumValue(key, i)
                except OSError:
                    break
                # The bug: a corrupted registry can hand us an int here.
                if not isinstance(font, str) or not isinstance(name, str):
                    continue
                if splitext(font)[1].lower() not in sf.OpenType_extensions:
                    continue
                if not dirname(font):
                    font = join(fontdir, font)
                for nm in name.split("&"):
                    if exists(font):
                        sf._parse_font_entry_win(nm, font, fonts)
    return fonts


def _make_default_font(size, bold, italic):
    """pygame's built-in font (always bundled), styled to match the request."""
    font = pygame.font.Font(None, size)
    try:
        font.set_bold(bool(bold))
        font.set_italic(bool(italic))
    except Exception:
        pass
    return font


def install():
    """Idempotently harden pygame's font loading. Call once, before the first
    ``SysFont``."""
    global _installed
    if _installed:
        return
    _installed = True

    sf = getattr(pygame, "sysfont", None)
    orig_init_win32 = getattr(sf, "initsysfonts_win32", None)
    if sf is not None and orig_init_win32 is not None:

        def _guarded_win32():
            try:
                return orig_init_win32()
            except Exception:
                try:
                    return _safe_initsysfonts_win32()
                except Exception:
                    return {}

        sf.initsysfonts_win32 = _guarded_win32

    orig_sysfont = pygame.font.SysFont

    def _safe_sysfont(name, size, bold=False, italic=False, constructor=None):
        try:
            return orig_sysfont(name, size, bold, italic, constructor)
        except Exception:
            return _make_default_font(size, bold, italic)

    pygame.font.SysFont = _safe_sysfont
