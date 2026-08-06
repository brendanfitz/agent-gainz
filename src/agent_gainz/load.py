"""Ingest the Essentials 4x logbook: header hygiene, synthetic dates, derived fields."""

from pathlib import Path

import pandas as pd

from agent_gainz import defs, transforms


def col_renamer(col: str) -> str:
    """Snake-case a spreadsheet header: 'Warm-up\\nSets' -> 'warmup_sets'."""
    return (col
            .lower()
            .replace(" ", "_")
            .replace("\n", "_")
            .replace("(", "")
            .replace(")", "")
            .replace("-", ""))


def read_raw(path: Path = defs.DEFAULT_DATA_PATH) -> pd.DataFrame:
    """Read the program sheet, clean headers, drop Jeff's prior-week columns."""
    return (pd.read_excel(path, sheet_name=defs.SHEET_NAME)
            .rename(columns=col_renamer)
            .drop(defs.DROPPED_COLS, axis=1))


def assign_session_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Insert a synthetic `date_day` column, one date per contiguous `day` block.

    The spreadsheet has no dates, so sessions get a Mon/Tue/Thu/Fri sequence
    starting at the program start. Not real session dates — ordering only.
    """
    session_number = df["day"].ne(df["day"].shift()).cumsum() - 1
    session_dates = pd.date_range(
        start=defs.PROGRAM_START,
        periods=session_number.max() + 1,
        freq=pd.offsets.CustomBusinessDay(weekmask=defs.WEEKMASK),
    )
    out = df.copy()
    out.insert(0, "date_day", session_number.map(dict(enumerate(session_dates))))
    return out


def load_logbook(path: Path = defs.DEFAULT_DATA_PATH, *, validate: bool = True) -> pd.DataFrame:
    """Load the workbook into the fully derived exercise-row frame (`df_parsed`).

    One row per programmed exercise-row, with prescribed fields, normalized
    exercise names, and every load-derived metric from the notebook's data
    dictionary. With `validate=True`, raises if the file breaks core invariants.
    """
    df = (read_raw(path)
          .pipe(assign_session_dates)
          .pipe(transforms.normalize_exercises)
          .pipe(transforms.parse_and_summarize))
    if validate:
        from agent_gainz import checks
        checks.assert_valid(df)
    return df
