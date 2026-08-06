import json

import pytest

from agent_gainz import analytics


@pytest.fixture
def inputs(mini_df):
    return analytics.build_briefing_inputs(mini_df)


def test_bundle_resolves_days(inputs):
    assert inputs["upcoming_day"] == "W4U1"
    assert inputs["latest_day"] == "W3U1"


def test_everything_json_serializable(inputs):
    json.dumps(inputs)  # raises on any stray numpy/pandas value


def test_previous_workout_summary(mini_df):
    prev = analytics.previous_workout_summary(mini_df, "W3U1")
    assert prev["n_exercises"] == 6
    assert prev["n_working_sets"] == 7  # Leg Extension has 2
    assert prev["n_drop_sets"] == 1
    names = {e["exercise_name"] for e in prev["exercises"]}
    assert "Bench Press" in names and "Cable Row (Heavy)" in names
    # Bench 110->120 volume (+9%) and Curl 360->300 (-17%) exceed the 5% band.
    changed = {c["exercise_name"] for c in prev["notable_changes"]}
    assert "Bench Press" in changed and "Curl" in changed
    assert "Cable Row (Heavy)" not in changed


def test_upcoming_workout_preview(mini_df):
    today = analytics.upcoming_workout_preview(mini_df, "W4U1")
    assert today["split"] == "upper" and today["week"] == 4
    assert today["n_exercises"] == 7
    assert today["superset_pairs"] == [["Cable Row (Heavy)", "Lat Pulldown"]]
    bench = next(e for e in today["exercises"] if e["exercise_name"] == "Bench Press")
    assert bench["rep_range"] == [8, 10]
    assert bench["substitutes"] == []


def test_exercise_history_trends(mini_df):
    h = analytics.exercise_history(mini_df, "Bench Press", "W4U1")
    assert h["trend"] == "improving" and h["n_appearances"] == 3
    assert h["deltas"]["volume_load"] == 100.0
    assert [a["day"] for a in h["appearances"]] == ["W1U1", "W2U1", "W3U1"]

    assert analytics.exercise_history(mini_df, "Curl", "W4U1")["trend"] == "declining"
    assert analytics.exercise_history(mini_df, "Cable Row (Heavy)", "W4U1")["trend"] == "stable"
    assert analytics.exercise_history(mini_df, "New Movement", "W4U1")["trend"] == "new"


def test_exercise_history_bodyweight_uses_reps(mini_df):
    h = analytics.exercise_history(mini_df, "Hanging Leg Raise", "W4U1")
    assert h["is_bodyweight"]
    assert h["trend_metric"] == "reps_total"
    assert h["trend"] == "improving"  # 10 -> 12 -> 14 reps


def test_exercise_history_insufficient(mini_df):
    only_one = mini_df.query("day in ['W3U1', 'W4U1']").reset_index(drop=True)
    h = analytics.exercise_history(only_one, "Bench Press", "W4U1")
    assert h["trend"] == "insufficient_history" and h["n_appearances"] == 1


def test_progression_signals(inputs):
    by_exercise = {}
    for s in inputs["progression_signals"]:
        by_exercise.setdefault(s["exercise_name"], set()).add(s["signal"])

    assert "top_weight_increased" in by_exercise["Bench Press"]
    assert "volume_increased" in by_exercise["Bench Press"]
    assert "unusual_load_change" not in by_exercise["Bench Press"]  # +9% < 15%
    assert "recently_declined" in by_exercise["Curl"]
    assert "volume_decreased" in by_exercise["Curl"]
    assert "rep_range_missed" in by_exercise["Curl"]  # 8 reps < prescribed 10-12
    assert "stable" in by_exercise["Cable Row (Heavy)"]
    assert "new_exercise" in by_exercise["New Movement"]


def test_data_quality_signals(inputs):
    kinds = {s["kind"] for s in inputs["data_quality_signals"]}
    assert "inferred_sets" in kinds  # Leg Extension shorthand rows
    assert "bodyweight_exercises" in kinds
    assert "imperfect_parse" not in kinds
    assert "upcoming_row_has_logged_values" not in kinds


def test_unknown_day_raises(mini_df):
    with pytest.raises(ValueError):
        analytics.previous_workout_summary(mini_df, "W9U9")
    with pytest.raises(ValueError):
        analytics.exercise_history(mini_df, "Bench Press", "W9U9")
