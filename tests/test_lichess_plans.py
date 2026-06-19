"""Walk/aggregation logic for the Lichess-masters plan miner, tested offline
with a canned (mock) explorer so no network is needed."""
import chess

import lichess_plans as lp


def _raw(w, d, b, moves):
    """moves: list of (san, uci, w, d, b)."""
    return {"white": w, "draws": d, "black": b,
            "moves": [{"san": s, "uci": u, "white": mw, "draws": md, "black": mb}
                      for (s, u, mw, md, mb) in moves],
            "opening": {"name": "Test"}}


def _fen_after(uci):
    b = chess.Board()
    for u in uci:
        b.push(chess.Move.from_uci(u))
    return b.fen()


START = chess.Board().fen()
AFTER_E4 = _fen_after(["e2e4"])
AFTER_D4 = _fen_after(["d2d4"])

DB = {
    START: _raw(600, 200, 200, [          # total 1000
        ("e4", "e2e4", 360, 120, 120),    # 600 -> share 0.60
        ("d4", "d2d4", 150, 60, 90),      # 300 -> share 0.30
        ("c4", "c2c4", 20, 10, 10),       # 40  -> share 0.04 (below min_share)
    ]),
    AFTER_E4: _raw(330, 120, 150, []),    # leaf in our depth
    AFTER_D4: _raw(160, 60, 80, []),
}


def _mock_fetch(fen):
    return DB[fen]


def test_explore_prunes_by_min_share_and_keeps_order():
    tree = lp.explore(START, depth=1, min_share=0.15, min_games=10,
                      fetch=_mock_fetch, throttle=0)
    sans = [c["san"] for c in tree["children"]]
    assert sans == ["e4", "d4"]            # c4 (4%) pruned by min_share
    assert tree["total"] == 1000
    assert abs(tree["score"] - 0.70) < 1e-9     # (600 + 0.5*200)/1000, White POV
    assert abs(tree["children"][0]["share"] - 0.60) < 1e-9
    assert abs(tree["children"][1]["share"] - 0.30) < 1e-9


def test_principal_line_follows_top_move():
    tree = lp.explore(START, depth=1, min_share=0.15, min_games=10,
                      fetch=_mock_fetch, throttle=0)
    line = lp.principal_line(tree)
    assert [c["san"] for c in line] == ["e4"]


def test_http_fetch_returns_fresh_cache_without_network(tmp_path):
    import time
    fen = "8/8/8/8/8/8/8/8 w - - 0 1"
    lp._CACHE_PATH = str(tmp_path / "cache.json")
    lp._cache = {f"12|{fen}": {"ts": time.time(),
                               "raw": {"white": 7, "draws": 0, "black": 0, "moves": []}}}
    try:
        raw = lp.http_fetch(fen)          # fresh hit -> no network call attempted
        assert raw["white"] == 7
    finally:
        lp._cache = None                   # don't leak state to other tests


def test_max_nodes_caps_fetches():
    calls = []
    def counting_fetch(fen):
        calls.append(fen)
        return DB[fen]
    tree = lp.explore(START, depth=3, min_share=0.15, min_games=10,
                      fetch=counting_fetch, throttle=0, max_nodes=1)
    assert len(calls) == 1                              # only the root was fetched
    assert tree["children"]                             # children listed from root data...
    assert all(c["node"]["children"] == [] for c in tree["children"])  # ...but not expanded


def test_on_progress_reports_the_current_line():
    seen = []
    lp.explore(START, depth=1, min_share=0.15, min_games=10, fetch=_mock_fetch,
               throttle=0, on_progress=lambda path: seen.append(list(path)))
    assert [] in seen                      # the root, before its fetch
    assert ["e4"] in seen and ["d4"] in seen   # the lines it descends into


def test_min_games_stops_expansion():
    # With min_games above the node total, no children are expanded.
    tree = lp.explore(START, depth=3, min_games=5000,
                      fetch=_mock_fetch, throttle=0)
    assert tree["children"] == []


def test_move_score_is_mover_white_pov():
    tree = lp.explore(START, depth=1, min_share=0.15, min_games=10,
                      fetch=_mock_fetch, throttle=0)
    e4 = tree["children"][0]
    assert abs(e4["score"] - (360 + 0.5 * 120) / 600) < 1e-9


def test_format_db_stats():
    raw = {"white": 60, "draws": 10, "black": 30,
           "moves": [{"san": "e4", "white": 30, "draws": 5, "black": 15},
                     {"san": "d4", "white": 20, "draws": 3, "black": 7}]}
    txt = lp.format_db_stats(raw)
    assert "Lichess database: 100 games" in txt
    assert "White 60%" in txt and "Black 30%" in txt
    assert "e4" in txt and "d4" in txt
    assert lp.format_db_stats({"white": 0, "draws": 0, "black": 0}) == \
        "Lichess database: no games for this position."
