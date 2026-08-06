"""Command-line interface: `agent-gainz report` and `agent-gainz brief`."""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent_gainz import analytics, defs, load, report, transforms


def _prepare_frame(args: argparse.Namespace):
    """Load the workbook and, unless told otherwise, simulate an upcoming day.

    The real workbook is fully logged, so by default the last program day
    (or `--upcoming-day`) has its loads blanked to stand in for today's
    session. `--no-simulate` uses the genuine workout states instead.
    """
    df = load.load_logbook(Path(args.data))
    if args.no_simulate:
        return df
    return transforms.simulate_upcoming(df, day=args.upcoming_day)


def cmd_report(args: argparse.Namespace) -> int:
    df = _prepare_frame(args)
    if transforms.next_upcoming(df) is None:
        print("Every session has logged data - nothing upcoming to report on. "
              "(Drop --no-simulate to simulate one.)")
        return 1
    print(report.render_report(analytics.build_briefing_inputs(df)))
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    from agent_gainz.coach.agent import run_briefing_cli
    df = _prepare_frame(args)
    if transforms.next_upcoming(df) is None:
        print("Every session has logged data - nothing upcoming to brief on. "
              "(Drop --no-simulate to simulate one.)")
        return 1
    return run_briefing_cli(df, model=args.model,
                            interactive=not args.no_questions,
                            simulated=not args.no_simulate)


def cmd_review(args: argparse.Namespace) -> int:
    from agent_gainz import records, review
    path = (Path(args.briefing) if args.briefing
            else records.latest_run_record(day=args.upcoming_day))
    if path is None:
        print("No saved briefing found - run `agent-gainz brief` first.")
        return 1
    df_actual = load.load_logbook(Path(args.data))  # real states, not simulated
    return review.run_review_cli(path, df_actual)


def cmd_eval(args: argparse.Namespace) -> int:
    from agent_gainz import evals, records
    path = Path(args.path) if args.path else records.latest_run_record()
    if path is None:
        print("No saved briefing found - run `agent-gainz brief` first.")
        return 1
    return evals.run_eval_cli(path)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="agent-gainz",
        description="Agentic pre-workout briefings from your training log.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data", default=str(defs.DEFAULT_DATA_PATH),
                        help="path to the Excel workout log")
    common.add_argument("--upcoming-day", default=None, metavar="DAY",
                        help="program day to treat as today's workout (default: last day)")
    common.add_argument("--no-simulate", action="store_true",
                        help="use real workout states instead of blanking a day")

    p_report = sub.add_parser("report", parents=[common],
                              help="deterministic pre-workout report (no LLM)")
    p_report.set_defaults(func=cmd_report)

    p_brief = sub.add_parser("brief", parents=[common],
                             help="agent-generated pre-workout briefing")
    p_brief.add_argument("--model", default=None,
                         help="OpenAI model (default: env AGENT_GAINZ_MODEL or gpt-5-mini)")
    p_brief.add_argument("--no-questions", action="store_true",
                         help="skip the interactive readiness questions")
    p_brief.set_defaults(func=cmd_brief)

    p_review = sub.add_parser(
        "review", help="post-workout: compare a briefing with what happened, record feedback")
    p_review.add_argument("--data", default=str(defs.DEFAULT_DATA_PATH),
                          help="path to the Excel workout log")
    p_review.add_argument("--briefing", default=None, metavar="PATH",
                          help="run-record file to review (default: most recent)")
    p_review.add_argument("--upcoming-day", default=None, metavar="DAY",
                          help="review the most recent record for this program day")
    p_review.set_defaults(func=cmd_review)

    p_eval = sub.add_parser("eval",
                            help="deterministic quality checks on a saved briefing")
    p_eval.add_argument("path", nargs="?", default=None,
                        help="run-record file to evaluate (default: most recent)")
    p_eval.set_defaults(func=cmd_eval)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
