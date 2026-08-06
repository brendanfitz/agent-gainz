import pandas as pd

from agent_gainz import transforms


def row(df, day, name):
    return df.query("day == @day and exercise_name == @name").iloc[0]


def test_normalize_superset_tag(mini_df):
    r = row(mini_df, "W1U1", "Cable Row (Heavy)")
    assert r.superset == "A1"
    assert r.exercise == "A1: Cable Row\n(Heavy)"  # raw untouched
    assert r.exercise_base == "Cable Row"


def test_normalize_plain_exercise(mini_df):
    r = row(mini_df, "W1U1", "Bench Press")
    assert pd.isna(r.superset)
    assert r.exercise_base == "Bench Press"


def test_summarize_shorthand_and_drop(mini_df):
    r = row(mini_df, "W1U1", "Leg Extension")
    assert r.n_working_sets == 2
    assert r.sets_inferred
    assert r.has_dropset and r.n_drop_sets == 1
    assert r.drop_weight == 60.0 and r.drop_reps == 12
    assert r.volume_load == 2 * 90 * 12
    assert r.volume_load_incl_drops == 2 * 90 * 12 + 60 * 12


def test_summarize_bodyweight(mini_df):
    r = row(mini_df, "W1U1", "Hanging Leg Raise")
    assert r.weight_top == 0.0
    assert r.volume_load == 0.0
    assert r.reps_total == 10


def test_reps_at_top_ties_take_last_set():
    df = pd.DataFrame([dict(day="W1U1", exercise="X", working_sets=2, load="100R10,100R8")])
    parsed = transforms.parse_and_summarize(df)
    assert parsed.iloc[0].reps_at_top == 8


def test_weight_changed_and_top():
    df = pd.DataFrame([dict(day="W1U1", exercise="X", working_sets=2, load="95R10,105R9")])
    r = transforms.parse_and_summarize(df).iloc[0]
    assert r.weight_changed
    assert r.weight_top == 105.0 and r.reps_at_top == 9
    assert r.weight_first == 95.0
    assert r.reps_total == 19


def test_unlogged_rows_have_consistent_nas(mini_df):
    r = row(mini_df, "W4U1", "Bench Press")
    assert r.parse_status == "empty"
    assert r.n_working_sets == 0 and r.n_drop_sets == 0
    assert pd.isna(r.weight_top) and pd.isna(r.volume_load)
    assert not r.has_dropset and not r.sets_inferred
