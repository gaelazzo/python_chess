"""Pre-render the toolbar emoji into colour PNG icons.

pygame/SDL_ttf renders the Windows emoji font only in black & white, so instead
of drawing the emoji live we bake each one into a colour PNG here (Pillow DOES
read the COLR/CPAL colour tables of Segoe UI Emoji via ``embedded_color=True``)
and the toolbar just blits the resulting surface.

Run once (and again whenever the icon set changes):

    python tools/generate_icons.py

Output: images/icons/<name>.png, square RGBA, transparent background.
Monochrome glyphs (chess king, the media-control arrows) come out as dark
silhouettes -- which is exactly what we want for the navigation arrows.
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

EMOJI_FONT = r"C:\Windows\Fonts\seguiemj.ttf"   # Segoe UI Emoji (colour)
SYMBOL_FONT = r"C:\Windows\Fonts\seguisym.ttf"  # Segoe UI Symbol (mono fallback)

# name -> emoji, or (emoji, font_path) when the colour-emoji font lacks the glyph
# (e.g. the chess king is only in Segoe UI Symbol). The name is what the toolbar
# references; keep it stable.
ICONS = {
    # top toolbar -- in-game tools
    "open":       "\U0001F4C2",  # open folder
    "save":       "\U0001F4BE",  # floppy disk
    "statistics": "\U0001F4CA",  # bar chart
    "variations": "\U0001F333",  # tree
    "pgn":        "\U0001F4CB",  # clipboard (PGN move-list panel)
    # top toolbar -- annotation / edit group (separate cluster, analysis only)
    "annotate":   "❗",      # annotate last move (NAG: ! ? !? ...)
    "comment":    "\U0001F4AC",  # speech balloon (text comment)
    "addtac":     "\U0001F9E9",  # puzzle piece (save position as tactic)
    "editpos":    "✏",      # pencil (edit position / setup board)
    "truncate":   "✂",      # scissors (truncate moves after here)
    "delvar":     "\U0001F5D1",  # wastebasket (delete the variation)
    "promote":    "⬆",      # up arrow (promote variation to main line)
    # training modes (replay / openings / endgames / brainmaster)
    "home":       "\U0001F3E0",  # house (back/quit to menu)
    "hint":       "\U0001F4A1",  # light bulb (show solution / correct move)
    "nextitem":   "⏩",      # fast-forward (next exercise / game / question)
    "moremoves":  "➕",      # heavy plus (show more continuation moves)
    # "engine" is drawn (a classic CPU chip), not an emoji -- see _render_cpu_icon.
    "flip":       "\U0001F503",  # clockwise vertical arrows (Segoe maps 1F504 to "END")
    "lock":       "\U0001F512",  # closed padlock (Lock side: fix the board orientation)
    "help":       "❓",      # question mark
    "ideas":      "\U0001F4AD",  # thought balloon (edit opening ideas / plans)
    "analyze":    "\U0001F50E",  # magnifier (analyze typical plans from masters)
    "db":         "\U0001F441",  # eye (Lichess games database: straight stats lookup)
    "twins":      "\U0001F500",  # twisted arrows / shuffle (cycle to a transposed twin)
    "watch":      "\U0001F4FA",  # television (follow a live board shown on screen)
    # top toolbar -- mode launchers (generated now, wired in a later iteration)
    "learning":   "\U0001F9E0",  # brain
    "openings":   "\U0001F4D6",  # open book
    "endgames":   ("♚", SYMBOL_FONT),  # black chess king (not in the emoji font)
    "solve":      "\U0001F3AF",  # direct hit / target
    "tactics":    "⚡",      # high voltage
    "settings":   "⚙",      # gear
    "download":   "\U0001F4E5",  # inbox tray (down arrow into tray)
    # bottom toolbar -- navigation
    "first":      "⏮",      # last-track button (|<<)
    "prev":       "◀",      # left-pointing triangle
    "next":       "▶",      # right-pointing triangle
    "last":       "⏭",      # next-track button (>>|)
}

FONT_CANDIDATES = [EMOJI_FONT, SYMBOL_FONT]

CANVAS = 128          # render big, the toolbar scales down for crisp results
GLYPH = 116           # font size; a little padding inside the canvas


# Text-badge icons: a coloured rounded square with a short label. Used where no
# emoji is distinct enough -- e.g. Copy FEN vs Copy PGN (the clipboard emoji is
# already the PGN-panel toggle). name -> (label, background colour).
TEXT_BADGES = {
    "copyfen": ("FEN", (0, 150, 136)),     # teal
    "copypgn": ("PGN", (230, 126, 34)),    # orange
}
_BOLD_FONTS = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]

_FONT_CACHE: dict = {}


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    if path is None or not os.path.exists(path):
        path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
    if path is None:
        raise SystemExit("No emoji font found (looked for Segoe UI Emoji/Symbol).")
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def _bold_font(size: int) -> ImageFont.FreeTypeFont:
    path = next((p for p in _BOLD_FONTS if os.path.exists(p)), None)
    key = (path or "default", size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = (ImageFont.truetype(path, size) if path
                            else ImageFont.load_default())
    return _FONT_CACHE[key]


def _render_cpu_icon() -> Image.Image:
    """A classic CPU / processor chip: a square body with pins on all four sides
    and a coloured core. Drawn here because there is no clean 'CPU chip' emoji
    (the engine button used the desktop-computer emoji before)."""
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body = (58, 70, 92, 255)       # slate chip body
    core = (74, 144, 226, 255)     # blue core (matches the app's accent)
    pin = (150, 158, 172, 255)     # metallic pins
    b0, b1 = 34, 94                # body square, leaving room for the pins
    pin_len, pin_w, n = 14, 10, 4
    span = b1 - b0
    for i in range(n):
        c = int(b0 + span * (i + 1) / (n + 1))
        d.rectangle([c - pin_w // 2, b0 - pin_len, c + pin_w // 2, b0], fill=pin)   # top
        d.rectangle([c - pin_w // 2, b1, c + pin_w // 2, b1 + pin_len], fill=pin)   # bottom
        d.rectangle([b0 - pin_len, c - pin_w // 2, b0, c + pin_w // 2], fill=pin)   # left
        d.rectangle([b1, c - pin_w // 2, b1 + pin_len, c + pin_w // 2], fill=pin)   # right
    d.rounded_rectangle([b0, b0, b1, b1], radius=10, fill=body)
    m = 15
    d.rounded_rectangle([b0 + m, b0 + m, b1 - m, b1 - m], radius=6, fill=core)
    return img


def _render_badge(label: str, bg) -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = 4
    draw.rounded_rectangle([pad, pad, CANVAS - pad, CANVAS - pad],
                           radius=22, fill=tuple(bg) + (255,))
    size = 70
    while size > 10:
        f = _bold_font(size)
        l, t, r, b = draw.textbbox((0, 0), label, font=f)
        if (r - l) <= CANVAS * 0.74 and (b - t) <= CANVAS * 0.58:
            break
        size -= 2
    draw.text((CANVAS // 2, CANVAS // 2), label, font=_bold_font(size),
              anchor="mm", fill=(255, 255, 255, 255))
    return img


def main() -> None:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(here, "images", "icons")
    os.makedirs(out_dir, exist_ok=True)

    for name, spec in ICONS.items():
        emoji, font_path = spec if isinstance(spec, tuple) else (spec, EMOJI_FONT)
        font = _font(font_path, GLYPH)
        img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Black fill is only used for monochrome glyphs; colour glyphs ignore it.
        try:
            draw.text((CANVAS // 2, CANVAS // 2), emoji, font=font,
                      anchor="mm", embedded_color=True, fill=(40, 40, 40, 255))
        except TypeError:
            # very old Pillow without embedded_color
            draw.text((CANVAS // 2, CANVAS // 2), emoji, font=font,
                      anchor="mm", fill=(40, 40, 40, 255))
        # Trim to the glyph's bounding box, then re-centre on a square canvas so
        # narrow glyphs (king, arrows) aren't tiny next to the wide ones.
        bbox = img.getbbox()
        if bbox:
            glyph = img.crop(bbox)
            side = max(glyph.size)
            square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            square.paste(glyph, ((side - glyph.width) // 2,
                                 (side - glyph.height) // 2))
            img = square.resize((CANVAS, CANVAS), Image.LANCZOS)
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path)
        print(f"  {name:11s} -> {path}")

    for name, (label, bg) in TEXT_BADGES.items():
        path = os.path.join(out_dir, f"{name}.png")
        _render_badge(label, bg).save(path)
        print(f"  {name:11s} -> {path}")

    # Drawn icons (no suitable emoji).
    engine_path = os.path.join(out_dir, "engine.png")
    _render_cpu_icon().save(engine_path)
    print(f"  {'engine':11s} -> {engine_path}")

    print(f"Done: {len(ICONS) + len(TEXT_BADGES) + 1} icons in {out_dir}")


if __name__ == "__main__":
    main()
