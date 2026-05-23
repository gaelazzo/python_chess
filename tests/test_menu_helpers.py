import menu_helpers as mh
import state


def test_make_updater_casts_int_into_dict():
    d = {}
    upd = mh.make_updater("x", int, target_dict=d)
    upd("5")
    assert d["x"] == 5


def test_make_updater_swallows_bad_cast():
    d = {"x": 5}
    upd = mh.make_updater("x", int, target_dict=d)
    upd("not-a-number")           # ValueError is swallowed
    assert d["x"] == 5            # unchanged


def test_make_updater_empty_string_becomes_none():
    d = {}
    upd = mh.make_updater("name", str, target_dict=d)
    upd("Bob")
    assert d["name"] == "Bob"
    upd("")
    assert d["name"] is None


def test_make_updater_validator_rejects():
    d = {}
    upd = mh.make_updater("v", int, target_dict=d, validator=lambda v: v > 0)
    upd("3")
    assert d["v"] == 3
    upd("-1")                     # rejected by validator
    assert d["v"] == 3


def test_make_updater_writes_to_state_when_no_dict():
    upd = mh.make_updater("num_moves_to_show", int)   # target_dict None -> state
    upd("7")
    assert state.num_moves_to_show == 7               # restored by autouse fixture


def test_make_selector_updater():
    d = {}
    upd = mh.make_selector_updater("k", target_dict=d)
    upd([("White", 1)], 0)
    assert d["k"] == 1


def test_make_bool_selector_updater():
    d = {}
    upd = mh.make_bool_selector_updater("b", d)
    upd([("On", 1)], 0)
    assert d["b"] is True
    upd([("Off", 0)], 0)
    assert d["b"] is False


def test_get_current_color_index():
    state.positionParameters["color"] = "w"
    assert mh.getCurrentColorIndex() == 0
    state.positionParameters["color"] = "b"
    assert mh.getCurrentColorIndex() == 1
    state.positionParameters["color"] = None
    assert mh.getCurrentColorIndex() == 2
