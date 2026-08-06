"""Post-workout review: compare a briefing's recommendations with what
actually happened, collect followed/usefulness feedback, append to JSONL.

Works because the run record's day exists fully logged in the real workbook
(the briefing was generated against a simulated blank of it), so the actual
performance is simply read back from the un-simulated frame.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from agent_gainz import analytics, defs

SCHEMA_VERSION = 1
BASE_NAME_RE = re.compile(r"\s*\([^)]*\)\s*$")
METRIC_KEYS = ["weight_top", "reps_at_top", "reps_total", "volume_load"]


def normalize_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().strip(".!?,;:").casefold()


def resolve_area(area: str, exercises: list[dict]) -> str | None:
    """Map a recommendation area onto a performed exercise_name, or None for
    workout-level / unrecognized areas."""
    target = normalize_name(area)
    by_name = {normalize_name(e["exercise_name"]): e["exercise_name"]
               for e in exercises}
    if target in by_name:
        return by_name[target]
    by_base = {normalize_name(BASE_NAME_RE.sub("", e["exercise_name"])): e["exercise_name"]
               for e in exercises}
    return by_base.get(target)


def classify_outcome(actual: dict | None, prior: dict | None, *,
                     is_bodyweight: bool) -> str:
    """What actually happened vs the prior appearance of the same exercise."""
    if actual is None or (actual.get("volume_load") is None
                          and actual.get("reps_total") is None):
        return "not_performed"
    if prior is None:
        return "no_prior"

    metric = "reps_total" if is_bodyweight else "volume_load"
    dw = _delta(actual, prior, "weight_top")
    dr = _delta(actual, prior, "reps_at_top")
    rel = None
    if actual.get(metric) is not None and prior.get(metric):
        rel = (actual[metric] - prior[metric]) / prior[metric]

    if (dw is not None and dw > 0) or (dw == 0 and dr is not None and dr > 0) \
            or (rel is not None and rel > defs.VOLUME_DELTA_MEANINGFUL):
        return "progressed"
    if (dw is not None and dw < 0) or (rel is not None
                                       and rel < -defs.VOLUME_DELTA_MEANINGFUL):
        return "regressed"
    return "repeated"


def _delta(actual: dict, prior: dict, key: str) -> float | None:
    if actual.get(key) is None or prior.get(key) is None:
        return None
    return actual[key] - prior[key]


ALIGNMENT = {
    "push": {"progressed": "yes", "repeated": "partial", "regressed": "no"},
    "maintain": {"progressed": "partial", "repeated": "yes", "regressed": "no"},
    "pull_back": {"progressed": "no", "repeated": "yes", "regressed": "yes"},
}


def alignment(category: str, outcome: str) -> str:
    return ALIGNMENT.get(category, {}).get(outcome, "n/a")


def compare_recommendations(record: dict, df_actual: pd.DataFrame) -> list[dict]:
    """Auto-compare each recommendation with the day's actual performance."""
    day = record["upcoming_day"]
    actual_by_name = {e["exercise_name"]: e for e in
                      analytics.previous_workout_summary(df_actual, day)["exercises"]}

    comparisons = []
    for rec in record["briefing"]["recommendations"]:
        resolved = resolve_area(rec["area"], list(actual_by_name.values()))
        actual = prior = None
        is_bodyweight = False
        if resolved is not None:
            hist = analytics.exercise_history(df_actual, resolved, day)
            is_bodyweight = hist["is_bodyweight"]
            prior = hist["appearances"][-1] if hist["appearances"] else None
            actual = actual_by_name.get(resolved)
        outcome = classify_outcome(actual, prior, is_bodyweight=is_bodyweight)
        comparisons.append(dict(
            area=rec["area"], category=rec["category"], action=rec["action"],
            resolved_exercise=resolved,
            outcome=outcome,
            aligned=alignment(rec["category"], outcome),
            actual={k: actual.get(k) for k in METRIC_KEYS} if actual else None,
            prior={k: prior.get(k) for k in METRIC_KEYS} if prior else None))
    return comparisons


def record_feedback(path: Path, entry: dict) -> None:
    """Append one review session to the feedback JSONL log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _describe(comparison: dict) -> str:
    if comparison["outcome"] == "not_performed":
        return "not performed (no logged data for this exercise that day)"
    if comparison["outcome"] == "no_prior":
        a = comparison["actual"]
        return (f"first appearance: {a['weight_top']} x {a['reps_at_top']}, "
                f"volume {a['volume_load']}")
    a, p = comparison["actual"], comparison["prior"]
    return (f"actual {a['weight_top']} x {a['reps_at_top']} vol {a['volume_load']} "
            f"vs prior {p['weight_top']} x {p['reps_at_top']} vol {p['volume_load']} "
            f"— {comparison['outcome']}; aligned with "
            f"'{comparison['category']}': {comparison['aligned']}")


def _ask_choice(ask_user, prompt: str, mapping: dict[str, str]) -> str:
    while True:
        raw = ask_user(prompt).strip().casefold()
        if raw in mapping:
            return mapping[raw]


def _ask_rating(ask_user) -> int:
    while True:
        raw = ask_user("Usefulness of this briefing, 1-5 > ").strip()
        if raw.isdigit() and 1 <= int(raw) <= 5:
            return int(raw)


def run_review_cli(record_path: Path, df_actual: pd.DataFrame, *,
                   ask_user=input,
                   feedback_path: Path = defs.FEEDBACK_PATH) -> int:
    """Interactive review of one saved briefing; appends one feedback line."""
    record = json.loads(Path(record_path).read_text())
    comparisons = compare_recommendations(record, df_actual)

    print(f"Reviewing briefing for {record['upcoming_day']} "
          f"(model {record['model']}, {record['ts']})\n")
    if all(c["outcome"] == "not_performed" for c in comparisons):
        print("No logged performance found for this day yet - the comparison "
              "columns will be empty, but you can still record feedback.\n")

    followed_map = {"y": "yes", "yes": "yes", "n": "no", "no": "no",
                    "p": "partial", "partial": "partial"}
    for c in comparisons:
        print(f"[{c['category']}] {c['area']} — {c['action']}")
        print(f"  {_describe(c)}")
        c["followed"] = _ask_choice(ask_user, "  Followed? [y/n/p] > ", followed_map)
        print()

    usefulness = _ask_rating(ask_user)

    entry = dict(
        schema_version=SCHEMA_VERSION,
        ts=datetime.now().isoformat(timespec="seconds"),
        briefing_path=str(record_path),
        upcoming_day=record["upcoming_day"],
        model=record["model"],
        usefulness=usefulness,
        recommendations=comparisons)
    record_feedback(feedback_path, entry)
    print(f"\nFeedback recorded to {feedback_path}")
    return 0
