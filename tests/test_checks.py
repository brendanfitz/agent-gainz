import pytest

from agent_gainz import checks, defs, transforms


def test_mini_fixture_is_valid(mini_df):
    assert checks.validate_logbook(mini_df, full_program=False) == []


def test_missing_columns_reported(mini_df):
    issues = checks.validate_logbook(mini_df.drop(columns=["weight_top", "superset"]),
                                     full_program=False)
    assert len(issues) == 1
    assert "missing columns" in issues[0]


def test_bad_day_format_reported(mini_df):
    broken = mini_df.assign(day=lambda d: d.day.str.replace("W4U1", "week4"))
    issues = checks.validate_logbook(broken, full_program=False)
    assert any("not matching" in i for i in issues)


def test_duplicate_exercise_reported(mini_df):
    dupe = transforms.parse_and_summarize(
        mini_df.assign(exercise=lambda d: d.exercise.str.replace("Curl", "Bench Press"))
        .pipe(transforms.normalize_exercises))
    issues = checks.validate_logbook(dupe, full_program=False)
    assert any("duplicate" in i for i in issues)


def test_set_count_mismatch_reported(mini_df):
    broken = mini_df.assign(working_sets=lambda d: d.working_sets.where(
        d.exercise_name != "Bench Press", 3))
    issues = checks.validate_logbook(broken, full_program=False)
    assert any("recovered sets" in i for i in issues)


def test_assert_valid_raises(mini_df):
    with pytest.raises(ValueError, match="missing columns"):
        checks.assert_valid(mini_df.drop(columns=["weight_top"]), full_program=False)


def test_data_notes(mini_df):
    notes = checks.data_notes(mini_df)
    assert notes["bodyweight_exercises"] == ["Hanging Leg Raise"]
    assert notes["n_rows_sets_inferred"] == 3  # Leg Extension x 3 sessions


def test_real_workbook_invariants(logbook):
    assert checks.validate_logbook(logbook) == []
    assert len(logbook) == defs.N_ROWS
    assert (logbook.parse_status == "ok").all()
    states = transforms.workout_states(logbook)
    assert len(states) == defs.N_SESSIONS
    assert (states.state == "completed").all()
    assert transforms.next_upcoming(logbook) is None
