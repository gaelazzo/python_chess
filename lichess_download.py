"""Incremental download + dedup of lichess games via the public API.

Functional mirror of chess_com_download.py, but with two simplifications:
 - lichess exposes a single endpoint (/api/games/user/{user}) that returns a
   streaming PGN, so there is no "monthly archive list" to iterate over;
 - the `since` parameter (UNIX ms timestamp) limits the query to games after
   a given instant: a single HTTP request does the entire incremental update.

The output file can be the same one used for chess.com: dedup by
signature (URL from [Site]/[Link] or a composite of headers) removes
duplicates and preserves any games from other sources already present.

API reference: https://lichess.org/api#tag/Games/operation/apiGamesUser
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional, Set, Tuple

import requests

import pgngamelist

try:
    import chess.pgn
except ImportError:
    chess = None


def _grab(pgn_text: str, tag: str) -> str:
    m = re.search(rf'\[{tag}\s+"([^"]*)"\]', pgn_text)
    return m.group(1) if m else ''


def _signature_from_pgn_text(pgn_text: str) -> str:
    """Unique signature for dedup. Prefers the URLs from [Site] (lichess) or
    [Link] (chess.com). Fallback: a composite of basic headers."""
    site = _grab(pgn_text, "Site")
    if "//" in site:
        return site
    link = _grab(pgn_text, "Link")
    if "//" in link:
        return link
    return "|".join([
        _grab(pgn_text, "Date") or "?",
        _grab(pgn_text, "UTCTime") or "?",
        _grab(pgn_text, "White") or "?",
        _grab(pgn_text, "Black") or "?",
        _grab(pgn_text, "Result") or "?",
    ])


def _read_existing_state(path: str) -> Tuple[Set[str], Optional[int]]:
    """Scan the existing PGN. Returns:
      - the set of signatures (for dedup, covers ALL sources, including chess.com),
      - UNIX ms timestamp of the most recent lichess game (None if absent).
    The latter is used as `since` for the API: lichess will return only games
    after that instant.
    """
    sigs: Set[str] = set()
    latest_ts_ms: Optional[int] = None
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return sigs, None
    if chess is None:
        return sigs, None
    with open(path, encoding='utf-8', errors='replace') as f:
        while True:
            try:
                h = chess.pgn.read_headers(f)
            except Exception:
                break
            if h is None:
                break
            site = h.get("Site") or ""
            link = h.get("Link") or ""
            if "//" in site:
                sigs.add(site)
            elif "//" in link:
                sigs.add(link)
            else:
                sigs.add("|".join([
                    h.get("Date") or "?",
                    h.get("UTCTime") or "?",
                    h.get("White") or "?",
                    h.get("Black") or "?",
                    h.get("Result") or "?",
                ]))
            # cutoff timestamp only for lichess games
            if "lichess.org" in site or "lichess.org" in link:
                ud = h.get("UTCDate") or h.get("Date") or ""
                ut = h.get("UTCTime") or "00:00:00"
                try:
                    dt_utc = datetime.strptime(f"{ud} {ut}", "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    ts = int(dt_utc.timestamp() * 1000)
                    if latest_ts_ms is None or ts > latest_ts_ms:
                        latest_ts_ms = ts
                except ValueError:
                    pass
    return sigs, latest_ts_ms


def load(user_name: str, output_file: str, color: Optional[str] = None,
         max_games: Optional[int] = None) -> Optional[int]:
    """Download the lichess games of `user_name` incrementally.

    - If the file exists, dedup by signature; append only the NEW ones.
    - Use the lichess `since` parameter to download only the games
      after the last lichess one already present in the file.
    - `color`: 'w'/'b'/None (converted to 'white'/'black' for the API).
    - `max_games`: passed as `max` to the API.

    Returns the number of games actually added, or None on error.
    """
    if not user_name:
        print("No lichess player set: fill in the 'player:' field first.")
        return None
    output_path = os.path.join(pgngamelist.PGN_FOLDER, output_file)
    os.makedirs(pgngamelist.PGN_FOLDER, exist_ok=True)

    existing_sigs, since_ts = _read_existing_state(output_path)
    if existing_sigs:
        msg = f"Existing file: {len(existing_sigs)} games found"
        if since_ts is not None:
            ts_iso = datetime.fromtimestamp(since_ts / 1000, tz=timezone.utc).isoformat()
            msg += f", last lichess: {ts_iso}"
        print(msg)

    params = {"sort": "dateDesc"}
    # Only download games up to yesterday (local time): the current day is
    # still in progress, so fetching it could leave it permanently incomplete
    # downstream (e.g. inclusive per-day watermarks).
    today_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    params["until"] = str(int(today_start.timestamp() * 1000) - 1)
    if since_ts is not None:
        # +1 ms to skip the game itself (dedup would catch the duplicates anyway).
        params["since"] = str(since_ts + 1)
    if max_games is not None:
        params["max"] = str(max_games)
    if color == "w":
        params["color"] = "white"
    elif color == "b":
        params["color"] = "black"

    url = f"https://lichess.org/api/games/user/{user_name}"
    req_headers = {"Accept": "application/x-chess-pgn"}

    try:
        response = requests.get(url, params=params, headers=req_headers, timeout=60)
    except requests.RequestException as e:
        print(f"Network error: {e}")
        return None
    if not response.ok:
        print(f"lichess API error: {response.status_code} {response.reason}")
        if response.status_code == 404:
            print(f"  (lichess user '{user_name}' not found -- check the 'player:' field)")
        return None

    pgn_text = response.text
    if not pgn_text.strip():
        print("Lichess returned no games.")
        return 0

    # Split the response into individual PGN blocks (at each new [Event ...]).
    chunks = re.split(r'(?=\[Event\s+")', pgn_text)
    kept = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        sig = _signature_from_pgn_text(chunk)
        if sig in existing_sigs:
            continue
        kept.append(chunk)
        existing_sigs.add(sig)

    if not kept:
        print("No new lichess games to add.")
        return 0

    already_has_content = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    with open(output_path, 'a' if already_has_content else 'w', encoding='utf-8') as f:
        if already_has_content:
            f.write('\n')
        for pgn in kept:
            f.write(pgn)
            f.write('\n\n')
    print(f"Added {len(kept)} new lichess games to {output_file}.")
    return len(kept)
