"""Demo mode: full Ship-or-Exit run on synthetic fixtures.

Zero keys, zero network. This is the script to screen-record for the
buildathon demo post.

    python demo.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ship_or_exit import agent, fixtures, report


def main() -> int:
    print("SHIP-OR-EXIT demo mode: synthetic fixtures, no API keys, no network.")
    print()
    verdicts = agent.run(fixtures.DEMO_WATCHLIST,
                         fixtures.FixtureNansen(), fixtures.FixtureGitHub())
    print(report.render_terminal(verdicts))
    with open("demo_report.md", "w", encoding="utf-8") as fh:
        fh.write(report.render_markdown(
            verdicts, title="Ship-or-Exit demo report (synthetic fixtures)"))
    print("Wrote demo_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
