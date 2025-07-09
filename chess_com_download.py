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

import re

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


def load(user_name:str,  output_path:str, color:str):
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    url_games = f'https://api.chess.com/pub/player/{user_name}/games/archives'

    # create cache
    with tempfile.TemporaryDirectory(prefix='chess_cache_') as cache_path:
        print(f"Cartella temporanea creata: {cache_path}")  # Debug
        json_data = cached_json_get(url_games, cache_path)
        archives = json_data['archives']
        pgns = []
        for archive in archives:
            print(archive)
            json_data = cached_json_get(archive, cache_path)

            for game in json_data['games']:
                pgns.append(game['pgn'])

        with open(output_path, 'w', encoding='utf-8') as f:
            for pgn in pgns:
                player_color = get_player_color(pgn, user_name)
                if color is not None:
                    if color!= player_color:
                        continue

                f.write(pgn)
                f.write('\n' * 2)

