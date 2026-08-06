"""Run records: every briefing run persists what the coach saw and produced.

A record bundles the structured briefing, the exact analytics payloads the
tools served, and the run metadata — enough for the review flow and the
deterministic evals to work long after the run.
"""

import json
from datetime import datetime
from pathlib import Path

from agent_gainz import analytics, defs
from agent_gainz.coach.models import PreWorkoutBriefing

SCHEMA_VERSION = 1


def build_run_record(*, briefing: PreWorkoutBriefing, tool_payloads: dict,
                     model: str, upcoming_day: str, latest_day: str | None,
                     readiness: list[dict], warnings: list[str],
                     interactive: bool, simulated: bool,
                     ts: str | None = None) -> dict:
    """Assemble the v1 run-record dict. `ts` is overridable for fixtures."""
    return analytics._jsonify(dict(
        schema_version=SCHEMA_VERSION,
        ts=ts or datetime.now().isoformat(timespec="seconds"),
        model=model,
        upcoming_day=upcoming_day,
        latest_day=latest_day,
        simulated=simulated,
        interactive=interactive,
        readiness=readiness,
        briefing=briefing.model_dump(),
        tool_payloads=tool_payloads,
        postvalidate_warnings=warnings,
    ))


def save_run_record(record: dict, directory: Path = defs.BRIEFINGS_DIR) -> Path:
    """Write one record as pretty JSON; filename sorts chronologically."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = record["ts"].replace("-", "").replace(":", "")
    path = directory / f"{record['upcoming_day']}_{stamp}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return path


def load_run_record(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def latest_run_record(directory: Path = defs.BRIEFINGS_DIR,
                      day: str | None = None) -> Path | None:
    """Most recent saved record, optionally restricted to one program day."""
    if not directory.is_dir():
        return None
    pattern = f"{day}_*.json" if day else "*.json"
    paths = sorted(directory.glob(pattern))
    return paths[-1] if paths else None
