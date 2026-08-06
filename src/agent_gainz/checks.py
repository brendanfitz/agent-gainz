"""Validation helpers for the parsed logbook frame."""

import pandas as pd

from agent_gainz import defs, transforms

REQUIRED_COLS = ["date_day", "day", "exercise", "warmup_sets", "working_sets",
                 "reps", "load", "rpe", "rest_min", "notes", "sub_1", "sub_2",
                 "superset", "exercise_name", "exercise_base",
                 *transforms.DERIVED_COLS]


def validate_logbook(df_parsed: pd.DataFrame, *, full_program: bool = True) -> list[str]:
    """Return human-readable structural problems; an empty list means valid.

    With `full_program=True`, also enforce the known 12-week shape (48 sessions,
    288 rows) — turn it off for fixtures and partial extracts.
    """
    issues: list[str] = []

    missing = [c for c in REQUIRED_COLS if c not in df_parsed.columns]
    if missing:
        issues.append(f"missing columns: {missing}")
        return issues  # nothing below is trustworthy without them

    if df_parsed.date_day.isna().any():
        issues.append("null date_day values")
    if (df_parsed.groupby("day").date_day.nunique() > 1).any():
        issues.append("day blocks with more than one date_day")

    bad_days = df_parsed.loc[~df_parsed.day.str.fullmatch(defs.DAY_RE), "day"].unique()
    if len(bad_days):
        issues.append(f"day values not matching W<week><U|L><slot>: {list(bad_days)}")

    unknown = set(df_parsed.parse_status) - defs.PARSE_STATUSES
    if unknown:
        issues.append(f"unknown parse_status values: {sorted(unknown)}")

    logged = df_parsed[df_parsed.parse_status.isin(defs.LOGGED_PARSE_STATUSES)]
    not_ok = logged[logged.parse_status != "ok"]
    if len(not_ok):
        issues.append(
            f"{len(not_ok)} logged rows with parse_status != ok: "
            f"{not_ok.parse_status.value_counts().to_dict()}")

    mismatched = logged[logged.n_working_sets != logged.working_sets]
    if len(mismatched):
        issues.append(
            f"{len(mismatched)} rows where recovered sets != prescribed working_sets: "
            f"{mismatched[['day', 'exercise_name']].to_dict('records')}")

    dupes = df_parsed[df_parsed.duplicated(["day", "exercise_name"], keep=False)]
    if len(dupes):
        issues.append(f"duplicate (day, exercise_name) rows: "
                      f"{dupes[['day', 'exercise_name']].to_dict('records')}")

    if full_program:
        if len(df_parsed) != defs.N_ROWS:
            issues.append(f"expected {defs.N_ROWS} rows, found {len(df_parsed)}")
        n_sessions = len(df_parsed[["day", "date_day"]].drop_duplicates())
        if n_sessions != defs.N_SESSIONS:
            issues.append(f"expected {defs.N_SESSIONS} sessions, found {n_sessions}")

    return issues


def assert_valid(df_parsed: pd.DataFrame, *, full_program: bool = True) -> None:
    """Raise ValueError listing every structural problem found."""
    issues = validate_logbook(df_parsed, full_program=full_program)
    if issues:
        raise ValueError("logbook validation failed:\n- " + "\n- ".join(issues))


def data_notes(df_parsed: pd.DataFrame) -> dict:
    """Informational (non-failing) facts consumers should be aware of."""
    logged = df_parsed[df_parsed.parse_status.isin(defs.LOGGED_PARSE_STATUSES)]
    return {
        "bodyweight_exercises": sorted(
            logged.loc[logged.weight_top.eq(0), "exercise_name"].unique()),
        "n_rows_sets_inferred": int(logged.sets_inferred.sum()),
        "n_rows_with_notes": int(df_parsed.notes.notna().sum()),
    }
