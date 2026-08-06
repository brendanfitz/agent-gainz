import pandas as pd
import pytest

from agent_gainz import defs, load, transforms


def _session(day, rows):
    return [dict(day=day, warmup_sets=1, rpe="8-9", rest_min=2,
                 notes=None, sub_1=None, sub_2=None, **r) for r in rows]


def _finalize(rows):
    return (pd.DataFrame(rows)
            .pipe(load.assign_session_dates)
            .pipe(transforms.normalize_exercises)
            .pipe(transforms.parse_and_summarize))


def _w4u1_rows(loads):
    return _session("W4U1", [
        dict(exercise="Bench Press", working_sets=1, reps="8-10", load=loads[0]),
        dict(exercise="A1: Cable Row\n(Heavy)", working_sets=1, reps="8-10", load=loads[1]),
        dict(exercise="A2: Lat Pulldown", working_sets=1, reps="10-12", load=loads[2]),
        dict(exercise="Leg Extension", working_sets=2, reps="10-12", load=loads[3]),
        dict(exercise="Hanging Leg Raise", working_sets=1, reps="10-15", load=loads[4]),
        dict(exercise="Curl", working_sets=1, reps="10-12", load=loads[5]),
        dict(exercise="New Movement", working_sets=2, reps="10-12", load=loads[6]),
    ])


def _history_rows():
    rows = []
    bench = ["100R10", "110R10", "120R10"]
    hlr = ["0R10", "0R12", "0R14"]
    curl = ["35R12", "30R12", "30R8"]  # last session drops below the 10-12 prescription
    for i, day in enumerate(["W1U1", "W2U1", "W3U1"]):
        rows += _session(day, [
            dict(exercise="Bench Press", working_sets=1, reps="8-10", load=bench[i]),
            dict(exercise="A1: Cable Row\n(Heavy)", working_sets=1, reps="8-10", load="80R10"),
            dict(exercise="A2: Lat Pulldown", working_sets=1, reps="10-12", load="60R12"),
            dict(exercise="Leg Extension", working_sets=2, reps="10-12", load="90R12\n▼60R12"),
            dict(exercise="Hanging Leg Raise", working_sets=1, reps="10-15", load=hlr[i]),
            dict(exercise="Curl", working_sets=1, reps="10-12", load=curl[i]),
        ])
    return rows


def build_mini_df():
    """3 completed sessions + 1 upcoming (blank loads).

    Recurring exercises are shaped to hit every trend branch:
    - Bench Press: volume rising >5% per session (improving)
    - A1/A2 pair: superset + '(Heavy)' variant + embedded newline, stable loads
    - Leg Extension: shorthand expansion (1 entry, 2 declared sets) + drop set
    - Hanging Leg Raise: bodyweight (weight 0), reps rising (improving via reps)
    - Curl: volume falling and last reps below prescription (declining)
    - New Movement: appears only in the upcoming session (new)
    """
    return _finalize(_history_rows() + _w4u1_rows([None] * 7))


def build_mini_df_completed():
    """Same program, but W4U1 performed — one load per outcome branch:

    Bench progressed (weight up), Cable Row and Lat Pulldown repeated,
    Leg Extension regressed (90 -> 80), Hanging Leg Raise repeated (bodyweight),
    Curl not performed, New Movement first appearance (no prior).
    """
    return _finalize(_history_rows() + _w4u1_rows(
        ["125R10", "80R10", "60R12", "80R12\n▼60R12", "0R14", None, "50R10"]))


@pytest.fixture
def mini_df():
    return build_mini_df()


@pytest.fixture
def mini_df_completed():
    return build_mini_df_completed()


@pytest.fixture
def logbook():
    """The real workbook, skipped when data/ is absent (it is gitignored)."""
    if not defs.DEFAULT_DATA_PATH.exists():
        pytest.skip("real workbook not available")
    return load.load_logbook()
