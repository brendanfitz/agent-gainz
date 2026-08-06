import pandas as pd
import pytest

from agent_gainz.transforms import parse_load


def working(sets):
    return [s for s in sets if s["kind"] == "working"]


def drops(sets):
    return [s for s in sets if s["kind"] == "drop"]


def test_single_set():
    sets, status = parse_load("55R5")
    assert status == "ok"
    assert sets == [dict(set_num=1, kind="working", drop_num=0,
                         weight=55.0, reps=5, inferred=False)]


def test_multiple_sets_comma_newline():
    sets, status = parse_load("95R10,\n105R9")
    assert status == "ok"
    assert [(s["weight"], s["reps"]) for s in sets] == [(95.0, 10), (105.0, 9)]
    assert [s["set_num"] for s in sets] == [1, 2]


def test_drop_marker_triangle():
    sets, status = parse_load("80R10\n▼40R12")
    assert status == "ok"
    assert [(s["kind"], s["weight"]) for s in sets] == [("working", 80.0), ("drop", 40.0)]
    assert drops(sets)[0]["set_num"] == 1  # hangs off working set 1


def test_drop_marker_ds():
    sets, status = parse_load("45R12DS25R12")
    assert status == "ok"
    assert [(s["kind"], s["weight"]) for s in sets] == [("working", 45.0), ("drop", 25.0)]


def test_repeat_suffix():
    sets, status = parse_load("140R12,\n160R12x2\n")
    assert status == "ok"
    assert [(s["weight"], s["reps"]) for s in sets] == [(140.0, 12), (160.0, 12), (160.0, 12)]
    assert [s["set_num"] for s in sets] == [1, 2, 3]


def test_shorthand_expansion():
    sets, status = parse_load("100R10", declared_sets=2)
    assert status == "ok"
    assert len(sets) == 2
    assert [s["inferred"] for s in sets] == [False, True]
    assert all(s["weight"] == 100.0 and s["reps"] == 10 for s in sets)


def test_shorthand_keeps_drop_on_final_set():
    sets, status = parse_load("90R12\n▼60R12", declared_sets=2)
    assert status == "ok"
    assert len(working(sets)) == 2
    assert working(sets)[1]["inferred"]
    assert drops(sets)[0]["set_num"] == 2  # re-attached to the last working set


def test_no_expansion_when_multiple_entries_logged():
    sets, _ = parse_load("95R10,105R9", declared_sets=3)
    assert len(working(sets)) == 2  # only single-entry shorthand expands


def test_missing_separator_two_digit_reps():
    sets, status = parse_load("115R11105R11")
    assert status == "ok"
    assert [(s["weight"], s["reps"]) for s in sets] == [(115.0, 11), (105.0, 11)]


def test_decimal_weight():
    sets, _ = parse_load("22.5R10")
    assert sets[0]["weight"] == 22.5


def test_bodyweight_zero():
    sets, status = parse_load("0R10")
    assert status == "ok"
    assert sets[0]["weight"] == 0.0


def test_bare_number_weight_only():
    sets, status = parse_load("85")
    assert status == "weight_only"
    assert sets[0]["weight"] == 85.0
    assert pd.isna(sets[0]["reps"])


def test_unparsed():
    sets, status = parse_load("skipped - shoulder")
    assert status == "unparsed"
    assert sets == []


def test_partial_leftover_text():
    sets, status = parse_load("55R5 felt heavy")
    assert status == "partial"
    assert len(sets) == 1


@pytest.mark.parametrize("raw", [None, pd.NA, "", "   "])
def test_empty(raw):
    sets, status = parse_load(raw)
    assert status == "empty"
    assert sets == []
