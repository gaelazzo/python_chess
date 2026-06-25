"""Typical opening plans from the Lichess MASTERS explorer, by MOVES PLAYED.

Method (as specified by the user):
  * source = Lichess masters (NOT the user's own games);
  * look at the MOVES played and their percentages -- NOT the final position;
  * fixed-depth search from the structure position (a development window of N
    plies), enumerate the lines, each weighted by its path probability;
  * per side (disjoint), find the groups of moves played TOGETHER in at least a
    support threshold of the lines (maximal frequent itemsets), ranked by that
    relative frequency. Those groups are the typical plans. Castling is just a
    move (O-O), counted like any other.

Runs in a background thread (network + throttle); the game loop poll()s it.
"""
from __future__ import annotations

import threading
from itertools import combinations
from typing import Optional, Tuple

import chess

import lichess_plans as LP
import opening_ideas as OI

# Fixed-depth development window + branching. No arbitrary request cap: the size
# is bounded by depth, branching (max_branch / min_share) and the masters data
# (min_games). max_nodes is only a generous runaway safety.
_DEPTH = 8           # FIXED depth in plies (4 moves each side)
_MIN_SHARE = 0.12    # follow moves played in >= 12% of games at a node
_MIN_GAMES = 20      # don't follow into positions with too little master data
_MAX_BRANCH = 3
_THROTTLE = 0.2
_MAX_NODES = 600     # runaway safety only (not a method parameter)
_MIN_SUPPORT = 0.20  # a move/bundle must be played in >= this share of lines

_state = {"busy": False, "result": None, "board": None, "progress": ""}


def token_ready() -> bool:
    return bool(LP.resolve_token())


def is_busy() -> bool:
    return _state["busy"]


def progress() -> str:
    """The line currently being queried (SANs of the path), for a live banner."""
    return _state.get("progress", "")


def _report_progress(path) -> None:
    _state["progress"] = " ".join(path) if path else "(root)"


def start(board: chess.Board) -> bool:
    """Launch the masters analysis for `board` in the background."""
    if _state["busy"]:
        return False
    _state.update(busy=True, result=None, board=board, progress="(start)")
    fen = board.fen()

    # Read the (Setup-configurable) parameters; fall back to the module defaults.
    from config import config
    depth = int(getattr(config, "plan_depth", None) or _DEPTH)
    min_share = float(getattr(config, "plan_min_share", None) or _MIN_SHARE)
    min_games = int(getattr(config, "plan_min_games", None) or _MIN_GAMES)
    max_branch = int(getattr(config, "plan_max_branch", None) or _MAX_BRANCH)

    def work():
        try:
            tree = LP.explore(fen, depth=depth, min_share=min_share,
                              min_games=min_games, max_branch=max_branch,
                              throttle=_THROTTLE, max_nodes=_MAX_NODES,
                              on_progress=_report_progress)
            _state["result"] = ("done", tree)
        except Exception as e:
            _state["result"] = ("error", str(e))
        finally:
            _state["busy"] = False

    threading.Thread(target=work, daemon=True, name="plan-miner").start()
    return True


def poll() -> Optional[Tuple[str, str]]:
    """Called every frame. Returns ('done', text) / ('error', msg) once, else None."""
    r = _state["result"]
    if r is None:
        return None
    _state["result"] = None
    _state["progress"] = ""          # analysis finished -> clear the banner text
    _state["dossier_saved"] = False
    _state["dossier_pending"] = None
    _state["variants"] = []
    kind, payload = r
    if kind == "error":
        return ("error", payload)
    board = _state["board"]
    text = format_suggestions(payload, board)
    try:
        summary = _summarize(payload, board)
        OI.set_mined(board, summary)
        # per-variant moves for the on-board arrows (numbered [1..N] in the popup)
        _state["variants"] = [{"mover": c.get("mover_moves", []), "resp": c.get("resp_moves", [])}
                              for c in summary["conditional"]]
        # Pre-fill the editable plan lists (no copy-paste needed) AND store the
        # full report in notes (read-only).
        content = {
            "plans_white": [b["moves"] for b in summary["white"]["bundles"]],
            "plans_black": [b["moves"] for b in summary["black"]["bundles"]],
            "notes": text,
        }
        updated = {**OI.get_dossier(board), **content}
        if OI.has_dossier(board):
            _state["dossier_pending"] = (board, updated)      # exists -> offer an Update button
        else:
            OI.set_dossier(board, updated)                    # no entry yet -> auto-create it
            _state["dossier_saved"] = True
    except Exception:
        pass
    return ("done", text)


def variants():
    """Per numbered plan [1..N]: {'mover': [san...], 'resp': [san...]} -- the
    moves to draw as arrows when the user presses that number in the popup."""
    return _state.get("variants", [])


def analyzed_board():
    """The board the last analysis was run on (for converting plan SANs to squares)."""
    return _state.get("board")


def dossier_saved() -> bool:
    """True if the last poll() auto-created the structure's dossier from masters."""
    return bool(_state.get("dossier_saved"))


def dossier_pending() -> bool:
    """True if a dossier already exists and an Update-from-masters is available."""
    return _state.get("dossier_pending") is not None


def apply_dossier_update() -> None:
    """Refresh the existing dossier's notes with the last masters report,
    PRESERVING the user's curated plan lists."""
    pend = _state.get("dossier_pending")
    if pend:
        OI.set_dossier(pend[0], pend[1])
        _state["dossier_pending"] = None


def _lines(tree: dict, root_white_to_move: bool):
    """Enumerate the lines (root->terminal paths) of the fixed-depth tree. Each
    line -> (white_moves, black_moves, weight, leaf_score, leaf_wdl), collecting
    the MOVES PLAYED (SAN) per side. `leaf_score`/`leaf_wdl` are the masters'
    result at the line's terminal position (White POV; score None if no data).
    Castling is just its SAN (O-O), like any move.

    `weight` is the line's PATH PROBABILITY (product of the move shares). This is
    a proper probability measure: support is a relative frequency, and the
    conditional step (P(opponent plan | mover plan)) normalises by the subset, so
    they are conditional relative frequencies. We deliberately do NOT weight by
    the explorer's per-position game total at the leaf: that double-counts
    transpositions (a transposed position is counted once per incoming path; the
    leaf-game sum came to 9874 > 6292 root games). Absolute game counts, if ever
    wanted, are path_prob x root_total -- same relative frequencies, no double
    count. The unexplored tail (pruned rare moves) just makes the total < 1."""
    out = []

    def walk(node, depth, wset, bset, prob):
        children = node.get("children", [])
        if not children:
            sc = node.get("score") if node.get("total", 0) else None   # None = no master data here
            out.append((frozenset(wset), frozenset(bset), prob, sc, node.get("wdl", (0.0, 0.0, 0.0))))
            return
        for c in children:
            is_white = ((depth % 2 == 0) == root_white_to_move)
            walk(c["node"], depth + 1,
                 wset | {c["san"]} if is_white else wset,
                 bset | {c["san"]} if not is_white else bset,
                 prob * c["share"])

    walk(tree, 0, set(), set(), 1.0)
    return out


def _mine_bundles(transactions, min_support=_MIN_SUPPORT, max_size=4):
    """Weighted frequent-itemset mining over move-sets. A 'plan' is a group of
    moves played TOGETHER in at least `min_support` of the lines -- a real joint
    relative frequency. The group is grown move by move while it stays above the
    threshold (support is anti-monotone: each added move can only lower it), so
    its SIZE is not chosen, it is the largest still-frequent group along that
    branch. We keep the MAXIMAL groups (no still-frequent superset) and rank them
    by support. `max_size` is just a search ceiling. Returns the maximal bundles
    as (set, support), plus the singleton supports."""
    total = sum(w for _, w in transactions) or 1.0
    sup1: dict = {}
    for fs, w in transactions:
        for f in fs:
            sup1[f] = sup1.get(f, 0.0) + w
    for f in list(sup1):
        sup1[f] /= total

    def support(itemset):
        return sum(w for fs, w in transactions if itemset <= fs) / total

    levels = {1: {frozenset([f]) for f, s in sup1.items() if s >= min_support}}
    frequent = set(levels[1])
    size = 1
    while levels[size] and size < max_size:
        cur = list(levels[size])
        cand = set()
        for i in range(len(cur)):
            for j in range(i + 1, len(cur)):
                u = cur[i] | cur[j]
                if len(u) == size + 1 and all(frozenset(s) in levels[size]
                                              for s in combinations(u, size)):
                    cand.add(u)
        nxt = {c for c in cand if support(c) >= min_support}
        frequent |= nxt
        levels[size + 1] = nxt
        size += 1

    kept = [(c, support(c)) for c in frequent if len(c) >= 2]
    maximal = [k for k in kept if not any(k[0] < o[0] for o in kept)]
    maximal.sort(key=lambda x: (-x[1], -len(x[0])))    # by relative frequency (support)
    return maximal, sup1


def _ply_orders(tree: dict, mover_white: bool):
    """Per side, the weighted-mean PLY at which each move (SAN) is played, so a
    bundle can be rendered in PLAY ORDER instead of alphabetically."""
    acc = {True: {}, False: {}}    # is_white -> {san: [sum(ply*w), sum(w)]}

    def walk(node, depth, prob):
        for c in node.get("children", []):
            np = prob * c["share"]
            is_white = ((depth % 2 == 0) == mover_white)
            d = acc[is_white].setdefault(c["san"], [0.0, 0.0])
            d[0] += depth * np
            d[1] += np
            walk(c["node"], depth + 1, np)

    walk(tree, 0, 1.0)
    reduce = lambda m: {k: v[0] / v[1] for k, v in m.items() if v[1]}
    return reduce(acc[True]), reduce(acc[False])   # (white_order, black_order)


def _render_moves(factset, order=None) -> str:
    """Join the moves of a bundle. With `order` (san -> mean ply) they come out
    in PLAY ORDER; otherwise alphabetical."""
    if order is None:
        return " + ".join(sorted(factset))
    return " + ".join(sorted(factset, key=lambda s: (order.get(s, 99.0), s)))


def _side_plan(transactions, min_support: float, order=None, max_shown: int = 5, max_size: int = 4) -> dict:
    bundles, sup1 = _mine_bundles(transactions, min_support=min_support, max_size=max_size)
    plans = [{"moves": _render_moves(fs, order), "support": round(sup, 2)}
             for fs, sup in bundles[:max_shown]]
    spots = [{"move": m, "support": round(s, 2)}
             for m, s in sorted(sup1.items(), key=lambda kv: -kv[1]) if s >= min_support][:8]
    return {"bundles": plans, "spots": spots}


def _dest_square(san: str):
    """Destination square of a SAN move ('fxe5'->'e5', 'Nxc3'->'c3', 'e8=Q'->'e8'),
    or None for castling."""
    s = san.rstrip("+#")
    if s.startswith("O-O"):
        return None
    if "=" in s:
        s = s.split("=")[0]
    if len(s) >= 2 and s[-2] in "abcdefgh" and s[-1] in "12345678":
        return s[-2:]
    return None


def _trigger_move(square, mover_sup1, thr):
    """The MOVER move that put a piece on `square` -- i.e. the move that makes a
    responder capture there possible (...e5 enabling fxe5, ...Nxc3 enabling bxc3).
    Highest-support such move above `thr`, else None."""
    if not square:
        return None
    cands = [(m, s) for m, s in mover_sup1.items()
             if s >= thr and "O-O" not in m and _dest_square(m) == square]
    return max(cands, key=lambda ms: ms[1])[0] if cands else None


def _render_response(subset, o_idx, mover_sup1, opp_order, ms2, mover_label,
                     responder_white, plan_set=frozenset(), max_size: int = 4):
    """Human-readable responder line for one mover plan. The replies are mined as
    BUNDLES (co-occurring move-sets): mutually-exclusive choices (e.g. ...Na6 vs
    ...Nc6, same knight) land in DIFFERENT bundles, so they show as ALTERNATIVES
    ('... or ...'), never as a contradictory 'core + then'. We factor the moves
    common to all shown bundles as a shared prefix, list the rest as alternatives,
    pull responder captures out as conditional clauses, append a full W/D/L (White
    POV) and -- if one alternative scores best for the responder -- a note."""
    opp_tx = [(L[o_idx], L[2]) for L in subset]
    opp_bundles, opp_sup1 = _mine_bundles(opp_tx, ms2, max_size=max_size)

    # responder captures whose enabling mover move is NOT in the plan -> clauses
    cap_by_trigger, captures = {}, set()
    for m, s in opp_sup1.items():
        if s >= ms2 and "x" in m:
            trig = _trigger_move(_dest_square(m), mover_sup1, ms2)
            if trig and trig not in plan_set:
                cap_by_trigger.setdefault(trig, []).append((s, m))
                captures.add(m)

    # the responder's alternative setups (top bundles), captures stripped out
    bsets = []
    for fs, _s in opp_bundles[:3]:
        b = set(fs) - captures
        if b and b not in bsets:
            bsets.append(b)
    if not bsets:                                   # no bundle -> top non-capture moves
        top = [m for m, s in sorted(opp_sup1.items(), key=lambda kv: -kv[1])
               if s >= ms2 and m not in captures][:3]
        bsets = [set(top)] if top else []

    core = set.intersection(*bsets) if bsets else set()
    rlabel = "White" if responder_white else "Black"

    # Each alternative setup gets ITS OWN W/D/L (White POV, over the lines that
    # play that setup) -- so the figures clearly belong to a specific reply, not
    # to the whole plan (which would just repeat the plan's own score).
    alts = []   # (rendered_rest, wdl_white, responder_score, rest_frozen)
    for b in bsets:
        rest = b - core
        if not rest:
            continue
        lines_b = [L for L in subset if b <= L[o_idx]]
        sw = _avg_score(lines_b)
        alts.append((_render_moves(frozenset(rest), opp_order), _avg_wdl(lines_b),
                     _pov(sw, responder_white) if sw is not None else None, frozenset(rest)))
    alts.sort(key=lambda a: a[0])   # determinism

    def _wdl(w):
        return f" (W{w[0]*100:.0f}/D{w[1]*100:.0f}/L{w[2]*100:.0f})" if w else ""

    parts = []
    if core:
        parts.append(_render_moves(frozenset(core), opp_order))
    if alts:
        parts.append(("then " if core else "")
                     + " or ".join(rendered + _wdl(w) for rendered, w, _sc, _rf in alts))
    text = ", ".join(parts) or "(varied)"

    for trig, caps in sorted(cap_by_trigger.items(), key=lambda kv: -max(s for s, _ in kv[1]))[:2]:
        cap_str = " or ".join(dict.fromkeys(c for _, c in sorted(caps, key=lambda x: -x[0])))
        text = f"{text}, and if {mover_label} plays {trig} then {cap_str}"

    # among the alternative setups, which scores best FOR THE RESPONDER?
    scored_alts = [a for a in alts if a[2] is not None]
    if len(scored_alts) >= 2:
        scored_alts.sort(key=lambda a: -a[2])
        if scored_alts[0][2] - scored_alts[1][2] > 0.02:
            text += f"\n   {rlabel} does best with {scored_alts[0][0]} ({rlabel} {scored_alts[0][2]*100:.0f}%)"

    # moves to draw as arrows: the shared core + the best (or first) alternative
    best_rest = set(scored_alts[0][3]) if scored_alts else (set(alts[0][3]) if alts else set())
    resp_moves = sorted(core | best_rest, key=lambda m: (opp_order.get(m, 99.0) if opp_order else 0.0, m))
    return text, resp_moves


def _pov(score_white: float, white: bool) -> float:
    """A White-POV score seen from the given side."""
    return score_white if white else 1.0 - score_white


def _avg_score(lines):
    """UNWEIGHTED mean of the White-POV leaf scores over `lines` -- each line
    counts once, NOT frequency-weighted (frequency is already captured by support;
    the score just measures how good the resulting positions are). None if no data."""
    vals = [L[3] for L in lines if len(L) > 3 and L[3] is not None]
    return sum(vals) / len(vals) if vals else None


def _avg_wdl(lines):
    """UNWEIGHTED mean of the (W, D, L) leaf fractions (White POV). None if no data."""
    vals = [L[4] for L in lines if len(L) > 4 and len(L) > 3 and L[3] is not None]
    if not vals:
        return None
    n = len(vals)
    return tuple(sum(v[i] for v in vals) / n for i in range(3))


def _conditional(lines, mover_white: bool, ms1: float, ms2: float,
                 mover_order=None, opp_order=None, max_shown: int = 5, max_size: int = 4):
    """Step 1: the MOVER's plans over all lines. Step 2: for each mover plan, the
    OPPONENT's typical response WITHIN the lines that contain that plan (relaxed
    support ms2, because the subset is smaller), rendered by _render_response.
    Returns a list of {plan, support, n_lines, response}."""
    w_idx, o_idx = (0, 1) if mover_white else (1, 0)
    mover_label = "White" if mover_white else "Black"
    responder_white = not mover_white
    mover_plans, _ = _mine_bundles([(L[w_idx], L[2]) for L in lines], ms1, max_size=max_size)
    out = []
    for plan_set, sup in mover_plans[:max_shown]:
        subset = [L for L in lines if plan_set <= L[w_idx]]
        _, mover_sup1 = _mine_bundles([(L[w_idx], L[2]) for L in subset], ms2, max_size=max_size)
        sw = _avg_score(subset)                          # plan score (unweighted), mover POV
        mover_score = _pov(sw, mover_white) if sw is not None else None
        response, resp_moves = _render_response(subset, o_idx, mover_sup1, opp_order, ms2,
                                                mover_label, responder_white, plan_set, max_size=max_size)
        mover_moves = sorted(plan_set, key=lambda m: (mover_order.get(m, 99.0) if mover_order else 0.0, m))
        out.append({"plan": _render_moves(plan_set, mover_order), "support": round(sup, 2),
                    "n_lines": len(subset), "mover_score": mover_score, "response": response,
                    "mover_moves": mover_moves, "resp_moves": resp_moves})
    return out


def _summarize(tree: dict, board: chess.Board) -> dict:
    from config import config
    ms = float(getattr(config, "plan_min_support", None) or _MIN_SUPPORT)
    n = int(getattr(config, "plan_max_shown", None) or 3)   # how many plans to list
    depth = int(getattr(config, "plan_depth", None) or _DEPTH)
    msize = max(4, depth // 2)   # bundle cap = moves per side, so a universal move (Bg7) is never dropped
    mover_white = board.turn == chess.WHITE
    lines = _lines(tree, mover_white)
    worder, border = _ply_orders(tree, mover_white)        # play-order per side
    mover_order, opp_order = (worder, border) if mover_white else (border, worder)

    # A deep/wide search spreads support over many diverse lines, so even the top
    # move pair can fall below min_support. Rather than give up, relax the support
    # threshold step by step until the strongest recurring plan(s) surface; flag it
    # 'diffuse' so the reader knows the signal is weak (and could lower depth/branch).
    cond, diffuse = [], False
    for ms_try in (ms, ms * 0.7, ms * 0.5, ms * 0.35):
        cond = _conditional(lines, mover_white, ms_try, max(0.08, ms_try * 0.7),
                            mover_order, opp_order, max_shown=n, max_size=msize)
        if cond:
            diffuse = ms_try < ms - 1e-9
            break

    return {
        "total": tree.get("total", 0),
        "white_score": round(tree.get("score", 0.0), 3),
        "n_lines": len(lines),
        "mover": "white" if mover_white else "black",
        "diffuse": diffuse,        # True if we had to relax below the configured min_support
        "white": _side_plan([(L[0], L[2]) for L in lines], ms, worder, max_shown=n, max_size=msize),
        "black": _side_plan([(L[1], L[2]) for L in lines], ms, border, max_shown=n, max_size=msize),
        "conditional": cond,
    }


def format_suggestions(tree: dict, board: chess.Board) -> str:
    s = _summarize(tree, board)
    mover = s["mover"].capitalize()
    opp = "Black" if mover == "White" else "White"
    out = [f"Masters: {s['total']} games, {mover} to move, White {s['white_score']*100:.0f}%  ({s['n_lines']} lines)"]
    if not s["conditional"]:
        out.append("(not enough data for a clear plan)")
        # Fallback: at least show the masters' moves with their frequency at this
        # position, like the Lichess-DB stats (D). The root fen was already fetched
        # by explore(), so this is a cache hit.
        try:
            raw = LP.http_fetch(board.fen())
            stats = LP.format_db_stats(raw, title="Masters -- moves played here")
            out.append("")
            out.append(stats)
        except Exception:
            pass
        return "\n".join(out)
    if s.get("diffuse"):    # had to relax the support threshold to surface a plan
        out.append("(search diffuse: plans below your support threshold -- try a lower depth/branch)")
    cond = s["conditional"]
    out.append(f"{mover} plans typically:")
    for i, c in enumerate(cond, 1):
        sc = f", {mover} {c['mover_score']*100:.0f}%" if c.get("mover_score") is not None else ""
        out.append(f"  [{i}] {c['plan']}   ({c['support']*100:.0f}%{sc})")
    # most promising plan: only if the top score clearly beats the second (> 2%)
    ranked = sorted(((c["mover_score"], i) for i, c in enumerate(cond, 1)
                     if c.get("mover_score") is not None), reverse=True)
    if len(ranked) >= 2 and ranked[0][0] - ranked[1][0] > 0.02:
        out.append(f"The most promising plan seems [{ranked[0][1]}] ({mover} {ranked[0][0]*100:.0f}%).")
    out.append("")
    for i, c in enumerate(cond, 1):
        out.append(f"On [{i}], {opp} plays: {c['response']}")
    out.append("")
    out.append(f"[1-{len(cond)}] show arrows on the board   -   [0] clear")
    return "\n".join(out)
