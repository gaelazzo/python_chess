"""Download incrementale + dedup di partite lichess via API pubblica.

Mirror funzionale di chess_com_download.py, ma con due semplificazioni:
 - lichess espone un endpoint unico (/api/games/user/{user}) che ritorna PGN
   streaming, quindi nessun "elenco archivi mensili" da iterare;
 - il parametro `since` (timestamp ms UNIX) limita la query alle partite dopo
   un certo istante: un solo HTTP fa l'intero incrementale.

Il file di output puo' essere lo stesso usato per chess.com: la dedup per
signature (URL di [Site]/[Link] o composito di intestazioni) elimina i
duplicati e preserva eventuali partite di altre fonti gia' presenti.

Riferimento API: https://lichess.org/api#tag/Games/operation/apiGamesUser
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
    """Signature univoca per dedup. Preferisce gli URL di [Site] (lichess) o
    [Link] (chess.com). Fallback: composito di intestazioni di base."""
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
    """Scansiona il PGN esistente. Ritorna:
      - set delle signature (per dedup, copre TUTTE le fonti, anche chess.com),
      - timestamp ms UNIX della partita lichess piu' recente (None se assente).
    Quest'ultimo serve come `since` per l'API: lichess ritornera' solo partite
    posteriori a quell'istante.
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
            # cutoff timestamp solo per le partite lichess
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
         max_games: Optional[int] = None):
    """Scarica le partite lichess di `user_name` in modo incrementale.

    - Se il file esiste, dedup-a per signature; appende soltanto le NUOVE.
    - Usa il parametro `since` di lichess per scaricare solo le partite
      successive all'ultima lichess gia' presente nel file.
    - `color`: 'w'/'b'/None (convertito a 'white'/'black' per l'API).
    - `max_games`: passato come `max` all'API.
    """
    output_path = os.path.join(pgngamelist.PGN_FOLDER, output_file)
    os.makedirs(pgngamelist.PGN_FOLDER, exist_ok=True)

    existing_sigs, since_ts = _read_existing_state(output_path)
    if existing_sigs:
        msg = f"File esistente: {len(existing_sigs)} partite trovate"
        if since_ts is not None:
            ts_iso = datetime.fromtimestamp(since_ts / 1000, tz=timezone.utc).isoformat()
            msg += f", ultimo lichess: {ts_iso}"
        print(msg)

    params = {"sort": "dateDesc"}
    if since_ts is not None:
        # +1 ms per saltare la partita stessa (la dedup catturerebbe comunque i duplicati).
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
        print(f"Errore di rete: {e}")
        return
    if not response.ok:
        print(f"Errore lichess API: {response.status_code} {response.reason}")
        return

    pgn_text = response.text
    if not pgn_text.strip():
        print("Lichess non ha restituito alcuna partita.")
        return

    # Split del response in singoli blocchi PGN (a ogni nuovo [Event ...]).
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
        print("Nessuna nuova partita lichess da aggiungere.")
        return

    already_has_content = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    with open(output_path, 'a' if already_has_content else 'w', encoding='utf-8') as f:
        if already_has_content:
            f.write('\n')
        for pgn in kept:
            f.write(pgn)
            f.write('\n\n')
    print(f"Aggiunte {len(kept)} nuove partite lichess a {output_file}.")
