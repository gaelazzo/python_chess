"""Plan extraction by MOVES PLAYED (not positions): fixed-depth line enumeration
and correlated move bundles via lift. No thread, no network."""
import chess

import plan_analysis as PA

# Root = BLACK to move. Black: f5 (60%) or Na6 (40%); after f5, White: Nf3 (100%).
TREE = {
    "total": 100, "score": 0.5, "opening": "X",
    "children": [
        {"san": "f5", "uci": "f7f5", "share": 0.60, "games": 60, "score": 0.5,
         "node": {"total": 60, "children": [
             {"san": "Nf3", "uci": "g1f3", "share": 1.0, "games": 60, "score": 0.5,
              "node": {"total": 60, "children": []}}]}},
        {"san": "Na6", "uci": "b8a6", "share": 0.40, "games": 40, "score": 0.5,
         "node": {"total": 40, "children": []}},
    ],
}
BLACK_TO_MOVE = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1")


def test_lines_collect_moves_per_side():
    lines = PA._lines(TREE, root_white_to_move=False)   # Black to move at root
    assert len(lines) == 2
    by_weight = sorted(lines, key=lambda x: -x[2])
    w0, b0, p0 = by_weight[0][:3]                        # the f5 -> Nf3 line
    assert b0 == frozenset({"f5"}) and w0 == frozenset({"Nf3"})
    assert abs(p0 - 0.60) < 1e-9                         # weight = path probability
    w1, b1, p1 = by_weight[1][:3]                        # the Na6 line
    assert b1 == frozenset({"Na6"}) and w1 == frozenset()
    assert abs(p1 - 0.40) < 1e-9


def test_support_separates_rival_plans():
    A = frozenset({"Be3", "O-O-O", "Qd2"})              # castling is just a move
    B = frozenset({"Be2", "O-O"})
    tx = [(A, 1.0)] * 30 + [(B, 1.0)] * 25 + [(frozenset({"h3"}), 1.0)] * 5
    bundles, _ = PA._mine_bundles(tx, min_support=0.2)
    sets = [fs for fs, _ in bundles]
    assert A in sets and B in sets
    assert not any("Be3" in fs and "Be2" in fs for fs in sets)   # rival plans don't co-occur


def test_render_moves_sorted_join():
    assert PA._render_moves(frozenset({"Be3", "O-O-O", "Qd2"})) == "Be3 + O-O-O + Qd2"


def test_render_moves_respects_play_order():
    order = {"Nf3": 0.0, "f4": 3.0, "Bd3": 5.0}        # mean ply each move is played
    assert PA._render_moves(frozenset({"Bd3", "Nf3", "f4"}), order) == "Nf3 + f4 + Bd3"


def test_ply_orders_uses_depth_per_side():
    tree = {"children": [
        {"san": "a4", "uci": "a2a4", "share": 1.0, "games": 1, "score": 0.5, "node": {"children": [
            {"san": "c5", "uci": "c7c5", "share": 1.0, "games": 1, "score": 0.5, "node": {"children": [
                {"san": "b4", "uci": "b2b4", "share": 1.0, "games": 1, "score": 0.5,
                 "node": {"children": []}}]}}]}}]}
    w, b = PA._ply_orders(tree, mover_white=True)
    assert w["a4"] == 0.0 and w["b4"] == 2.0       # White moves at even plies
    assert b["c5"] == 1.0                           # Black move at odd ply


def test_conditional_pairs_mover_plan_with_opponent_response():
    # Mover = White. Plan {a4,h3} -> Black plays ...f5; plan {Be3,d5} -> ...e6.
    A = (frozenset({"a4", "h3"}), frozenset({"f5"}), 1.0)
    B = (frozenset({"Be3", "d5"}), frozenset({"e6"}), 1.0)
    lines = [A] * 10 + [B] * 8
    cond = PA._conditional(lines, mover_white=True, ms1=0.3, ms2=0.2)
    plans = {c["plan"]: c for c in cond}
    assert "a4 + h3" in plans and "Be3 + d5" in plans
    assert "f5" in plans["a4 + h3"]["response"]   # Black's response in A's games
    assert "e6" in plans["Be3 + d5"]["response"]  # ...and in B's games


def test_response_pulls_out_conditional_capture():
    # ...e5 is NOT in the mover's plan (only 30% play it), so White's fxe5 is shown
    # conditionally: "if Black plays e5 then fxe5".
    on = (frozenset({"Nf3", "Bd3", "fxe5"}), frozenset({"Bg7", "O-O", "e5"}), 1.0)
    off = (frozenset({"Nf3", "Bd3"}), frozenset({"Bg7", "O-O"}), 1.0)
    resp = PA._conditional([on] * 3 + [off] * 7, mover_white=False, ms1=0.5, ms2=0.2)[0]["response"]
    assert "if Black plays e5 then fxe5" in resp           # capture shown conditionally
    assert "fxe5" not in resp.split("if Black")[0]         # ...not left in the main line


def test_response_keeps_capture_inline_when_trigger_in_plan():
    # ...e5 IS in the plan -> the recapture fxe5 is left inline, no "if" clause.
    L = (frozenset({"Nf3", "Bd3", "fxe5"}), frozenset({"Bg7", "O-O", "e5"}), 1.0)
    resp = PA._conditional([L] * 10, mover_white=False, ms1=0.3, ms2=0.2)[0]["response"]
    assert "if Black plays" not in resp                    # trigger already named in the plan
    assert "fxe5" in resp                                  # ...so the capture stays inline


def test_response_factors_core_and_alternatives():
    A = (frozenset({"Nf3", "O-O", "d5"}), frozenset({"Bg7", "Nc6"}), 1.0)
    B = (frozenset({"Nf3", "O-O", "h3"}), frozenset({"Bg7", "Nc6"}), 1.0)
    resp = PA._conditional([A] * 6 + [B] * 6, mover_white=False, ms1=0.3, ms2=0.2)[0]["response"]
    assert "Nf3 + O-O" in resp and "then" in resp and "d5 or h3" in resp


def test_summarize_and_format_use_moves():
    s = PA._summarize(TREE, BLACK_TO_MOVE)
    black_moves = {sp["move"] for sp in s["black"]["spots"]}
    assert "f5" in black_moves and "Na6" in black_moves   # Black moves only
    assert {sp["move"] for sp in s["white"]["spots"]} <= {"Nf3"}   # White moves only
    assert s["mover"] == "black"                                    # side to move at the root
    assert "Masters:" in PA.format_suggestions(TREE, BLACK_TO_MOVE)
