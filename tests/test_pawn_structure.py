"""Pilot validation: the Pirc and the King's Indian reach the same central
pawn structure (so ideas are shared, not duplicated), and the locked chain
derives forward from the open centre. No engine, pure pawn geometry."""
import chess

import pawn_structure as ps

# Locked King's-Indian chain core (White d5/e4 vs Black d6/e5).
# Pirc route leaves the c-pawn on c2; the KID route has it on c4.
PIRC_CHAIN = chess.Board("4k3/ppp2ppp/3p4/3Pp3/4P3/8/PPP2PPP/4K3 w - - 0 1")
KID_CHAIN  = chess.Board("4k3/ppp2ppp/3p4/3Pp3/2P1P3/8/PP3PPP/4K3 w - - 0 1")
# Open centre before White locks with d4-d5 (White d4/e4 vs Black d6/e5).
OPEN_CENTRE = chess.Board("4k3/ppp2ppp/3p4/4p3/3PP3/8/PPP2PPP/4K3 w - - 0 1")


def test_default_signature_uses_global_cf_granularity():
    # Global decision: c-f. So by default Pirc (c2) and KID (c4) are DISTINCT
    # structures, but still linked by forward derivation (c2 -> c4).
    assert ps.signature(PIRC_CHAIN) != ps.signature(KID_CHAIN)
    assert ps.can_derive(PIRC_CHAIN, KID_CHAIN)
    assert not ps.can_derive(KID_CHAIN, PIRC_CHAIN)


def test_pirc_and_kid_share_the_central_structure():
    # On the bare centre (d,e) the two openings are the SAME structure...
    assert ps.signature(PIRC_CHAIN, ps.CENTRE_DE) == ps.signature(KID_CHAIN, ps.CENTRE_DE)
    # ...but the exact structure separates them by the c-pawn (c2 vs c4).
    assert ps.signature(PIRC_CHAIN, ps.ALL_FILES) != ps.signature(KID_CHAIN, ps.ALL_FILES)


def test_kid_chain_derives_from_pirc_chain_not_vice_versa():
    # c2 -> c4 is a legal forward advance, so the KID chain derives from the Pirc
    # chain; the reverse (c4 -> c2) is impossible (pawns don't retreat).
    assert ps.can_derive(PIRC_CHAIN, KID_CHAIN)
    assert not ps.can_derive(KID_CHAIN, PIRC_CHAIN)


def test_open_centre_locks_into_the_chain():
    assert ps.can_derive(OPEN_CENTRE, PIRC_CHAIN)        # d4 -> d5
    assert not ps.can_derive(PIRC_CHAIN, OPEN_CENTRE)    # d5 can't retreat to d4


def test_signature_is_colour_normalised():
    # A structure and its colours-reversed twin share the signature.
    assert ps.signature(PIRC_CHAIN) == ps.signature(PIRC_CHAIN.mirror())
    # ...and orientation reports which face we are on (opposite for the twin).
    assert ps.orientation(PIRC_CHAIN) == -ps.orientation(PIRC_CHAIN.mirror())


def test_real_move_orders_reach_the_same_central_structure():
    # Pirc move order.
    pirc = chess.Board()
    for mv in ["e2e4", "d7d6", "d2d4", "g8f6", "b1c3", "g7g6", "g1f3", "f8g7",
               "f1e2", "e8g8", "e1g1", "e7e5", "d4d5"]:
        pirc.push(chess.Move.from_uci(mv))
    # King's Indian move order (1.d4 ... with c4) reaching the same centre.
    kid = chess.Board()
    for mv in ["d2d4", "g8f6", "c2c4", "g7g6", "b1c3", "f8g7", "e2e4", "d7d6",
               "g1f3", "e8g8", "f1e2", "e7e5", "d4d5"]:
        kid.push(chess.Move.from_uci(mv))
    # Same central structure (d,e) discovered automatically -- no opening label.
    assert ps.signature(pirc, ps.CENTRE_DE) == ps.signature(kid, ps.CENTRE_DE)
