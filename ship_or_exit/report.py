"""Report rendering: terminal for the demo recording, markdown for sharing."""
from __future__ import annotations

from datetime import datetime, timezone

MARK = {
    "HIGH_CONVICTION": ">>",
    "EXIT_LIQUIDITY_RISK": "!!",
    "CONTRARIAN_WATCH": "?>",
    "AVOID": "xx",
    "NEUTRAL": "--",
    "INSUFFICIENT_DATA": "..",
    "ERROR": "EE",
}


def render_terminal(verdicts: list) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("SHIP-OR-EXIT  |  smart money x commit reality")
    lines.append("=" * 72)
    for v in verdicts:
        mark = MARK.get(v["verdict"], "??")
        lines.append("")
        lines.append(f"[{mark}] {v['symbol']:<8} {v['verdict']:<20} score {v['score']:>3}/100")
        lines.append(f"      flow: {v.get('flow', '-'):<14} shipping: {v.get('shipping', '-')}")
        for reason in v.get("reasons", [])[:4]:
            lines.append(f"      - {reason}")
    lines.append("")
    lines.append("=" * 72)
    lines.append(f"{len(verdicts)} tokens scored | "
                 f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 72)
    return "\n".join(lines)


def render_markdown(verdicts: list, title: str = "Ship-or-Exit report") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# {title}", "", f"Generated {ts}. Nansen Smart Money netflows "
             "crossed with protocol GitHub commit activity.", "",
             "| Token | Verdict | Score | Flow | Shipping |",
             "|-------|---------|-------|------|----------|"]
    for v in verdicts:
        lines.append(f"| {v['symbol']} | {v['verdict']} | {v['score']} "
                     f"| {v.get('flow', '-')} | {v.get('shipping', '-')} |")
    lines.append("")
    for v in verdicts:
        lines.append(f"## {v['symbol']} : {v['verdict']} ({v['score']}/100)")
        lines.append("")
        for reason in v.get("reasons", []):
            lines.append(f"- {reason}")
        lines.append("")
    return "\n".join(lines)
