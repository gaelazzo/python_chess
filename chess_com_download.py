# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import os
import urllib
import urllib.request
import tempfile
from shutil import rmtree  # Per la cancellazione ricorsiva

import requests as requests
import pgngamelist
from typing import Optional, Tuple, Set

import re

try:
    import chess.pgn  # per leggere le intestazioni delle partite gia' presenti
except ImportError:
    chess = None    # gestiamo fallback se python-chess non c'e' (improbabile)

def get_player_color(pgn_text, username):
    """
    Restituisce 'white', 'black' o None se lo username non è presente nella partita.
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
    """Signature univoca per dedup. Preferisce gli URL di [Link] (chess.com) o
    [Site] (lichess). Fallback: composito di intestazioni di base."""
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
    """Scansiona le intestazioni del PGN esistente. Ritorna:
      - set delle signature (per dedup),
      - (year, month) della partita chess.com piu' recente, o None se non ce ne sono.
    L'ultima informazione permette di saltare gli archivi mensili gia' coperti.
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
            # cutoff: solo per le partite chess.com (il file potrebbe contenere
            # anche lichess o altre, ma per il fetching chess.com ci basano sulle
            # date dei suoi propri archivi).
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
    """Estrae (anno, mese) da un URL d'archivio chess.com tipo .../games/2025/03."""
    m = re.search(r'/(\d{4})/(\d{1,2})\b', url)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def load(user_name: str, output_file: str, color: str, max_games: Optional[int] = None):
    """Scarica le partite chess.com in modo INCREMENTALE.

    - Se il file esiste, dedup-a per signature (Link/Site URL o composito di
      Date|UTCTime|White|Black|Result) cosi' non riscrive ne' duplica nulla --
      anche partite lichess merged a mano restano intoccate.
    - Salta gli archivi mensili antecedenti l'ultima partita chess.com gia'
      presente (i mesi vecchi sono immutabili lato chess.com).
    - `max_games` ora significa: al massimo N NUOVE partite aggiunte.
    - Append-only sul file (non sovrascrive).
    """
    output_dir = os.path.join(pgngamelist.PGN_FOLDER, output_file)
    os.makedirs(pgngamelist.PGN_FOLDER, exist_ok=True)

    existing_sigs, cutoff = _read_existing_state(output_dir)
    if existing_sigs:
        print(f"File esistente: {len(existing_sigs)} partite trovate"
              + (f", ultimo mese chess.com: {cutoff[0]}-{cutoff[1]:02d}" if cutoff else ""))

    url_games = f'https://api.chess.com/pub/player/{user_name}/games/archives'

    with tempfile.TemporaryDirectory(prefix='chess_cache_') as cache_path:
        json_data = cached_json_get(url_games, cache_path)
        archives = json_data.get('archives')
        if archives is None:
            print(f"User {user_name} does not exist")
            return

        # Skip dei mesi precedenti al cutoff (i mesi vecchi non cambiano).
        if cutoff is not None:
            archives = [a for a in archives
                        if _archive_yyyymm(a) is None or _archive_yyyymm(a) >= cutoff]
            print(f"Archivi da fetchare: {len(archives)} (filtrati dal cutoff)")

        # Dal mese piu' recente all'indietro -- dedup per signature, filtro
        # colore, max_games sulle NUOVE.
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
                existing_sigs.add(sig)   # evita duplicati anche all'interno della stessa run
                if max_games is not None and len(kept) >= max_games:
                    break
            if max_games is not None and len(kept) >= max_games:
                break

        if not kept:
            print("Nessuna nuova partita da aggiungere.")
            return

        # Append (o creazione) -- assicura separazione dalle partite gia' presenti.
        already_has_content = os.path.exists(output_dir) and os.path.getsize(output_dir) > 0
        with open(output_dir, 'a' if already_has_content else 'w', encoding='utf-8') as f:
            if already_has_content:
                f.write('\n')   # safety: un newline separatore
            for pgn in kept:
                f.write(pgn)
                f.write('\n' * 2)
        print(f"Aggiunte {len(kept)} nuove partite a {output_file}.")

