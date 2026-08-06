import json
from pathlib import Path

import pytest

from agent_gainz import review

FIXTURE = Path(__file__).parent / "fixtures" / "run_record_mini.json"


@pytest.fixture
def record():
    return json.loads(FIXTURE.read_text())


def test_classify_outcome_truth_table():
    prior = dict(weight_top=100.0, reps_at_top=10, reps_total=10, volume_load=1000.0)
    cases = [
        (dict(prior, weight_top=105.0, volume_load=1050.0), "progressed"),  # weight up
        (dict(prior, reps_at_top=12, reps_total=12, volume_load=1200.0), "progressed"),  # reps up, same weight
        (dict(prior), "repeated"),
        (dict(prior, reps_at_top=9, reps_total=9, volume_load=960.0), "repeated"),  # within dead-band
        (dict(prior, weight_top=95.0, volume_load=950.0), "regressed"),  # weight down
        (dict(prior, reps_at_top=8, reps_total=8, volume_load=800.0), "regressed"),  # volume -20%
    ]
    for actual, expected in cases:
        assert review.classify_outcome(actual, prior, is_bodyweight=False) == expected

    assert review.classify_outcome(None, prior, is_bodyweight=False) == "not_performed"
    assert review.classify_outcome(
        dict(weight_top=None, reps_at_top=None, reps_total=None, volume_load=None),
        prior, is_bodyweight=False) == "not_performed"
    assert review.classify_outcome(prior, None, is_bodyweight=False) == "no_prior"

    bw_prior = dict(weight_top=0.0, reps_at_top=12, reps_total=12, volume_load=0.0)
    bw_more = dict(bw_prior, reps_at_top=14, reps_total=14)
    assert review.classify_outcome(bw_more, bw_prior, is_bodyweight=True) == "progressed"
    assert review.classify_outcome(bw_prior, bw_prior, is_bodyweight=True) == "repeated"


def test_alignment_table():
    assert review.alignment("push", "progressed") == "yes"
    assert review.alignment("push", "repeated") == "partial"
    assert review.alignment("push", "regressed") == "no"
    assert review.alignment("maintain", "repeated") == "yes"
    assert review.alignment("maintain", "progressed") == "partial"
    assert review.alignment("pull_back", "regressed") == "yes"
    assert review.alignment("pull_back", "progressed") == "no"
    assert review.alignment("ask_for_context", "progressed") == "n/a"
    assert review.alignment("push", "not_performed") == "n/a"
    assert review.alignment("push", "no_prior") == "n/a"


def test_resolve_area():
    exercises = [dict(exercise_name="Cable Row (Heavy)"),
                 dict(exercise_name="Bench Press")]
    assert review.resolve_area("Cable Row (Heavy)", exercises) == "Cable Row (Heavy)"
    assert review.resolve_area("cable row", exercises) == "Cable Row (Heavy)"
    assert review.resolve_area("Bench Press.", exercises) == "Bench Press"
    assert review.resolve_area("Workout", exercises) is None
    assert review.resolve_area("Deadlift", exercises) is None
    # Model-appended descriptions resolve to the real exercise.
    assert review.resolve_area("Bench Press (chest)", exercises) == "Bench Press"
    assert review.resolve_area("Cable Row (lats/mid-back)", exercises) == "Cable Row (Heavy)"


def test_compare_recommendations_all_outcomes(record, mini_df_completed):
    record["briefing"]["recommendations"].append(dict(
        action="a", area="Leg Extension", category="maintain",
        evidence="e 1", confidence="low", needs_confirmation=False))
    by_area = {c["area"]: c for c in
               review.compare_recommendations(record, mini_df_completed)}

    assert by_area["Bench Press"]["outcome"] == "progressed"  # 120 -> 125
    assert by_area["Bench Press"]["aligned"] == "yes"  # push
    assert by_area["Cable Row (Heavy)"]["outcome"] == "repeated"
    assert by_area["Cable Row (Heavy)"]["aligned"] == "yes"  # maintain
    assert by_area["Curl"]["outcome"] == "not_performed"
    assert by_area["Curl"]["aligned"] == "n/a"
    assert by_area["New Movement"]["outcome"] == "no_prior"
    assert by_area["Leg Extension"]["outcome"] == "regressed"  # 90 -> 80
    assert by_area["Leg Extension"]["aligned"] == "no"  # maintain + regressed

    bench = by_area["Bench Press"]
    assert bench["actual"]["weight_top"] == 125.0
    assert bench["prior"]["weight_top"] == 120.0


def test_run_review_cli_writes_feedback(record, mini_df_completed, tmp_path):
    answers = iter(["y", "p", "n", "y", "9", "4"])  # 9 is invalid -> reprompt
    feedback = tmp_path / "feedback.jsonl"
    rc = review.run_review_cli(FIXTURE, mini_df_completed,
                               ask_user=lambda _: next(answers),
                               feedback_path=feedback)
    assert rc == 0
    lines = feedback.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["schema_version"] == 1
    assert entry["upcoming_day"] == "W4U1"
    assert entry["usefulness"] == 4
    assert [r["followed"] for r in entry["recommendations"]] == \
        ["yes", "partial", "no", "yes"]
    assert entry["recommendations"][0]["outcome"] == "progressed"
