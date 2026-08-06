"""Offline tests: tool payloads, output models, agent construction. No network."""

import json

import pytest

from agent_gainz import transforms
from agent_gainz.coach import agent as coach_agent
from agent_gainz.coach import tools
from agent_gainz.coach.models import PreWorkoutBriefing


@pytest.fixture
def context(mini_df, tmp_path):
    return tools.CoachContext(
        df_parsed=mini_df,
        upcoming_day="W4U1",
        latest_day=transforms.latest_completed(mini_df, before="W4U1"),
        readiness_log_path=tmp_path / "readiness_log.jsonl")


def test_tool_impls_return_json_payloads(context):
    payloads = [
        tools.previous_workout_summary(context),
        tools.upcoming_workout_preview(context),
        tools.exercise_history(context, "Bench Press"),
        tools.progression_signals(context),
        tools.data_quality_signals(context),
    ]
    for p in payloads:
        json.dumps(p)
    assert tools.exercise_history(context, "Bench Press")["trend"] == "improving"
    assert "error" in tools.exercise_history(context, "Nonexistent") or \
        tools.exercise_history(context, "Nonexistent")["trend"] == "new"


def test_no_latest_day_is_reported_not_raised(context):
    context.latest_day = None
    assert "error" in tools.previous_workout_summary(context)


def test_coach_tools_are_registered():
    names = {t.name for t in tools.COACH_TOOLS}
    assert names == {"get_previous_workout_summary", "get_upcoming_workout_preview",
                     "get_exercise_history", "get_progression_signals",
                     "get_data_quality_signals"}


def test_build_coach_offline():
    coach = coach_agent.build_coach(model="gpt-5-mini")
    assert coach.model == "gpt-5-mini"
    assert len(coach.tools) == 5
    questions = coach.clone(output_type=coach_agent.ReadinessQuestions)
    assert questions.output_type is coach_agent.ReadinessQuestions
    assert questions.instructions == coach.instructions


def test_briefing_model_validates():
    briefing = PreWorkoutBriefing.model_validate(dict(
        previous_workout_summary="did stuff",
        todays_workout="lower body",
        key_observations=["a", "b", "c", "d"],
        readiness_questions_asked=[],
        recommendations=[dict(action="repeat 100 for 8-10", area="Bench Press",
                              category="maintain", evidence="volume 1000 -> 1050",
                              confidence="medium", needs_confirmation=False)],
        limitations=["short history"],
        tip=None))
    validated, warnings = coach_agent.postvalidate(briefing)
    assert len(validated.key_observations) == 3
    assert any("truncated" in w for w in warnings)


def test_postvalidate_flags_missing_evidence():
    briefing = PreWorkoutBriefing.model_validate(dict(
        previous_workout_summary="s", todays_workout="t",
        key_observations=[], readiness_questions_asked=[],
        recommendations=[dict(action="a", area="Bench Press", category="push",
                              evidence="  ", confidence="low",
                              needs_confirmation=True)],
        limitations=[], tip="drink water"))
    _, warnings = coach_agent.postvalidate(briefing)
    assert any("no evidence" in w for w in warnings)


def test_record_readiness_appends_valid_jsonl(tmp_path):
    path = tmp_path / "log.jsonl"
    coach_agent.record_readiness(path, "W4U1", "Sleep?", "8 hours")
    coach_agent.record_readiness(path, "W4U1", "Soreness?", "none")
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[0]["question"] == "Sleep?" and lines[0]["upcoming_day"] == "W4U1"
    assert set(lines[1]) == {"ts", "upcoming_day", "question", "answer"}
