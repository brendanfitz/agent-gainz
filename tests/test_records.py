import json

from agent_gainz import analytics, records
from agent_gainz.coach.models import PreWorkoutBriefing

BRIEFING = PreWorkoutBriefing(
    previous_workout_summary="s", todays_workout="t",
    key_observations=["Bench volume 1100 -> 1200"], readiness_questions_asked=[],
    recommendations=[], limitations=[], tip=None)


def make_record(mini_df, ts="2026-01-01T00:00:00", day="W4U1"):
    return records.build_run_record(
        briefing=BRIEFING,
        tool_payloads=analytics.build_briefing_inputs(mini_df),
        model="gpt-5-mini", upcoming_day=day, latest_day="W3U1",
        readiness=[dict(question="Sleep?", answer="fine")],
        warnings=[], interactive=True, simulated=True, ts=ts)


def test_record_schema_and_serializable(mini_df):
    record = make_record(mini_df)
    assert set(record) == {"schema_version", "ts", "model", "upcoming_day",
                           "latest_day", "simulated", "interactive", "readiness",
                           "briefing", "tool_payloads", "postvalidate_warnings"}
    assert record["schema_version"] == 1
    assert record["ts"] == "2026-01-01T00:00:00"  # override honored
    json.dumps(record)


def test_save_load_round_trip(mini_df, tmp_path):
    record = make_record(mini_df)
    path = records.save_run_record(record, tmp_path)
    assert path.name == "W4U1_20260101T000000.json"
    assert records.load_run_record(path) == record


def test_latest_run_record_ordering_and_filter(mini_df, tmp_path):
    early = records.save_run_record(make_record(mini_df, ts="2026-01-01T00:00:00"), tmp_path)
    late = records.save_run_record(make_record(mini_df, ts="2026-02-01T09:30:00"), tmp_path)
    other = records.save_run_record(
        make_record(mini_df, ts="2026-03-01T00:00:00", day="W9U9"), tmp_path)

    assert records.latest_run_record(tmp_path) == other
    assert records.latest_run_record(tmp_path, day="W4U1") == late
    assert records.latest_run_record(tmp_path, day="W1U1") is None
    assert early.exists()


def test_latest_run_record_missing_dir(tmp_path):
    assert records.latest_run_record(tmp_path / "nope") is None
