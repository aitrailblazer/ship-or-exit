"""Fusion scoring: smart-money flows crossed with commit reality.

Explainable by design. Every verdict carries its reasons, because a
trader should be able to verify the call in under a minute.

Verdicts:
  HIGH_CONVICTION      flows in, team shipping
  EXIT_LIQUIDITY_RISK  flows in, repo quiet (the money/code divergence)
  CONTRARIAN_WATCH     flows out, team shipping (divergence, other side)
  AVOID                flows out, repo quiet
  NEUTRAL              no meaningful signal on either side
  INSUFFICIENT_DATA    missing commit data or flow data
"""
from __future__ import annotations

MIN_FLOW_USD = 250_000
ACCEL_THRESHOLD = 1.5


def classify_flow(m: dict, min_flow_usd: float = MIN_FLOW_USD):
    f7 = m["net_7d"]
    accel = m["accel_ratio"]
    reasons: list = []
    if f7 >= min_flow_usd and accel >= ACCEL_THRESHOLD:
        label = "ACCUMULATING"
        reasons.append(
            f"7d net inflow ${f7:,.0f}, accelerating at {accel}x the 30d pace")
    elif f7 >= min_flow_usd:
        label = "ACCUMULATING"
        reasons.append(f"7d net inflow ${f7:,.0f} at a steady pace")
    elif f7 <= -min_flow_usd:
        label = "DISTRIBUTING"
        reasons.append(f"7d net outflow ${abs(f7):,.0f}")
    else:
        label = "NEUTRAL"
        reasons.append(f"7d net flow ${f7:,.0f} is noise-level")
    if m.get("trader_count"):
        reasons.append(f"{m['trader_count']} smart-money traders active in 30d")
    return label, reasons


def classify_shipping(m: dict):
    ratio = m["velocity_ratio"]
    rec = m["recency_days"]
    contribs = m["contributors_recent"]
    reasons = [
        f"{m['velocity_recent_wk']} commits/wk recent vs "
        f"{m['velocity_base_wk']} commits/wk baseline",
        f"{contribs} contributors in the last 28d",
    ]
    if rec is None:
        return "UNKNOWN", reasons + ["no commits found in window"]
    reasons.append(f"last human commit {rec}d ago")
    if ratio >= 0.8 and rec <= 14:
        return "SHIPPING", reasons
    if ratio >= 0.4 and rec <= 45:
        return "STEADY", reasons
    if rec > 90 and ratio < 0.2:
        return "DORMANT", reasons
    if ratio < 0.4 and rec > 45:
        return "QUIET", reasons
    return "STEADY", reasons


def fuse(symbol: str, flow_label: str, ship_label: str,
         flow_reasons: list, ship_reasons: list) -> dict:
    score, verdict, thesis = 50, "NEUTRAL", []
    if flow_label == "ACCUMULATING" and ship_label in ("SHIPPING", "STEADY"):
        verdict, score = "HIGH_CONVICTION", 88
        thesis = ["Smart money is accumulating into a team that is actively shipping."]
    elif flow_label == "ACCUMULATING" and ship_label in ("QUIET", "DORMANT"):
        verdict, score = "EXIT_LIQUIDITY_RISK", 22
        thesis = ["Smart money is accumulating but development has gone quiet. "
                  "Treat inflows as potential exit liquidity, not validation."]
    elif flow_label == "DISTRIBUTING" and ship_label in ("SHIPPING", "STEADY"):
        verdict, score = "CONTRARIAN_WATCH", 60
        thesis = ["Money is leaving while the team keeps shipping. "
                  "Divergence worth watching, not chasing."]
    elif flow_label == "DISTRIBUTING" and ship_label in ("QUIET", "DORMANT"):
        verdict, score = "AVOID", 15
        thesis = ["Outflows plus a quiet repo. No thesis here."]
    elif ship_label == "UNKNOWN":
        verdict, score = "INSUFFICIENT_DATA", 50
        thesis = ["Not enough signal on one or both sides to call it."]
    elif flow_label == "NEUTRAL":
        verdict, score = "NEUTRAL", 50
        thesis = ["No meaningful smart-money flow signal; "
                  "holding for stronger evidence on either side."]
    return {
        "symbol": symbol,
        "verdict": verdict,
        "score": score,
        "flow": flow_label,
        "shipping": ship_label,
        "reasons": thesis + flow_reasons + ship_reasons,
    }
