"""Mine 'typical plans' for a position from the Lichess MASTERS opening explorer.

The explorer returns, per position, the distribution of the NEXT moves played by
masters (with W/D/B counts) -- not whole games. So a 'typical plan' is the
high-probability CONTINUATION TREE: from a structure's crystallization position
we follow the moves played in at least `min_share` of the games at each node,
down to a development-window depth, and the dominant branch(es) are the plans,
coloured by the masters' score. Transpositions merge for free (the explorer is
keyed by position; we also cache by FEN).

Network: needs https://explorer.lichess.ovh (masters endpoint). `fetch` is
injectable, so the walk/aggregation logic is unit-testable offline with canned
responses (the live HTTP part is the only thing that needs connectivity).

Run live (from a machine that can reach the explorer):
    python lichess_plans.py --moves "e2e4 d7d6 d2d4 ... d4d5" --depth 12
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

import chess

MASTERS_URL = "https://explorer.lichess.ovh/masters"
USER_AGENT = "chess-trainer-plan-miner/0.1"


# --- Persistent on-disk cache of explorer responses -----------------------
# The masters DB changes slowly, so a request for a FEN can be reused for a long
# time (TTL in days, from config.lichess_cache_days). This is the big efficiency
# win: a structure analysed once is essentially free afterwards.
def _data_dir() -> str:
    base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data")


# Disposable, auto-rebuilt cache -> its own subfolder so it doesn't clutter the
# data/ files the user browses (PGNs, lessons, ...). Safe to delete any time.
_CACHE_PATH = os.path.join(_data_dir(), "cache", "lichess_cache.json")
_cache: Optional[dict] = None
_cache_dirty = False
_net_fetches = 0          # count of ACTUAL network requests (cache misses); lets the
                          # walk throttle only real traffic, so a cached re-run is instant


def _cache_load() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _cache_ttl_seconds() -> float:
    try:
        from config import config
        days = getattr(config, "lichess_cache_days", None)
    except Exception:
        days = None
    return float(days or 365) * 86400.0


def flush_cache() -> None:
    """Persist the cache to disk (called at the end of a walk)."""
    global _cache_dirty
    if _cache_dirty and _cache is not None:
        try:
            os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
            with open(_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(_cache, f)
            _cache_dirty = False
        except OSError as e:
            print(f"lichess cache: save failed: {e}")


def resolve_token(explicit: Optional[str] = None) -> Optional[str]:
    """Find the Lichess API token, in order: explicit arg, LICHESS_TOKEN env var,
    then `lichess_token` in config.json (gitignored, alongside the other secrets).
    Never hard-code it in source or paste it in chat."""
    if explicit:
        return explicit
    env = os.environ.get("LICHESS_TOKEN")
    if env:
        return env
    try:
        from config import config
        return getattr(config, "lichess_token", None) or None
    except Exception:
        return None


def http_fetch(fen: str, moves: int = 12, timeout: float = 20.0,
               token: Optional[str] = None) -> dict:
    """Live GET against the Lichess masters explorer for `fen`.

    The endpoint requires a Lichess API token (it answers 401 otherwise). Create
    one at https://lichess.org/account/oauth/token (no scope needed) and put it
    in the LICHESS_TOKEN env var or in config.json (`"lichess_token": "lip_..."`)."""
    global _cache_dirty, _net_fetches
    key = f"{moves}|{fen}"
    cache = _cache_load()
    ent = cache.get(key)
    if ent and (time.time() - ent.get("ts", 0)) < _cache_ttl_seconds():
        return ent["raw"]                       # fresh cache hit -> no network

    token = resolve_token(token)
    url = MASTERS_URL + "?" + urllib.parse.urlencode(
        {"fen": fen, "moves": moves, "topGames": 0, "recentGames": 0})
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    _net_fetches += 1                           # a real network request is happening
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = json.load(r)
    cache[key] = {"ts": time.time(), "raw": raw}    # store only successful responses
    _cache_dirty = True
    return raw


LICHESS_DB_URL = "https://explorer.lichess.ovh/lichess"


def db_fetch(fen: str, moves: int = 15, timeout: float = 20.0, token: Optional[str] = None) -> dict:
    """One direct query to the Lichess GAMES database (all players, NOT masters)
    for `fen`. Same on-disk cache as the masters fetch (distinct key), so a repeat
    is instant. Returns the raw explorer JSON."""
    global _cache_dirty, _net_fetches
    key = f"db|{moves}|{fen}"
    cache = _cache_load()
    ent = cache.get(key)
    if ent and (time.time() - ent.get("ts", 0)) < _cache_ttl_seconds():
        return ent["raw"]                       # fresh cache hit -> no network

    token = resolve_token(token)
    url = LICHESS_DB_URL + "?" + urllib.parse.urlencode(
        {"fen": fen, "moves": moves, "topGames": 0, "recentGames": 0})
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    _net_fetches += 1
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = json.load(r)
    cache[key] = {"ts": time.time(), "raw": raw}
    _cache_dirty = True
    flush_cache()
    return raw


def format_db_stats(raw: dict) -> str:
    """Plain stats for the Lichess games DB: total + overall W/D/B, then per move
    the share, game count and W/D/B (White POV). A straight query, no plans."""
    w, d, b = raw.get("white", 0), raw.get("draws", 0), raw.get("black", 0)
    total = w + d + b
    if not total:
        return "Lichess database: no games for this position."
    out = [f"Lichess database: {total:,} games   "
           f"White {w*100/total:.0f}% / Draw {d*100/total:.0f}% / Black {b*100/total:.0f}%", ""]
    for m in raw.get("moves", []):
        mw, md, mb = m.get("white", 0), m.get("draws", 0), m.get("black", 0)
        g = mw + md + mb
        if not g:
            continue
        out.append(f"  {m.get('san', ''):6} {g*100/total:4.1f}%  ({g:,} games)   "
                   f"W{mw*100/g:.0f}/D{md*100/g:.0f}/B{mb*100/g:.0f}")
    return "\n".join(out)


def _node(raw: dict) -> dict:
    """Normalise an explorer response into {total, score(White POV), moves[], opening}."""
    w, d, b = raw.get("white", 0), raw.get("draws", 0), raw.get("black", 0)
    total = w + d + b
    moves = []
    for m in raw.get("moves", []):
        mw, md, mb = m.get("white", 0), m.get("draws", 0), m.get("black", 0)
        g = mw + md + mb
        moves.append({"san": m.get("san"), "uci": m.get("uci"), "games": g,
                      "score": (mw + 0.5 * md) / g if g else 0.0})
    return {"total": total, "score": (w + 0.5 * d) / total if total else 0.0,
            "wdl": (w / total, d / total, b / total) if total else (0.0, 0.0, 0.0),
            "moves": moves, "opening": (raw.get("opening") or {}).get("name")}


def explore(fen: str, *, depth: int = 12, min_share: float = 0.15, min_games: int = 40,
            max_branch: int = 3, fetch: Callable[[str], dict] = http_fetch,
            cache: Optional[Dict[str, dict]] = None, throttle: float = 0.7,
            max_nodes: int = 250, on_progress: Optional[Callable] = None) -> dict:
    """Pruned continuation tree from `fen`: follow the top `max_branch` moves
    played in >= `min_share` of games, while a node has >= `min_games` games,
    down to `depth` plies. `max_nodes` caps the number of explorer requests so a
    deep walk always finishes in bounded time (a node hit past the budget becomes
    a leaf). Returns nested:
        {fen, total, score, opening, children:[{san, uci, share, games, score, node}]}
    """
    if cache is None:
        cache = {}
    budget = {"fetched": 0}

    def visit(fen: str, d: int, path: List[str]) -> dict:
        raw = cache.get(fen)
        if raw is None:
            if budget["fetched"] >= max_nodes:
                return {"fen": fen, "total": 0, "score": 0.0, "wdl": (0.0, 0.0, 0.0),
                        "opening": None, "children": []}
            if on_progress:                # report the line we are about to query
                try:
                    on_progress(path)
                except Exception:
                    pass
            budget["fetched"] += 1
            before = _net_fetches
            raw = fetch(fen)
            cache[fen] = raw
            if throttle and _net_fetches > before:
                time.sleep(throttle)      # gentle with the API, but ONLY on real
                                          # network calls -- cache hits stay instant
        nd = _node(raw)
        children: List[dict] = []
        if d > 0 and nd["total"] >= min_games:
            board = chess.Board(fen)
            for m in nd["moves"][:max_branch]:
                share = m["games"] / nd["total"] if nd["total"] else 0.0
                if share < min_share:
                    break                  # moves come sorted desc -> the rest are smaller
                try:
                    board.push(chess.Move.from_uci(m["uci"]))
                    child_fen = board.fen()
                    board.pop()
                except Exception:
                    continue
                children.append({"san": m["san"], "uci": m["uci"], "share": share,
                                 "games": m["games"], "score": m["score"],
                                 "node": visit(child_fen, d - 1, path + [m["san"]])})
        return {"fen": fen, "total": nd["total"], "score": nd["score"],
                "wdl": nd.get("wdl", (0.0, 0.0, 0.0)),
                "opening": nd["opening"], "children": children}

    result = visit(fen, depth, [])
    flush_cache()      # persist any new responses for next time
    return result


def principal_line(node: dict) -> List[dict]:
    """The single most-played continuation (top move at each node)."""
    line = []
    while node["children"]:
        top = node["children"][0]
        line.append(top)
        node = top["node"]
    return line


def format_tree(node: dict, *, _depth: int = 0, _prob: float = 1.0) -> List[str]:
    """Indented view: each move with its share, cumulative path %, games, White-score."""
    out = []
    for c in node["children"]:
        p = _prob * c["share"]
        out.append("  " * _depth +
                    f"{c['san']:7} {c['share']*100:3.0f}%  path {p*100:5.1f}%  "
                    f"{c['games']:6}g  W{c['score']*100:3.0f}%")
        out += format_tree(c["node"], _depth=_depth + 1, _prob=p)
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Mine typical plans from Lichess masters.")
    ap.add_argument("--moves", help="space-separated UCI moves from the start position")
    ap.add_argument("--fen", help="start FEN (alternative to --moves)")
    ap.add_argument("--depth", type=int, default=12)
    ap.add_argument("--min-share", type=float, default=0.15)
    ap.add_argument("--min-games", type=int, default=40)
    a = ap.parse_args()

    if a.moves:
        b = chess.Board()
        for u in a.moves.split():
            b.push(chess.Move.from_uci(u))
        start_fen = b.fen()
    elif a.fen:
        start_fen = a.fen
    else:
        ap.error("give --moves or --fen")

    if not resolve_token():
        print("WARNING: no Lichess token found -- the explorer will answer 401.\n"
              "  Create one at https://lichess.org/account/oauth/token (no scope), then either\n"
              "  set the LICHESS_TOKEN env var, or add \"lichess_token\": \"lip_...\" to config.json.\n")
    try:
        tree = explore(start_fen, depth=a.depth, min_share=a.min_share, min_games=a.min_games)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SystemExit("401 from the explorer: set a valid LICHESS_TOKEN (see above).")
        raise
    print(f"opening: {tree['opening']}   games: {tree['total']}   White-score: {tree['score']*100:.0f}%\n")
    print("\n".join(format_tree(tree)))
