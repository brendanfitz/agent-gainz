import pandas as pd
import pytest

from agent_gainz import defs, load, transforms


def _session(day, rows):
    return [dict(day=day, warmup_sets=1, rpe="8-9", rest_min=2,
                 notes=None, sub_1=None, sub_2=None, **r) for r in rows]


@pytest.fixture
def mini_df():
    """Hand-built 4-session fixture: 3 completed sessions + 1 upcoming (blank loads).

    Recurring exercises are shaped to hit every trend branch:
    - Bench Press: volume rising >5% per session (improving)
    - A1/A2 pair: superset + '(Heavy)' variant + embedded newline, stable loads
    - Leg Extension: shorthand expansion (1 entry, 2 declared sets) + drop set
    - Hanging Leg Raise: bodyweight (weight 0), reps rising (improving via reps)
    - Curl: volume falling (declining)
    - New Movement: appears only in the upcoming session (new)
    """
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
    rows += _session("W4U1", [
        dict(exercise="Bench Press", working_sets=1, reps="8-10", load=None),
        dict(exercise="A1: Cable Row\n(Heavy)", working_sets=1, reps="8-10", load=None),
        dict(exercise="A2: Lat Pulldown", working_sets=1, reps="10-12", load=None),
        dict(exercise="Leg Extension", working_sets=2, reps="10-12", load=None),
        dict(exercise="Hanging Leg Raise", working_sets=1, reps="10-15", load=None),
        dict(exercise="Curl", working_sets=1, reps="10-12", load=None),
        dict(exercise="New Movement", working_sets=2, reps="10-12", load=None),
    ])
    return (pd.DataFrame(rows)
            .pipe(load.assign_session_dates)
            .pipe(transforms.normalize_exercises)
            .pipe(transforms.parse_and_summarize))


@pytest.fixture
def logbook():
    """The real workbook, skipped when data/ is absent (it is gitignored)."""
    if not defs.DEFAULT_DATA_PATH.exists():
        pytest.skip("real workbook not available")
    return load.load_logbook()
