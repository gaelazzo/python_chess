import state


def test_play_parameters_keys():
    for k in ("whiteCPU", "blackCPU", "elo", "elomax", "white",
              "black", "result", "event", "site", "gameid"):
        assert k in state.playParameters


def test_position_parameters_keys():
    for k in ("eco", "color", "filename", "base", "player",
              "movesToAnalyze", "blunderValue", "ponderTime", "useBook"):
        assert k in state.positionParameters


def test_color_map_round_trip():
    assert state.COLOR_MAP[0] == "w"
    assert state.COLOR_MAP[1] == "b"
    assert state.REVERSE_COLOR_MAP["w"] == 0
    assert state.REVERSE_COLOR_MAP["b"] == 1
