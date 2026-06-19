"""The opening-ideas store: dossiers keyed by pawn structure (shared across
positions/move orders), and persistence. Pure backend, no pygame."""
import chess

import opening_ideas as OI

# Same c-f structure (White c2 d5 e4 f2 / Black c7 d6 e5 f7), different positions.
PIRC_CHAIN = chess.Board("4k3/ppp2ppp/3p4/3Pp3/4P3/8/PPP2PPP/4K3 w - - 0 1")
SAME_STRUCT_MORE_PIECES = chess.Board("4k3/ppp2ppp/3p1n2/3Pp3/4P3/8/PPP2PPP/4K3 w - - 0 1")


def test_dossier_shared_by_structure_and_persisted(tmp_path):
    OI.STORE_PATH = str(tmp_path / "ideas.json")
    OI.reload()

    OI.set_dossier(PIRC_CHAIN, {
        "character": "King's Indian chain",
        "plans_white": ["c4-c5"], "plans_black": ["...f5"],
        "breaks": [], "key_squares": ["c5", "f5"], "notes": "",
    })

    # A different position with the SAME c-f structure reads the SAME dossier.
    assert OI.get_dossier(SAME_STRUCT_MORE_PIECES)["character"] == "King's Indian chain"
    assert OI.has_dossier(SAME_STRUCT_MORE_PIECES)

    # Persisted: drop the cache, re-read from file.
    OI.reload()
    assert OI.get_dossier(PIRC_CHAIN)["plans_white"] == ["c4-c5"]
    assert "f5" in OI.get_dossier(SAME_STRUCT_MORE_PIECES)["key_squares"]


def test_no_dossier_when_unset(tmp_path):
    OI.STORE_PATH = str(tmp_path / "ideas2.json")
    OI.reload()
    assert OI.get_dossier(chess.Board()) == {}
    assert not OI.has_dossier(chess.Board())


def test_dossier_lines_render(tmp_path):
    OI.STORE_PATH = str(tmp_path / "ideas3.json")
    OI.reload()
    OI.set_dossier(PIRC_CHAIN, {
        "main_idea": ["...f5", "...Na6-c5"],
        "character": "Closed centre, opposite-wing play",
        "plans_white": ["c5", "f3 then b4"], "plans_black": ["...f5", "...Nf6-e8"],
        "breaks": [], "key_squares": ["c5"], "notes": "Black attacks the king.",
    })
    lines = OI.dossier_lines(PIRC_CHAIN)
    assert lines[0].startswith("△")          # headline idea shown with the triangle
    assert "...f5" in lines[0]
    assert "Closed centre, opposite-wing play" in lines
    assert any("White:" in ln and "c5" in ln for ln in lines)
    assert any("Black:" in ln and "...f5" in ln for ln in lines)
