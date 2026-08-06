"""The coach agent: readiness questions, then a structured pre-workout briefing."""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from agents import Agent, Runner, trace

from agent_gainz import analytics, defs, records, transforms
from agent_gainz.coach.models import PreWorkoutBriefing, ReadinessQuestions
from agent_gainz.coach.tools import COACH_TOOLS, CoachContext

DEFAULT_MODEL = "gpt-5-mini"
MAX_QUESTIONS = defs.MAX_QUESTIONS
MAX_OBSERVATIONS = defs.MAX_OBSERVATIONS

INSTRUCTIONS = """\
You are an evidence-driven personal trainer preparing the user for the workout
immediately ahead. You work only from the tool outputs — never invent, estimate,
or recompute numbers. Every numeric claim must come from a tool result, and every
recommendation's evidence field must cite specific tool-provided values.

Workflow: always call the tools first — the upcoming workout preview, the
previous workout summary, the progression signals, the data-quality signals,
and exercise history for any exercise you discuss in detail.

Recommendation rules (stay inside the written program):
- Categories: push (target the top of the rep range, small load increase,
  continue planned progression), maintain (repeat last working weight, middle
  of the range, follow the program as written), pull_back (start at the bottom
  of the range, avoid load increases, use a listed substitute), or
  ask_for_context (clarify soreness, recovery, an odd data point, or a note).
- Set each recommendation's area to the exact exercise_name from the preview
  (or a session-level word like "workout" or "recovery"). Do not append
  muscle groups or descriptions to the area.
- Never rewrite the program, add unplanned volume, or recommend large load
  increases. Only suggest substitutes that the prescription already lists.
- Never diagnose injuries or recommend training through acute pain — if pain
  comes up, advise caution and suggest speaking to a professional.
- Prescribed RPE is a target, not what the user actually experienced.
- Mind the data-quality signals: treat inferred sets, bodyweight rows, and
  imperfect parses as weaker evidence, and say so in limitations.

Readiness questions: ask at most 3, and only questions whose answers could
materially change a recommendation (sleep, soreness near today's target
muscles, joint discomfort, planned substitutions, unclear log entries). If
nothing would change your advice, ask fewer or none.

Briefing limits: at most 3 key observations and 3 readiness questions.
Keep the tone practical and concise; confidence reflects the strength and
cleanliness of the evidence.
"""


def resolve_model(model: str | None = None) -> str:
    return model or os.environ.get("AGENT_GAINZ_MODEL") or DEFAULT_MODEL


def build_coach(model: str | None = None) -> Agent[CoachContext]:
    """The single coach agent; stages clone it with different output types."""
    return Agent[CoachContext](
        name="agent-gainz coach",
        instructions=INSTRUCTIONS,
        tools=COACH_TOOLS,
        model=resolve_model(model),
    )


def record_readiness(path: Path, upcoming_day: str, question: str, answer: str) -> None:
    """Append one readiness Q&A to the JSONL log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(ts=datetime.now().isoformat(timespec="seconds"),
                 upcoming_day=upcoming_day, question=question, answer=answer)
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def postvalidate(briefing: PreWorkoutBriefing) -> tuple[PreWorkoutBriefing, list[str]]:
    """Enforce limits the strict output schema cannot express."""
    warnings = []
    if len(briefing.key_observations) > MAX_OBSERVATIONS:
        warnings.append(f"truncated key_observations to {MAX_OBSERVATIONS}")
        briefing.key_observations = briefing.key_observations[:MAX_OBSERVATIONS]
    if len(briefing.readiness_questions_asked) > MAX_QUESTIONS:
        warnings.append(f"truncated readiness_questions_asked to {MAX_QUESTIONS}")
        briefing.readiness_questions_asked = briefing.readiness_questions_asked[:MAX_QUESTIONS]
    for rec in briefing.recommendations:
        if not rec.evidence.strip():
            warnings.append(f"recommendation for {rec.area!r} has no evidence")
    return briefing, warnings


def run_briefing(context: CoachContext, *, model: str | None = None,
                 interactive: bool = True,
                 ask_user=input) -> tuple[PreWorkoutBriefing, list[str], list[dict]]:
    """Run the two-stage coach flow; returns (briefing, warnings, readiness Q&A).

    Stage 1 asks for readiness questions, answers are collected via `ask_user`
    and logged; stage 2 continues the same conversation into the final
    structured briefing. With `interactive=False`, stage 1 is skipped.
    """
    coach = build_coach(model)
    prompt = (f"Prepare the pre-workout briefing for {context.upcoming_day}. "
              "Review the tools first.")

    with trace("agent-gainz pre-workout briefing"):
        answers: list[tuple[str, str]] = []
        input_items: list | str = prompt

        if interactive:
            question_agent = coach.clone(output_type=ReadinessQuestions)
            stage1 = Runner.run_sync(question_agent, prompt, context=context)
            questions = stage1.final_output.questions[:MAX_QUESTIONS]
            for q in questions:
                answer = ask_user(f"\n{q}\n> ").strip()
                record_readiness(context.readiness_log_path, context.upcoming_day,
                                 q, answer)
                answers.append((q, answer))
            answer_text = ("Readiness answers:\n" +
                           "\n".join(f"- Q: {q}\n  A: {a}" for q, a in answers)
                           if answers else
                           "No readiness questions were needed.")
            input_items = stage1.to_input_list() + [
                {"role": "user", "content": answer_text +
                 "\nNow produce the final pre-workout briefing."}]

        briefing_agent = coach.clone(output_type=PreWorkoutBriefing)
        stage2 = Runner.run_sync(briefing_agent, input_items, context=context)

    briefing, warnings = postvalidate(stage2.final_output)
    if interactive and not briefing.readiness_questions_asked:
        briefing.readiness_questions_asked = [q for q, _ in answers]
    return briefing, warnings, [dict(question=q, answer=a) for q, a in answers]


def render_briefing(briefing: PreWorkoutBriefing) -> str:
    """Terminal-friendly markdown rendering of the structured briefing."""
    lines = ["# Pre-Workout Briefing", "",
             "## Previous Workout", "", briefing.previous_workout_summary, "",
             "## Today's Workout", "", briefing.todays_workout, ""]
    if briefing.key_observations:
        lines += ["## Key Observations", ""]
        lines += [f"- {o}" for o in briefing.key_observations] + [""]
    if briefing.readiness_questions_asked:
        lines += ["## Readiness Questions Asked", ""]
        lines += [f"- {q}" for q in briefing.readiness_questions_asked] + [""]
    lines += ["## Recommendations", ""]
    for r in briefing.recommendations:
        confirm = " *(confirm before applying)*" if r.needs_confirmation else ""
        lines += [f"- **[{r.category}] {r.area}** — {r.action}{confirm}",
                  f"  - Evidence: {r.evidence}",
                  f"  - Confidence: {r.confidence}"]
    lines.append("")
    if briefing.limitations:
        lines += ["## Limitations", ""]
        lines += [f"- {l}" for l in briefing.limitations] + [""]
    if briefing.tip:
        lines += ["## Tip", "", briefing.tip, ""]
    return "\n".join(lines)


def run_briefing_cli(df_parsed: pd.DataFrame, *, model: str | None = None,
                     interactive: bool = True, simulated: bool = True) -> int:
    """CLI entry: run the coach, print the briefing, persist the run record."""
    upcoming = transforms.next_upcoming(df_parsed)
    latest = transforms.latest_completed(df_parsed, before=upcoming)
    context = CoachContext(df_parsed=df_parsed, upcoming_day=upcoming,
                           latest_day=latest, readiness_log_path=defs.READINESS_LOG)
    briefing, warnings, readiness = run_briefing(context, model=model,
                                                 interactive=interactive)
    print(render_briefing(briefing))
    for w in warnings:
        print(f"[warning] {w}")

    record = records.build_run_record(
        briefing=briefing,
        tool_payloads=analytics.build_briefing_inputs(df_parsed),
        model=resolve_model(model), upcoming_day=upcoming, latest_day=latest,
        readiness=readiness, warnings=warnings,
        interactive=interactive, simulated=simulated)
    path = records.save_run_record(record)
    print(f"\nRun record saved to {path}")
    return 0
