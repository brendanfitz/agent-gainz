"""Derived fields: load-string parsing, per-set expansion, exercise-row summaries."""

import re

import pandas as pd

from agent_gainz import defs


def parse_load(raw: object, declared_sets: object = None) -> tuple[list[dict], str]:
    """Parse one `load` cell into a list of set dicts plus a parse status.

    Each set is {set_num, kind, drop_num, weight, reps, inferred}. On a drop set,
    `set_num` points at the working set it hung off of. `inferred` marks sets that
    were filled in from `declared_sets` rather than written down.

    Status is one of: ok / partial (leftover text) / weight_only (bare number,
    no reps) / unparsed / empty.
    """
    # `load` is a str-dtype column, so a blank cell arrives as pd.NA, not float nan.
    if raw is None or pd.isna(raw):
        return [], "empty"

    text = str(raw).strip()
    if not text:
        return [], "empty"

    sets: list[dict] = []
    spans: list[tuple[int, int]] = []
    set_num = drop_num = 0

    for m in defs.SET_RE.finditer(text):
        spans.append(m.span())
        weight, reps = float(m.group("weight")), int(m.group("reps"))
        for _ in range(int(m.group("repeat") or 1)):
            if m.group("drop"):
                drop_num += 1
                kind, num = "drop", set_num
            else:
                set_num, drop_num = set_num + 1, 0
                kind, num = "working", set_num
            sets.append(dict(set_num=num, kind=kind, drop_num=drop_num,
                             weight=weight, reps=reps, inferred=False))

    # Anything left over that isn't a separator means we didn't understand the cell.
    covered = set(i for start, end in spans for i in range(start, end))
    leftover = "".join(c for i, c in enumerate(text)
                       if i not in covered and c not in defs.SEPARATORS)

    if not sets:
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            # Bare number: weight logged, reps never were.
            return [dict(set_num=1, kind="working", drop_num=0,
                         weight=float(text), reps=pd.NA, inferred=False)], "weight_only"
        return [], "unparsed"

    status = "ok" if not leftover else "partial"

    # Shorthand: one entry logged but the program called for more sets -> repeat it.
    # Any drop set stays attached to the final working set only.
    if declared_sets is not None and not pd.isna(declared_sets):
        working = [s for s in sets if s["kind"] == "working"]
        missing = int(declared_sets) - len(working)
        if len(working) == 1 and missing > 0:
            template = working[0]
            extra = [dict(template, set_num=template["set_num"] + i, inferred=True)
                     for i in range(1, missing + 1)]
            drops = [dict(s, set_num=template["set_num"] + missing)
                     for s in sets if s["kind"] == "drop"]
            sets = working + extra + drops

    return sets, status


def build_sets(df: pd.DataFrame, load_col: str = "load", sets_col: str = "working_sets",
               id_cols: list[str] = defs.ID_COLS) -> pd.DataFrame:
    """Tidy frame: one row per logged set."""
    rows = []
    for idx, raw in df[load_col].items():
        parsed, status = parse_load(raw, df.at[idx, sets_col] if sets_col in df else None)
        base = {"row_id": idx, **{c: df.at[idx, c] for c in id_cols if c in df}}
        if not parsed:
            parsed = [dict(set_num=pd.NA, kind=pd.NA, drop_num=pd.NA,
                           weight=pd.NA, reps=pd.NA, inferred=False)]
        rows += [{**base, **s, "parse_status": status, "load_raw": raw} for s in parsed]

    return (pd.DataFrame(rows)
            .sort_values(["row_id", "set_num", "drop_num"])
            .reset_index(drop=True)
            .assign(volume_load=lambda d: d.weight * d.reps))


def summarize_sets(sets: pd.DataFrame) -> pd.DataFrame:
    """Collapse the tidy set frame back to one row per exercise-row."""
    work = sets[sets.kind == "working"]
    drop = sets[sets.kind == "drop"]

    summary = pd.DataFrame({
        "parse_status": sets.groupby("row_id").parse_status.first(),
        "n_working_sets": work.groupby("row_id").size(),
        "n_drop_sets": drop.groupby("row_id").size(),
        "weights": work.groupby("row_id").weight.apply(tuple),
        "weight_changed": work.groupby("row_id").weight.nunique() > 1,
        "weight_first": work.groupby("row_id").weight.first(),
        "weight_top": work.groupby("row_id").weight.max(),
        "reps_total": work.groupby("row_id").reps.sum(min_count=1),
        "volume_load": work.groupby("row_id").volume_load.sum(min_count=1),
        "volume_load_incl_drops": sets.groupby("row_id").volume_load.sum(min_count=1),
        "drop_weight": drop.groupby("row_id").weight.first(),
        "drop_reps": drop.groupby("row_id").reps.first(),
        "sets_inferred": work.groupby("row_id").inferred.any(),
    })
    # Reps recorded at the heaviest working set (last set at that weight if tied).
    top = (work.sort_values(["weight", "set_num"])
               .groupby("row_id").last()[["reps"]].rename(columns={"reps": "reps_at_top"}))

    return (summary.join(top)
                   .assign(n_drop_sets=lambda d: d.n_drop_sets.fillna(0).astype(int),
                           n_working_sets=lambda d: d.n_working_sets.fillna(0).astype(int),
                           weight_changed=lambda d: d.weight_changed.fillna(False),
                           sets_inferred=lambda d: d.sets_inferred.fillna(False),
                           has_dropset=lambda d: d.n_drop_sets > 0)
                   .rename_axis(None))


DERIVED_COLS = ["parse_status", "n_working_sets", "n_drop_sets", "weights",
                "weight_changed", "weight_first", "weight_top", "reps_total",
                "volume_load", "volume_load_incl_drops", "drop_weight", "drop_reps",
                "sets_inferred", "reps_at_top", "has_dropset"]


def parse_and_summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Attach every load-derived column to the exercise-row frame."""
    return df.drop(columns=DERIVED_COLS, errors="ignore").pipe(
        lambda d: d.join(summarize_sets(build_sets(d))))


def normalize_exercises(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized exercise-name columns; the raw `exercise` stays untouched.

    - `superset`: the 'A1'/'A2' tag, or NA — workout structure, not identity.
    - `exercise_name`: tag stripped, embedded newlines collapsed to spaces.
      Canonical comparison key; '(Heavy)'/'(Back-off)' variants stay distinct
      because their loads are not comparable.
    - `exercise_base`: parenthetical variant removed — display/grouping only.
    """
    stripped = df["exercise"].str.replace(r"\s+", " ", regex=True).str.strip()
    tag = stripped.str.extract(defs.SUPERSET_RE)["tag"]
    name = stripped.str.replace(defs.SUPERSET_RE, "", regex=True)
    base = name.str.replace(r"\s*\([^)]*\)\s*$", "", regex=True)
    return df.assign(superset=tag, exercise_name=name, exercise_base=base)


def workout_states(df_parsed: pd.DataFrame) -> pd.DataFrame:
    """One row per session, in program order, with its completion state.

    A session is 'completed' if any of its rows carry parsed load data,
    'upcoming' if none do. Completed sessions with unlogged rows are a
    data-quality concern, not a separate state.
    """
    return (df_parsed
            .assign(logged=lambda d: d.parse_status.isin(defs.LOGGED_PARSE_STATUSES))
            .groupby(["day", "date_day"], sort=False)
            .agg(n_exercises=("exercise", "size"), n_logged=("logged", "sum"))
            .reset_index()
            .sort_values("date_day", ignore_index=True)
            .assign(state=lambda d: d.n_logged.gt(0).map({True: "completed", False: "upcoming"})))


def next_upcoming(df_parsed: pd.DataFrame) -> str | None:
    """The first upcoming session's `day` key, or None if everything is logged."""
    states = workout_states(df_parsed)
    upcoming = states[states.state == "upcoming"]
    return None if upcoming.empty else upcoming.iloc[0]["day"]


def latest_completed(df_parsed: pd.DataFrame, before: str | None = None) -> str | None:
    """The most recent completed session's `day` key, optionally before `before`."""
    states = workout_states(df_parsed)
    if before is not None:
        cutoff = states.index[states.day == before]
        if cutoff.empty:
            raise ValueError(f"unknown day: {before!r}")
        states = states.iloc[:cutoff[0]]
    completed = states[states.state == "completed"]
    return None if completed.empty else completed.iloc[-1]["day"]


def simulate_upcoming(df_parsed: pd.DataFrame, day: str | None = None) -> pd.DataFrame:
    """Blank one session's logged loads to simulate an upcoming workout.

    Defaults to the last session in program order. Derived columns are re-run
    from scratch so parse statuses and NA metrics stay mutually consistent.
    """
    if day is None:
        day = workout_states(df_parsed).iloc[-1]["day"]
    if not (df_parsed.day == day).any():
        raise ValueError(f"unknown day: {day!r}")
    return (df_parsed
            .assign(load=lambda d: d.load.mask(d.day == day))
            .pipe(parse_and_summarize))
