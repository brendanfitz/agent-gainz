"""Deterministic pre-workout analytics.

Every public function returns plain JSON-serializable dicts/lists — these
payloads feed the LLM-free report and become the coach agent's tool output
verbatim, so no numbers are ever computed by the model.
"""

import re

import numpy as np
import pandas as pd

from agent_gainz import defs, transforms

REP_RANGE_RE = re.compile(r"(?P<low>\d+)\s*-\s*(?P<high>\d+)")


def _jsonify(obj: object) -> object:
    """Recursively convert pandas/numpy values into JSON-native ones."""
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, pd.Timestamp):
        return obj.date().isoformat()
    if isinstance(obj, np.generic):
        obj = obj.item()
    if obj is None or isinstance(obj, (str, bool, int, float)):
        if isinstance(obj, float) and np.isnan(obj):
            return None
        return obj
    if pd.isna(obj):
        return None
    raise TypeError(f"cannot jsonify {type(obj)}: {obj!r}")


def _session_days(df_parsed: pd.DataFrame) -> list[str]:
    """Session `day` keys in program (date) order."""
    return list(transforms.workout_states(df_parsed).day)


def _exercise_row_dict(r: pd.Series) -> dict:
    return dict(
        exercise_name=r.exercise_name, superset=r.superset,
        weight_top=r.weight_top, reps_at_top=r.reps_at_top,
        reps_total=r.reps_total, volume_load=r.volume_load,
        n_working_sets=r.n_working_sets, has_dropset=r.has_dropset,
        weight_changed=r.weight_changed, sets_inferred=r.sets_inferred,
        note=r.notes)


def parse_rep_range(reps: object) -> tuple[int, int] | None:
    """'10-12 (drop set)' -> (10, 12); None when no range is present."""
    if pd.isna(reps):
        return None
    m = REP_RANGE_RE.search(str(reps))
    return (int(m["low"]), int(m["high"])) if m else None


def _rel_change(prior: float | None, latest: float | None) -> float | None:
    if prior is None or latest is None or pd.isna(prior) or pd.isna(latest) or prior == 0:
        return None
    return (latest - prior) / prior


def previous_workout_summary(df_parsed: pd.DataFrame, day: str) -> dict:
    """What happened in one completed session, plus notable changes vs prior."""
    rows = df_parsed[df_parsed.day == day]
    if rows.empty:
        raise ValueError(f"unknown day: {day!r}")

    notable = []
    for _, r in rows.iterrows():
        hist = exercise_history(df_parsed, r.exercise_name, day, n_recent=1)
        if not hist["appearances"]:
            continue
        prior = hist["appearances"][-1]
        for metric in ["volume_load", "weight_top"]:
            rel = _rel_change(prior[metric], r[metric])
            if rel is not None and abs(rel) > defs.VOLUME_DELTA_MEANINGFUL:
                notable.append(dict(
                    exercise_name=r.exercise_name, metric=metric,
                    prior=prior[metric], latest=r[metric],
                    pct_change=round(rel * 100, 1),
                    direction="up" if rel > 0 else "down"))

    return _jsonify(dict(
        day=day,
        date=rows.date_day.iloc[0],
        n_exercises=len(rows),
        n_working_sets=rows.n_working_sets.sum(),
        n_drop_sets=rows.n_drop_sets.sum(),
        total_reps=rows.reps_total.sum(),
        exercises=[_exercise_row_dict(r) for _, r in rows.iterrows()],
        exercises_with_notes=list(rows.loc[rows.notes.notna(), "exercise_name"]),
        exercises_with_weight_change=list(rows.loc[rows.weight_changed, "exercise_name"]),
        notable_changes=notable))


def upcoming_workout_preview(df_parsed: pd.DataFrame, day: str) -> dict:
    """The prescription for one session — no performance data."""
    rows = df_parsed[df_parsed.day == day]
    if rows.empty:
        raise ValueError(f"unknown day: {day!r}")

    m = defs.DAY_RE.fullmatch(day)
    supersets: list[list[str]] = []
    for _, r in rows[rows.superset.notna()].iterrows():
        if r.superset.endswith("1") or not supersets:
            supersets.append([])
        supersets[-1].append(r.exercise_name)

    return _jsonify(dict(
        day=day,
        date=rows.date_day.iloc[0],
        week=int(m["week"]) if m else None,
        split={"U": "upper", "L": "lower"}.get(m["split"]) if m else None,
        n_exercises=len(rows),
        exercises=[dict(
            exercise_name=r.exercise_name, superset=r.superset,
            warmup_sets=r.warmup_sets, working_sets=r.working_sets,
            reps=r.reps, rep_range=parse_rep_range(r.reps),
            rpe=r.rpe, rest_min=r.rest_min,
            substitutes=[s for s in [r.sub_1, r.sub_2] if pd.notna(s)],
            note=r.notes) for _, r in rows.iterrows()],
        superset_pairs=supersets,
        notes=[dict(exercise_name=r.exercise_name, note=r.notes)
               for _, r in rows.iterrows() if pd.notna(r.notes)]))


def exercise_history(df_parsed: pd.DataFrame, exercise_name: str, upcoming_day: str,
                     n_recent: int = defs.TREND_WINDOW) -> dict:
    """Recent completed appearances of one exercise strictly before `upcoming_day`.

    Appearances come back oldest-to-newest. `trend` is one of new /
    insufficient_history / improving / stable / declining, judged on volume
    load with a dead-band — or on total reps for bodyweight movements, where
    volume is always zero.
    """
    days = _session_days(df_parsed)
    if upcoming_day not in days:
        raise ValueError(f"unknown day: {upcoming_day!r}")
    prior_days = days[:days.index(upcoming_day)]

    hist = (df_parsed
            [df_parsed.exercise_name.eq(exercise_name)
             & df_parsed.day.isin(prior_days)
             & df_parsed.parse_status.isin(defs.LOGGED_PARSE_STATUSES)]
            .sort_values("date_day")
            .tail(n_recent))

    appearances = [dict(day=r.day, date=r.date_day, **_exercise_row_dict(r),
                        parse_status=r.parse_status) for _, r in hist.iterrows()]

    is_bodyweight = bool(len(hist)) and bool(hist.weight_top.eq(0).all())
    metric = "reps_total" if is_bodyweight else "volume_load"

    if hist.empty:
        trend = "new"
    elif len(hist) < defs.MIN_HISTORY:
        trend = "insufficient_history"
    else:
        rel = _rel_change(hist[metric].iloc[0], hist[metric].iloc[-1])
        if rel is None:
            trend = "insufficient_history"
        elif rel > defs.VOLUME_DELTA_MEANINGFUL:
            trend = "improving"
        elif rel < -defs.VOLUME_DELTA_MEANINGFUL:
            trend = "declining"
        else:
            trend = "stable"

    deltas = None
    if len(hist) >= 2:
        prior, latest = hist.iloc[-2], hist.iloc[-1]
        deltas = {c: (None if pd.isna(latest[c]) or pd.isna(prior[c])
                      else float(latest[c]) - float(prior[c]))
                  for c in ["weight_top", "reps_at_top", "reps_total", "volume_load"]}

    return _jsonify(dict(
        exercise_name=exercise_name,
        n_appearances=len(hist),
        appearances=appearances,
        deltas=deltas,
        trend=trend,
        trend_metric=metric,
        is_bodyweight=is_bodyweight))


def progression_signals(df_parsed: pd.DataFrame, upcoming_day: str) -> list[dict]:
    """Per-exercise signals for today's prescription, from recent history."""
    signals = []

    def add(name: str, signal: str, detail: str) -> None:
        signals.append(dict(exercise_name=name, signal=signal, detail=detail))

    for _, row in df_parsed[df_parsed.day == upcoming_day].iterrows():
        name = row.exercise_name
        h = exercise_history(df_parsed, name, upcoming_day)

        if h["trend"] == "new":
            add(name, "new_exercise", "no completed history for this exercise")
            continue
        if h["trend"] == "insufficient_history":
            add(name, "insufficient_history",
                f"only {h['n_appearances']} completed appearance(s)")
            continue

        latest, prior = h["appearances"][-1], h["appearances"][-2]
        d = h["deltas"]

        if d["weight_top"] and d["weight_top"] > 0:
            add(name, "top_weight_increased",
                f"top weight {prior['weight_top']} -> {latest['weight_top']}")
        if d["weight_top"] == 0 and d["reps_at_top"] and d["reps_at_top"] > 0:
            add(name, "reps_increased_at_same_weight",
                f"{prior['reps_at_top']} -> {latest['reps_at_top']} reps "
                f"at {latest['weight_top']}")

        rel_vol = _rel_change(prior[h["trend_metric"]], latest[h["trend_metric"]])
        if rel_vol is not None and rel_vol > defs.VOLUME_DELTA_MEANINGFUL:
            add(name, "volume_increased",
                f"{h['trend_metric']} {prior[h['trend_metric']]} -> "
                f"{latest[h['trend_metric']]} ({rel_vol:+.0%})")
        if rel_vol is not None and rel_vol < -defs.VOLUME_DELTA_MEANINGFUL:
            add(name, "volume_decreased",
                f"{h['trend_metric']} {prior[h['trend_metric']]} -> "
                f"{latest[h['trend_metric']]} ({rel_vol:+.0%})")

        rng = parse_rep_range(row.reps)
        if rng and latest["reps_at_top"] is not None and latest["reps_at_top"] < rng[0]:
            add(name, "rep_range_missed",
                f"last time: {latest['reps_at_top']} reps at top weight, "
                f"prescribed {rng[0]}-{rng[1]}")

        if h["trend"] == "stable":
            add(name, "stable", f"{h['trend_metric']} flat over last "
                                f"{h['n_appearances']} appearances")
        if h["trend"] == "declining":
            add(name, "recently_declined", f"{h['trend_metric']} down over last "
                                          f"{h['n_appearances']} appearances")

        if latest["has_dropset"] and not prior["has_dropset"]:
            add(name, "drop_set_added", "drop set logged last time but not the time before")

        rel_w = _rel_change(prior["weight_top"], latest["weight_top"])
        if rel_w is not None and abs(rel_w) > defs.UNUSUAL_LOAD_JUMP:
            add(name, "unusual_load_change",
                f"top weight changed {rel_w:+.0%} in one session — worth confirming")

    return _jsonify(signals)


def data_quality_signals(df_parsed: pd.DataFrame, upcoming_day: str) -> list[dict]:
    """Caveats the coach should know about before trusting the numbers."""
    signals = []

    def add(kind: str, detail: str, **extra: object) -> None:
        signals.append(dict(kind=kind, detail=detail, **extra))

    logged = df_parsed[df_parsed.parse_status.isin(defs.LOGGED_PARSE_STATUSES)]
    today = df_parsed[df_parsed.day == upcoming_day]
    today_names = list(today.exercise_name)

    not_ok = logged[logged.parse_status != "ok"]
    for _, r in not_ok.iterrows():
        add("imperfect_parse", f"load {r.load!r} parsed as {r.parse_status}",
            exercise_name=r.exercise_name, day=r.day)

    n_inferred = int(logged.loc[logged.exercise_name.isin(today_names),
                                "sets_inferred"].sum())
    if n_inferred:
        add("inferred_sets",
            f"{n_inferred} historical rows for today's exercises logged one set "
            "shorthand-expanded to the prescribed count; per-set detail is inferred")

    bw = sorted(set(today_names) & set(logged.loc[logged.weight_top.eq(0), "exercise_name"]))
    if bw:
        add("bodyweight_exercises",
            "weight is 0 (bodyweight) so volume load is uninformative; "
            "progress is judged on reps", exercises=bw)

    collapsed = (df_parsed.exercise_name.str.casefold()
                 .str.replace(r"\s+", " ", regex=True))
    inconsistent = (df_parsed.groupby(collapsed).exercise_name.nunique()
                    .loc[lambda s: s > 1].index.tolist())
    if inconsistent:
        add("name_inconsistencies",
            f"same exercise spelled multiple ways: {inconsistent}")

    states = transforms.workout_states(df_parsed)
    completed_days = set(states.loc[states.state == "completed", "day"])
    gaps = df_parsed[df_parsed.day.isin(completed_days)
                     & ~df_parsed.parse_status.isin(defs.LOGGED_PARSE_STATUSES)]
    for _, r in gaps.iterrows():
        add("completed_row_missing_load",
            "session has logged data but this exercise has none",
            exercise_name=r.exercise_name, day=r.day)

    stray = today[today.parse_status.isin(defs.LOGGED_PARSE_STATUSES)]
    for _, r in stray.iterrows():
        add("upcoming_row_has_logged_values",
            f"upcoming workout already contains load {r.load!r}",
            exercise_name=r.exercise_name, day=r.day)

    for _, r in today[today.notes.notna()].iterrows():
        add("note_on_upcoming", f"note on today's plan: {r.notes!r}",
            exercise_name=r.exercise_name, day=r.day)

    return _jsonify(signals)


def build_briefing_inputs(df_parsed: pd.DataFrame) -> dict:
    """Everything the report renderer and the coach agent need, in one bundle."""
    upcoming = transforms.next_upcoming(df_parsed)
    if upcoming is None:
        raise ValueError("no upcoming workout: every session has logged data")
    latest = transforms.latest_completed(df_parsed, before=upcoming)

    today_names = list(df_parsed.loc[df_parsed.day == upcoming, "exercise_name"])
    return dict(
        upcoming_day=upcoming,
        latest_day=latest,
        previous_workout=(previous_workout_summary(df_parsed, latest)
                          if latest else None),
        upcoming_workout=upcoming_workout_preview(df_parsed, upcoming),
        exercise_histories={name: exercise_history(df_parsed, name, upcoming)
                            for name in today_names},
        progression_signals=progression_signals(df_parsed, upcoming),
        data_quality_signals=data_quality_signals(df_parsed, upcoming))
