"""Agent tools: thin wrappers over the deterministic analytics.

The agent never touches raw dataframe rows — every number it can cite comes
out of `agent_gainz.analytics` through these tools.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from agents import RunContextWrapper, function_tool

from agent_gainz import analytics


@dataclass
class CoachContext:
    df_parsed: pd.DataFrame
    upcoming_day: str
    latest_day: str | None
    readiness_log_path: Path


def previous_workout_summary(ctx: CoachContext) -> dict:
    if ctx.latest_day is None:
        return {"error": "no completed workout on record"}
    return analytics.previous_workout_summary(ctx.df_parsed, ctx.latest_day)


def upcoming_workout_preview(ctx: CoachContext) -> dict:
    return analytics.upcoming_workout_preview(ctx.df_parsed, ctx.upcoming_day)


def exercise_history(ctx: CoachContext, exercise_name: str) -> dict:
    try:
        return analytics.exercise_history(ctx.df_parsed, exercise_name, ctx.upcoming_day)
    except ValueError as e:
        return {"error": str(e)}


def progression_signals(ctx: CoachContext) -> list[dict]:
    return analytics.progression_signals(ctx.df_parsed, ctx.upcoming_day)


def data_quality_signals(ctx: CoachContext) -> list[dict]:
    return analytics.data_quality_signals(ctx.df_parsed, ctx.upcoming_day)


@function_tool
def get_previous_workout_summary(wrapper: RunContextWrapper[CoachContext]) -> str:
    """Summary of the latest completed workout: per-exercise metrics, counts, notes, and notable changes vs each exercise's prior appearance."""
    return json.dumps(previous_workout_summary(wrapper.context))


@function_tool
def get_upcoming_workout_preview(wrapper: RunContextWrapper[CoachContext]) -> str:
    """Today's prescribed workout: exercises, sets, rep ranges, RPE, rest, supersets, substitutes, and notes. Prescription only — no performance data."""
    return json.dumps(upcoming_workout_preview(wrapper.context))


@function_tool
def get_exercise_history(wrapper: RunContextWrapper[CoachContext], exercise_name: str) -> str:
    """Recent completed appearances of one exercise (use the exact exercise_name from the preview): per-appearance metrics, deltas, and an improving/stable/declining/new trend."""
    return json.dumps(exercise_history(wrapper.context, exercise_name))


@function_tool
def get_progression_signals(wrapper: RunContextWrapper[CoachContext]) -> str:
    """Per-exercise progression signals for today's prescription (weight/rep/volume changes, missed rep ranges, declines, new exercises, unusual load changes)."""
    return json.dumps(progression_signals(wrapper.context))


@function_tool
def get_data_quality_signals(wrapper: RunContextWrapper[CoachContext]) -> str:
    """Data caveats to weigh before trusting the numbers: inferred sets, bodyweight exercises, parse problems, naming inconsistencies, and notes needing clarification."""
    return json.dumps(data_quality_signals(wrapper.context))


COACH_TOOLS = [get_previous_workout_summary, get_upcoming_workout_preview,
               get_exercise_history, get_progression_signals, get_data_quality_signals]
