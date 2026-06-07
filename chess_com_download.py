# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import os
import urllib
import urllib.request
import tempfile
from shutil import rmtree  # For recursive deletion

import requests as requests
import pgngamelist
from typing import Optional, Tuple, Set

import re

try:
    import chess.pgn  # to read the headers of games already present
except ImportError:
    chess = None    # handle fallback if python-chess is not available (unlikely)

def get_player_color(pgn_text, username):
    """
    Returns 'white', 'black' or None if the username is not present in the game.
    """
    white_player = re.search(r'\[White\s+"(.+?)"\]', pgn_text)
    black_player = re.search(r'\[Black\s+"(.+?)"\]', pgn_text)
    
    white_name = white_player.group(1).lower() if white_player else ''
    black_name = black_player.group(1).lower() if black_player else ''
    username = username.lower()
    
    if username == white_name:
        return 'w'
    elif username == black_name:
        return 'b'
    else:
        return None


def cached_json_get(url, cache_path):
    """
    Get cached or real JSON.

    :param url: URL to get.
    :param cache_path: Path to cache JSON.
    :return:
    """

    h = hashlib.sha256(url.encode())
    file_name = f'{h.hexdigest()}.json'
    file_path = os.path.join(cache_path, file_name)
    # check if cached
    if os.path.exists(file_path):
        # get from cache
        with open(file_path, 'r') as f:
            json_data = json.load(f)
        return json_data
    # not cached
    else:
        headers = {     
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        
        json_data = response.json()
        # put in cache
        with open(file_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        return json_data


def _grab(pgn_text: str, tag: str) -> str:
    m = re.search(rf'\[{tag}\s+"([^"]*)"\]', pgn_text)
    return m.group(1) if m else ''


def _signature_from_pgn_text(pgn_text: str) -> str:
    """Unique signature for dedup. Prefers the URLs of [Link] (chess.com) or
    [Site] (lichess). Fallback: composite of basic headers."""
    link = _grab(pgn_text, "Link")
    if "//" in link:
        return link
    site = _grab(pgn_text, "Site")
    if "//" in site:
        return site
    return "|".join([
        _grab(pgn_text, "Date") or "?",
        _grab(pgn_text, "UTCTime") or "?",
        _grab(pgn_text, "White") or "?",
        _grab(pgn_text, "Black") or "?",
        _grab(pgn_text, "Result") or "?",
    ])


def _read_existing_state(path: str) -> Tuple[Set[str], Optional[Tuple[int, int]]]:
    """Scans the headers of the existing PGN. Returns:
      - set of signatures (for dedup),
      - (year, month) of the most recent chess.com game, or None if there are none.
    The latter information allows skipping monthly archives already covered.
    """
    sigs: Set[str] = set()
    chesscom_latest: Optional[Tuple[int, int]] = None
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
            link = h.get("Link") or ""
            site = h.get("Site") or ""
            if "//" in link:
                sigs.add(link)
            elif "//" in site:
                sigs.add(site)
            else:
                sigs.add("|".join([
                    h.get("Date") or "?",
                    h.get("UTCTime") or "?",
                    h.get("White") or "?",
                    h.get("Black") or "?",
                    h.get("Result") or "?",
                ]))
            # cutoff: only for chess.com games (the file might also contain
            # lichess or others, but for chess.com fetching we rely on the
            # dates of its own archives).
            if "chess.com" in link or "chess.com" in site:
                date = h.get("Date") or h.get("UTCDate") or ""
                parts = date.split(".")
                if len(parts) >= 2:
                    try:
                        ym = (int(parts[0]), int(parts[1]))
                        if chesscom_latest is None or ym > chesscom_latest:
                            chesscom_latest = ym
                    except ValueError:
                        pass
    return sigs, chesscom_latest


def _archive_yyyymm(url: str) -> Optional[Tuple[int, int]]:
    """Extracts (year, month) from a chess.com archive URL like .../games/2025/03."""
    m = re.search(r'/(\d{4})/(\d{1,2})\b', url)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def load(user_name: str, output_file: str, color: str, max_games: Optional[int] = None):
    """Downloads chess.com games INCREMENTALLY.

    - If the file exists, dedup by signature (Link/Site URL or composite of
      Date|UTCTime|White|Black|Result) so it neither rewrites nor duplicates
      anything -- even lichess games merged by hand remain untouched.
    - Skips monthly archives prior to the last chess.com game already
      present (old months are immutable on the chess.com side).
    - `max_games` now means: at most N NEW games added.
    - Append-only on the file (does not overwrite).
    """
    output_dir = os.path.join(pgngamelist.PGN_FOLDER, output_file)
    os.makedirs(pgngamelist.PGN_FOLDER, exist_ok=True)

    existing_sigs, cutoff = _read_existing_state(output_dir)
    if existing_sigs:
        print(f"Existing file: {len(existing_sigs)} games found"
              + (f", last chess.com month: {cutoff[0]}-{cutoff[1]:02d}" if cutoff else ""))

    url_games = f'https://api.chess.com/pub/player/{user_name}/games/archives'

    with tempfile.TemporaryDirectory(prefix='chess_cache_') as cache_path:
        json_data = cached_json_get(url_games, cache_path)
        archives = json_data.get('archives')
        if archives is None:
            print(f"User {user_name} does not exist")
            return

        # Skip months prior to the cutoff (old months do not change).
        if cutoff is not None:
            archives = [a for a in archives
                        if _archive_yyyymm(a) is None or _archive_yyyymm(a) >= cutoff]
            print(f"Archives to fetch: {len(archives)} (filtered by cutoff)")

        # From the most recent month backwards -- dedup by signature, color
        # filter, max_games on the NEW ones.
        kept = []
        for archive in reversed(archives):
            print(archive)
            data = cached_json_get(archive, cache_path)
            for game in reversed(data.get('games', [])):
                pgn = game['pgn']
                sig = _signature_from_pgn_text(pgn)
                if sig in existing_sigs:
                    continue
                if color is not None and color != get_player_color(pgn, user_name):
                    continue
                kept.append(pgn)
                existing_sigs.add(sig)   # avoid duplicates even within the same run
                if max_games is not None and len(kept) >= max_games:
                    break
            if max_games is not None and len(kept) >= max_games:
                break

        if not kept:
            print("No new games to add.")
            return

        # Append (or creation) -- ensures separation from games already present.
        already_has_content = os.path.exists(output_dir) and os.path.getsize(output_dir) > 0
        with open(output_dir, 'a' if already_has_content else 'w', encoding='utf-8') as f:
            if already_has_content:
                f.write('\n')   # safety: a separator newline
            for pgn in kept:
                f.write(pgn)
                f.write('\n' * 2)
        print(f"Added {len(kept)} new games to {output_file}.")

