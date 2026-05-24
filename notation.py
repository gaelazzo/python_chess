"""Formatted game-notation view: the whole game tree (mainline + variations)
with move glyphs and text comments, shown as a scrollable, clickable full-screen
overlay. Variations are broken onto their own indented lines (tree style).

`notation_items` is pure (no UI) and produces the token stream; `show_notation`
renders it and lets the user click a move to jump the board there.
"""
from __future__ import annotations

import sys

import pygame as p

from app_context import app
from GameState import NAG_SYMBOL

MAIN_COLOR = (235, 235, 235)
VAR_COLOR = (150, 165, 195)
COMMENT_COLOR = (120, 200, 130)
HILITE_BG = (60, 60, 105)
BG_COLOR = (20, 20, 28)


def _glyph(node) -> str:
    return "".join(NAG_SYMBOL[x] for x in sorted(node.nags) if x in NAG_SYMBOL)


def _move_text(node, force_number: bool) -> str:
    ply = node.ply()
    num = (ply + 1) // 2
    if ply % 2 == 1:                       # White just moved
        prefix = f"{num}."
    else:                                  # Black just moved
        prefix = f"{num}..." if force_number else ""
    return prefix + node.san() + _glyph(node)


def notation_items(game):
    """Flat list of tokens describing the game tree.

    Each token is (kind, text, depth, node, newline):
      kind   : 'move' | 'comment'
      node   : the move's PGN node (for 'move'; None for 'comment')
      newline: True if this token must start a new (indented) line.
    """
    items = []
    if game.comment:
        items.append(("comment", game.comment.strip(), 0, None, False))

    def walk(node, depth, force_number, start_newline):
        if not node.variations:
            return
        main = node.variations[0]
        alts = node.variations[1:]

        items.append(("move", _move_text(main, force_number), depth, main, start_newline))
        if main.comment:
            items.append(("comment", main.comment.strip(), depth, None, False))

        for alt in alts:
            items.append(("move", _move_text(alt, True), depth + 1, alt, True))
            if alt.comment:
                items.append(("comment", alt.comment.strip(), depth + 1, None, False))
            walk(alt, depth + 1, False, False)

        force_next = bool(main.comment) or bool(alts)
        walk(main, depth, force_next, start_newline=bool(alts))

    walk(game, 0, True, False)
    return items


def _layout(items, font, width):
    """Place tokens into virtual (pre-scroll) positions, wrapping long lines and
    indenting by depth. Returns (spans, total_height, line_height)."""
    line_h = font.get_linesize() + 4
    indent = 24
    margin = 24
    space_w = font.size(" ")[0]
    spans = []                      # (x, y, w, h, text, color, node)
    top = 52                        # leave room for the header bar
    x = margin
    y = top
    cur_left = margin

    def newline(depth):
        nonlocal x, y, cur_left
        cur_left = margin + depth * indent
        x = cur_left
        y += line_h

    first = True
    for kind, text, depth, node, nl in items:
        if first:
            cur_left = margin + depth * indent
            x = cur_left
            first = False
        elif nl:
            newline(depth)

        color = COMMENT_COLOR if kind == "comment" else (MAIN_COLOR if depth == 0 else VAR_COLOR)
        w = font.size(text)[0]
        if x + w > width - margin and x > cur_left:
            newline(depth)
        spans.append((x, y, w, line_h, text, color, node))
        x += w + space_w

    return spans, y + line_h + margin, line_h


def show_notation(gs):
    """Full-screen scrollable notation overlay. Clicking a move jumps the board
    to that position. Closes with V / Esc."""
    font = p.font.SysFont("Segoe UI Symbol,Cambria Math,Arial", 18)
    header_font = p.font.SysFont("Arial", 14, bold=True)
    spans, total_h, line_h = _layout(notation_items(gs.pgn), font, app.W)
    max_scroll = max(0, total_h - app.H)
    header = ("Notazione  --  <- / ->: mossa prec/succ  |  su/giu, rotella, PgUp/PgDn: scorri"
              "  |  click: vai  |  V/Esc: chiudi")

    move_nodes = [s[6] for s in spans if s[6] is not None]
    scroll = 0

    def ensure_visible(node):
        """Scroll just enough to keep `node`'s span on screen."""
        nonlocal scroll
        for (x, y, w, h, text, color, nd) in spans:
            if nd is node:
                if y - scroll < 52:
                    scroll = y - 52
                elif y + h - scroll > app.H:
                    scroll = y + h - app.H
                break

    def current_index():
        try:
            return move_nodes.index(gs.node)
        except ValueError:
            return -1

    def goto(i):
        gs.goToNode(move_nodes[i])
        ensure_visible(move_nodes[i])

    ensure_visible(gs.node)
    running = True
    while running:
        for e in p.event.get():
            if e.type == p.QUIT:
                p.quit()
                sys.exit()
            elif e.type == p.KEYDOWN:
                if e.key in (p.K_v, p.K_ESCAPE):
                    running = False
                elif e.key == p.K_LEFT and move_nodes:           # previous move
                    i = current_index()
                    goto(len(move_nodes) - 1 if i < 0 else max(0, i - 1))
                elif e.key == p.K_RIGHT and move_nodes:          # next move
                    i = current_index()
                    goto(0 if i < 0 else min(len(move_nodes) - 1, i + 1))
                elif e.key == p.K_DOWN:
                    scroll += line_h
                elif e.key == p.K_UP:
                    scroll -= line_h
                elif e.key == p.K_PAGEDOWN:
                    scroll += app.H - line_h
                elif e.key == p.K_PAGEUP:
                    scroll -= app.H - line_h
                elif e.key == p.K_HOME:
                    scroll = 0
                elif e.key == p.K_END:
                    scroll = max_scroll
            elif e.type == p.MOUSEWHEEL:
                scroll -= e.y * line_h * 3
            elif e.type == p.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                for (x, y, w, h, text, color, node) in spans:
                    if node is not None and p.Rect(x, y - scroll, w, h).collidepoint(mx, my):
                        gs.goToNode(node)
                        running = False
                        break

        scroll = max(0, min(scroll, max_scroll))

        app.screen.fill(BG_COLOR)
        for (x, y, w, h, text, color, node) in spans:
            sy = y - scroll
            if sy + h < 0 or sy > app.H:
                continue
            if node is not None and node is gs.node:
                p.draw.rect(app.screen, HILITE_BG, p.Rect(x - 2, sy, w + 4, h))
            app.screen.blit(font.render(text, True, color), (x, sy))
        # header bar on top
        p.draw.rect(app.screen, (38, 38, 52), p.Rect(0, 0, app.W, 40))
        app.screen.blit(header_font.render(header, True, (210, 210, 170)), (16, 12))
        p.display.flip()
