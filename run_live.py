"""Live mode: full Ship-or-Exit run on real Nansen + GitHub data.

Requires NANSEN_API_KEY (create one at https://app.nansen.ai/api).
GITHUB_TOKEN is optional but recommended (60 req/hr unauthenticated).

    export NANSEN_API_KEY=<key>
    python run_live.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ship_or_exit import agent, report
from ship_or_exit.github import GitHubClient
from ship_or_exit.nansen import NansenClient, NansenError


def main() -> int:
    with open(os.path.join("config", "watchlist.json"), encoding="utf-8") as fh:
        watchlist = json.load(fh)
    try:
        nansen = NansenClient()
    except NansenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    github = GitHubClient()
    calls_before = nansen.call_count()
    credits_before = nansen.credits_spent()
    verdicts = agent.run(watchlist, nansen, github)
    print(report.render_terminal(verdicts))
    with open("report.md", "w", encoding="utf-8") as fh:
        fh.write(report.render_markdown(verdicts))
    print("Wrote report.md")
    print(f"Nansen calls this run: {nansen.call_count() - calls_before} "
          f"({nansen.credits_spent() - credits_before} credits spent, "
          f"see .call_log.jsonl)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
