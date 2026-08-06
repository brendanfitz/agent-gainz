import pandas as pd
import pytest

from agent_gainz import transforms


def test_workout_states(mini_df):
    states = transforms.workout_states(mini_df)
    assert list(states.day) == ["W1U1", "W2U1", "W3U1", "W4U1"]
    assert list(states.state) == ["completed"] * 3 + ["upcoming"]
    assert states.date_day.is_monotonic_increasing


def test_selectors(mini_df):
    assert transforms.next_upcoming(mini_df) == "W4U1"
    assert transforms.latest_completed(mini_df) == "W3U1"
    assert transforms.latest_completed(mini_df, before="W4U1") == "W3U1"
    assert transforms.latest_completed(mini_df, before="W2U1") == "W1U1"


def test_selectors_edge_cases(mini_df):
    all_logged = mini_df.query("day != 'W4U1'")
    assert transforms.next_upcoming(all_logged) is None
    assert transforms.latest_completed(mini_df, before="W1U1") is None
    with pytest.raises(ValueError):
        transforms.latest_completed(mini_df, before="W9U9")


def test_partially_logged_session_counts_as_completed(mini_df):
    # The user's MVP rule: any logged data in a session -> completed.
    partial = mini_df.assign(
        load=lambda d: d.load.mask(d.day.eq("W3U1") & d.exercise_name.ne("Bench Press"))
    ).pipe(transforms.parse_and_summarize)
    states = transforms.workout_states(partial)
    assert states.set_index("day").state["W3U1"] == "completed"
    assert transforms.latest_completed(partial) == "W3U1"


def test_simulate_upcoming_defaults_to_last_day(mini_df):
    completed = mini_df.query("day != 'W4U1'").reset_index(drop=True)
    sim = transforms.simulate_upcoming(completed)
    states = transforms.workout_states(sim)
    assert states.set_index("day").state["W3U1"] == "upcoming"
    assert (states.query("day != 'W3U1'").state == "completed").all()


def test_simulate_upcoming_leaves_other_days_untouched(mini_df):
    sim = transforms.simulate_upcoming(mini_df, day="W2U1")
    assert sim.query("day == 'W2U1'").parse_status.eq("empty").all()
    for day in ["W1U1", "W3U1"]:
        pd.testing.assert_frame_equal(
            sim.query("day == @day").reset_index(drop=True),
            mini_df.query("day == @day").reset_index(drop=True))


def test_simulate_upcoming_unknown_day(mini_df):
    with pytest.raises(ValueError):
        transforms.simulate_upcoming(mini_df, day="W9U9")
