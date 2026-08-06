"""Canonical constants for the Essentials 4x logbook.

Mirrors the data dictionary in 00_essentials_4x_eda.ipynb.
"""

import re
from pathlib import Path

SHEET_NAME = "4x Program"
DEFAULT_DATA_PATH = Path("data/Essentials 4x Logbook.xlsx")

# Spreadsheet columns dropped on ingest (Jeff's prior-week reference columns).
DROPPED_COLS = [
    "prior_load",
    "prior_reps",
    "prior_load.1",
    "prior_row",
    "2xprior_load",
    "2xprior_reps",
    "2xprior_load.1",
    "prior_row.1",
    "jeff's_notes",
]

ID_COLS = ["date_day", "day", "exercise"]

# Synthetic session-date sequence: the spreadsheet has no dates, so sessions
# are assigned Mon/Tue/Thu/Fri dates starting from the program start.
PROGRAM_START = "2025-03-17"
WEEKMASK = "Mon Tue Thu Fri"

N_SESSIONS = 48  # 12 weeks x 4 sessions
N_ROWS = 288  # one row per programmed exercise-row

# Program slot, e.g. W1U1 = week 1, upper 1.
DAY_RE = re.compile(r"W(?P<week>\d+)(?P<split>[UL])(?P<slot>\d+)")

# 'A1: EZ Bar Curl' -> superset tag A1.
SUPERSET_RE = re.compile(r"^(?P<tag>A\d+):\s*")

# Optional drop marker (▼ or DS), weight, "R", reps, optional "xN" repeat count.
SET_RE = re.compile(
    r"(?P<drop>▼|DS)?\s*"
    r"(?P<weight>\d+(?:\.\d+)?)\s*R\s*(?P<reps>\d{1,2})"
    r"(?:\s*[xX]\s*(?P<repeat>\d+))?",
    re.IGNORECASE,
)
SEPARATORS = set(",\n\r\t ▼")

# A row with any of these statuses carries logged performance data.
LOGGED_PARSE_STATUSES = {"ok", "partial", "weight_only"}
PARSE_STATUSES = {"ok", "partial", "weight_only", "unparsed", "empty"}

# Analytics thresholds.
TREND_WINDOW = 3  # recent appearances considered for a trend
MIN_HISTORY = 2  # appearances needed before a trend is claimed
VOLUME_DELTA_MEANINGFUL = 0.05  # relative volume change worth mentioning
UNUSUAL_LOAD_JUMP = 0.15  # relative top-weight change that looks suspicious

# Persisted artifacts (data/ is gitignored).
BRIEFINGS_DIR = Path("data/interim/briefings")
FEEDBACK_PATH = Path("data/interim/feedback.jsonl")
READINESS_LOG = Path("data/interim/readiness_log.jsonl")

# Briefing shape limits, shared by the coach's postvalidate and the evals.
MAX_QUESTIONS = 3
MAX_OBSERVATIONS = 3

# Recommendation areas that legitimately refer to the whole session rather
# than one exercise.
WORKOUT_AREAS = frozenset({
    "workout", "session", "overall", "today's workout", "whole workout",
    "warm-up", "warmup", "warm-ups", "readiness", "recovery",
})
