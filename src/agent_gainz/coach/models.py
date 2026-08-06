"""Structured output models for the coach agent (README section 13)."""

from typing import Literal

from pydantic import BaseModel


class Recommendation(BaseModel):
    action: str
    area: str
    category: Literal["push", "maintain", "pull_back", "ask_for_context"]
    evidence: str
    confidence: Literal["low", "medium", "high"]
    needs_confirmation: bool


class ReadinessQuestions(BaseModel):
    """Stage-1 output: targeted questions whose answers could change the advice."""

    questions: list[str]


class PreWorkoutBriefing(BaseModel):
    """Stage-2 output: the full pre-workout briefing."""

    previous_workout_summary: str
    todays_workout: str
    key_observations: list[str]
    readiness_questions_asked: list[str]
    recommendations: list[Recommendation]
    limitations: list[str]
    tip: str | None
