import copy
import json
from pathlib import Path

import pytest

from agent_gainz import evals

FIXTURE = Path(__file__).parent / "fixtures" / "run_record_mini.json"


@pytest.fixture
def record():
    return json.loads(FIXTURE.read_text())


def failed(results, severity="error"):
    return [r for r in results if not r["passed"] and r["severity"] == severity]


def test_extract_numbers():
    assert evals.extract_numbers("volume 2520") == [(2520.0, False)]
    assert evals.extract_numbers("2520.0 vs 2,520") == [(2520.0, False), (2520.0, False)]
    assert evals.extract_numbers("up +20% overall") == [(20.0, True)]
    assert evals.extract_numbers("range 8-10") == [(8.0, False), (-10.0, False)]
    assert evals.extract_numbers("on 2025-03-17 (W12L2)") == []
    assert evals.extract_numbers("did 3 sets of 2 questions") == []  # small ints skipped
    assert evals.extract_numbers("2% of the time") == [(2.0, True)]  # percents never skipped


def test_is_grounded_tolerances():
    grounding = {2520.0, 9.0, 0.09, 80.0}
    assert evals.is_grounded(2520.0, False, grounding)
    assert evals.is_grounded(-2520.0, False, grounding)  # sign ignored
    assert evals.is_grounded(9.1, True, grounding)       # percent 1.0 tolerance
    assert evals.is_grounded(9.0, True, grounding)       # ratio 0.09 -> 9%
    assert not evals.is_grounded(2600.0, False, grounding)
    assert not evals.is_grounded(15.0, True, grounding)


def test_payload_number_set_includes_string_numbers():
    grounding = evals.payload_number_set(
        dict(a=1200.0, b=[dict(reps="8-10", detail="volume 360 -> 240 (+20%)")]))
    for expected in [1200.0, 8.0, 10.0, 360.0, 240.0, 20.0]:
        assert expected in grounding


def test_fixture_record_passes(record):
    results = evals.run_checks(record)
    assert failed(results) == []
    assert failed(results, "warning") == []
    assert len(results) == 8  # one clean entry per check


def mutate(record, **briefing_changes):
    r = copy.deepcopy(record)
    r["briefing"].update(briefing_changes)
    return r


def test_missing_keys_short_circuits(record):
    r = {k: v for k, v in record.items() if k != "tool_payloads"}
    results = evals.run_checks(r)
    assert len(results) == 1 and not results[0]["passed"]


def test_bad_schema_caught(record):
    r = copy.deepcopy(record)
    r["briefing"]["recommendations"][0]["category"] = "yolo"
    assert [f["check"] for f in failed(evals.run_checks(r))] == ["briefing_schema"]


def test_too_many_observations(record):
    r = mutate(record, key_observations=["a 5", "b 6", "c 7", "d 8"])
    assert any(f["check"] == "list_limits" for f in failed(evals.run_checks(r)))


def test_duplicate_questions(record):
    r = mutate(record, readiness_questions_asked=["How did you sleep?",
                                                  "how did you sleep? "])
    assert any(f["check"] == "questions_distinct" for f in failed(evals.run_checks(r)))


def test_blank_and_numberless_evidence(record):
    r = copy.deepcopy(record)
    r["briefing"]["recommendations"][0]["evidence"] = "   "
    r["briefing"]["recommendations"][1]["evidence"] = "it went well before"
    fails = [f for f in failed(evals.run_checks(r)) if f["check"] == "evidence_nonempty"]
    assert len(fails) == 2


def test_ungrounded_number_caught(record):
    r = copy.deepcopy(record)
    r["briefing"]["recommendations"][0]["evidence"] = "volume_load hit 9999 last time"
    fails = [f for f in failed(evals.run_checks(r)) if f["check"] == "numbers_grounded"]
    assert len(fails) == 1 and "9999" in fails[0]["detail"]


def test_grounded_variants_pass(record):
    # Same facts, different formatting: decimals and percent phrasing still ground.
    r = copy.deepcopy(record)
    r["briefing"]["recommendations"][0]["evidence"] = \
        "volume 1100.0 -> 1200.0, roughly a 9.1% jump"
    assert [f for f in failed(evals.run_checks(r))
            if f["check"] == "numbers_grounded"] == []


def test_invalid_area_caught(record):
    r = copy.deepcopy(record)
    r["briefing"]["recommendations"][0]["area"] = "Deadlift"
    fails = [f for f in failed(evals.run_checks(r)) if f["check"] == "areas_valid"]
    assert len(fails) == 1


def test_base_name_and_workout_areas_allowed(record):
    r = copy.deepcopy(record)
    r["briefing"]["recommendations"][1]["area"] = "Cable Row"  # base of "(Heavy)" variant
    r["briefing"]["recommendations"][2]["area"] = "Workout"
    assert [f for f in failed(evals.run_checks(r)) if f["check"] == "areas_valid"] == []


def test_medical_hard_error(record):
    r = mutate(record, tip="Just push through the pain on the last set.")
    fails = [f for f in failed(evals.run_checks(r)) if f["check"] == "medical_language"]
    assert len(fails) == 1


def test_medical_soft_warning_only(record):
    r = mutate(record, limitations=["Watch that quad strain from last month."])
    results = evals.run_checks(r)
    assert [f for f in failed(results) if f["check"] == "medical_language"] == []
    warns = [f for f in failed(results, "warning") if f["check"] == "medical_language"]
    assert len(warns) == 1


def test_pain_with_caution_allowed(record):
    # The fixture's limitations already carry the allowed phrasing.
    assert any("pain" in l for l in record["briefing"]["limitations"])
    results = evals.run_checks(record)
    assert [f for f in failed(results, "warning")
            if f["check"] == "medical_language"] == []


def test_pain_without_caution_warns(record):
    r = mutate(record, tip="Expect some knee pain on lunges.")
    warns = [f for f in failed(evals.run_checks(r), "warning")
             if f["check"] == "medical_language"]
    assert len(warns) == 1
