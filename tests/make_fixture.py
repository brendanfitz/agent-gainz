"""Regenerate tests/fixtures/run_record_mini.json deterministically.

Run with: uv run python -m tests.make_fixture

The briefing is hand-written — no API call — with every number copied from
the mini_df analytics payloads, so the committed fixture always passes the
grounding checks and CI needs no OPENAI_API_KEY.
"""

import json
from pathlib import Path

from agent_gainz import analytics, records
from agent_gainz.coach.models import PreWorkoutBriefing

from tests.conftest import build_mini_df

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "run_record_mini.json"

BRIEFING = PreWorkoutBriefing.model_validate(dict(
    previous_workout_summary=(
        "W3U1: 6 exercises, 7 working sets, 78 total reps. Bench Press moved up "
        "again (volume 1100 -> 1200), while Curl fell off (volume 360 -> 240)."),
    todays_workout=(
        "W4U1 - upper session, 7 exercises including the Cable Row (Heavy) / "
        "Lat Pulldown superset and a new movement."),
    key_observations=[
        "Bench Press volume rose 1100 -> 1200 (+9%) with top weight 110 -> 120.",
        "Curl missed the prescribed range last time: 8 reps at top weight 30.",
        "Hanging Leg Raise is bodyweight; reps rose 12 -> 14.",
    ],
    readiness_questions_asked=[
        "How sore are your shoulders and chest after the last upper session?",
        "Did you sleep at least 7 hours last night?",
    ],
    recommendations=[
        dict(action="Target the top of the 8-10 range; continue the planned progression.",
             area="Bench Press", category="push",
             evidence="volume_load 1100 -> 1200 (+9%), top weight 110 -> 120",
             confidence="high", needs_confirmation=False),
        dict(action="Repeat the same working weight and stay in the middle of the range.",
             area="Cable Row (Heavy)", category="maintain",
             evidence="top weight 80 for 10 reps in each of the last 3 sessions",
             confidence="medium", needs_confirmation=False),
        dict(action="Start at the bottom of the 10-12 range and avoid adding load.",
             area="Curl", category="pull_back",
             evidence="reps at top weight fell 12 -> 8; volume_load 360 -> 240",
             confidence="medium", needs_confirmation=True),
        dict(action="Confirm the plan for this new exercise before loading up.",
             area="New Movement", category="ask_for_context",
             evidence="0 completed appearances in the log",
             confidence="low", needs_confirmation=True),
    ],
    limitations=[
        "Leg Extension history logs one set expanded to the prescribed count, "
        "so per-set detail is inferred.",
        "If any pain comes up during warm-ups, stop and consult a professional.",
    ],
    tip="Drive your feet into the floor on presses for a more stable base.",
))


def main() -> None:
    record = records.build_run_record(
        briefing=BRIEFING,
        tool_payloads=analytics.build_briefing_inputs(build_mini_df()),
        model="fixture", upcoming_day="W4U1", latest_day="W3U1",
        readiness=[dict(question=q, answer="all good")
                   for q in BRIEFING.readiness_questions_asked],
        warnings=[], interactive=True, simulated=True,
        ts="2026-01-01T00:00:00")
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"wrote {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
