"""Representative workout scenarios over the real workbook.

These same days are the manual-eval scenarios for
`agent-gainz brief --upcoming-day X` followed by `agent-gainz eval`.
"""

import json

import pytest

from agent_gainz import analytics, evals, transforms


@pytest.mark.parametrize("day", ["W1U1", "W6L1", "W12L2"])
def test_scenario_briefing_inputs(logbook, day):
    sim = transforms.simulate_upcoming(logbook, day=day)
    inputs = analytics.build_briefing_inputs(sim)
    assert inputs["upcoming_day"] == day
    json.dumps(inputs)
    assert evals.payload_number_set(inputs)


def test_program_start_has_no_history(logbook):
    sim = transforms.simulate_upcoming(logbook, day="W1U1")
    inputs = analytics.build_briefing_inputs(sim)
    assert inputs["previous_workout"] is None
    assert inputs["latest_day"] is None
    assert all(h["trend"] == "new" for h in inputs["exercise_histories"].values())


def test_mid_program_day_has_history(logbook):
    sim = transforms.simulate_upcoming(logbook, day="W6L1")
    inputs = analytics.build_briefing_inputs(sim)
    assert inputs["latest_day"] is not None
    trends = {h["trend"] for h in inputs["exercise_histories"].values()}
    assert trends <= {"improving", "stable", "declining", "new", "insufficient_history"}
    assert trends & {"improving", "stable", "declining"}
