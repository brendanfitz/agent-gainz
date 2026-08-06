"""LLM-free pre-workout report rendered from the analytics bundle."""


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _previous_section(prev: dict | None) -> list[str]:
    if prev is None:
        return ["## Previous Workout", "", "No completed workout on record.", ""]
    lines = [
        "## Previous Workout",
        "",
        f"**{prev['day']}** ({prev['date']}) — {prev['n_exercises']} exercises, "
        f"{prev['n_working_sets']} working sets, {prev['n_drop_sets']} drop sets, "
        f"{prev['total_reps']} total reps.",
        "",
        "| Exercise | Top weight | Reps @ top | Total reps | Volume | Drop set |",
        "|---|---|---|---|---|---|",
    ]
    for e in prev["exercises"]:
        lines.append(f"| {e['exercise_name']} | {_fmt(e['weight_top'])} "
                     f"| {_fmt(e['reps_at_top'])} | {_fmt(e['reps_total'])} "
                     f"| {_fmt(e['volume_load'])} | {'yes' if e['has_dropset'] else ''} |")
    lines.append("")
    if prev["notable_changes"]:
        lines.append("Notable changes vs each exercise's prior appearance:")
        for c in prev["notable_changes"]:
            lines.append(f"- {c['exercise_name']}: {c['metric']} "
                         f"{_fmt(c['prior'])} -> {_fmt(c['latest'])} "
                         f"({c['pct_change']:+.1f}%)")
        lines.append("")
    if prev["exercises_with_notes"]:
        lines.append(f"Notes were logged on: {', '.join(prev['exercises_with_notes'])}.")
        lines.append("")
    return lines


def _upcoming_section(today: dict) -> list[str]:
    lines = [
        "## Today's Workout",
        "",
        f"**{today['day']}** — week {today['week']}, {today['split']} session, "
        f"{today['n_exercises']} exercises.",
        "",
        "| Exercise | Warm-up | Sets | Reps | RPE | Rest (min) | Substitutes |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in today["exercises"]:
        subs = ", ".join(e["substitutes"]) if e["substitutes"] else "-"
        lines.append(f"| {e['exercise_name']} | {_fmt(e['warmup_sets'])} "
                     f"| {_fmt(e['working_sets'])} | {_fmt(e['reps'])} "
                     f"| {_fmt(e['rpe'])} | {_fmt(e['rest_min'])} | {subs} |")
    lines.append("")
    if today["superset_pairs"]:
        pairs = "; ".join(" + ".join(p) for p in today["superset_pairs"])
        lines.append(f"Supersets: {pairs}.")
        lines.append("")
    for n in today["notes"]:
        lines.append(f"- Note on {n['exercise_name']}: {n['note']}")
    if today["notes"]:
        lines.append("")
    return lines


def _history_section(histories: dict) -> list[str]:
    lines = ["## Exercise Comparisons", ""]
    for name, h in histories.items():
        if h["trend"] == "new":
            lines.append(f"- **{name}**: new — no completed history.")
            continue
        latest = h["appearances"][-1]
        desc = (f"last done {latest['day']}: top {_fmt(latest['weight_top'])} "
                f"x {_fmt(latest['reps_at_top'])}, volume {_fmt(latest['volume_load'])}")
        trend = h["trend"].replace("_", " ")
        metric_note = " (judged on reps — bodyweight)" if h["is_bodyweight"] else ""
        lines.append(f"- **{name}**: {desc} — {trend} over {h['n_appearances']} "
                     f"appearance(s){metric_note}.")
    lines.append("")
    return lines


def _signal_section(title: str, signals: list[dict], key: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not signals:
        lines += ["Nothing to flag.", ""]
        return lines
    for s in signals:
        prefix = f"{s[key]}: " if s.get(key) else ""
        detail = s.get("detail", "")
        label = s.get("signal") or s.get("kind")
        lines.append(f"- {prefix}**{label}** — {detail}")
    lines.append("")
    return lines


def render_report(inputs: dict) -> str:
    """Deterministic markdown pre-workout report (Phase 2 — no LLM involved)."""
    lines = [f"# Pre-Workout Report — {inputs['upcoming_day']}", ""]
    lines += _previous_section(inputs["previous_workout"])
    lines += _upcoming_section(inputs["upcoming_workout"])
    lines += _history_section(inputs["exercise_histories"])
    lines += _signal_section("Progression Signals", inputs["progression_signals"],
                             "exercise_name")
    lines += _signal_section("Data Quality", inputs["data_quality_signals"],
                             "exercise_name")
    return "\n".join(lines).rstrip() + "\n"
