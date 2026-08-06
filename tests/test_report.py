from agent_gainz import analytics, report, transforms


def test_render_report_sections(mini_df):
    text = report.render_report(analytics.build_briefing_inputs(mini_df))
    for header in ["# Pre-Workout Report — W4U1", "## Previous Workout",
                   "## Today's Workout", "## Exercise Comparisons",
                   "## Progression Signals", "## Data Quality"]:
        assert header in text


def test_report_mentions_every_prescribed_exercise(mini_df):
    text = report.render_report(analytics.build_briefing_inputs(mini_df))
    for name in mini_df.query("day == 'W4U1'").exercise_name:
        assert name in text


def test_report_with_no_prior_workout(mini_df):
    first_only = transforms.simulate_upcoming(
        mini_df.query("day == 'W1U1'").reset_index(drop=True), day="W1U1")
    text = report.render_report(analytics.build_briefing_inputs(first_only))
    assert "No completed workout on record." in text
