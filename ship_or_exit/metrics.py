"""Commit and flow metrics. Pure functions, no I/O.

Conventions:
- A repo is scored against its own history, never against other repos.
  A mature protocol ships at a different cadence than a new launch.
- Nansen netflow windows (1h/24h/7d/30d) are compared as rates to get
  flow acceleration without needing historical series.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def commit_metrics(commits: list, now: datetime | None = None,
                   recent_days: int = 28, base_days: int = 84) -> dict:
    """Velocity, contributor breadth, and recency for human commits."""
    now = now or datetime.now(timezone.utc)
    recent_cut = now - timedelta(days=recent_days)
    base_cut = now - timedelta(days=recent_days + base_days)

    recent = [c for c in commits if _parse_dt(c["date"]) >= recent_cut]
    base = [c for c in commits
            if base_cut <= _parse_dt(c["date"]) < recent_cut]

    vel_recent = len(recent) / (recent_days / 7.0)
    vel_base = len(base) / (base_days / 7.0)

    def authors(rows):
        return {(c.get("author_login") or c.get("author_name") or "?").lower()
                for c in rows}

    last = max((_parse_dt(c["date"]) for c in commits), default=None)
    return {
        "n_recent": len(recent),
        "n_base": len(base),
        "velocity_recent_wk": round(vel_recent, 2),
        "velocity_base_wk": round(vel_base, 2),
        "velocity_ratio": (round(vel_recent / vel_base, 3) if vel_base > 0
                           else (1.0 if vel_recent > 0 else 0.0)),
        "contributors_recent": len(authors(recent)),
        "contributors_base": len(authors(base)),
        "recency_days": (now - last).days if last else None,
    }


def flow_momentum(record: dict) -> dict:
    """Turn Nansen netflow windows into direction plus acceleration."""
    f1h = record.get("net_flow_1h_usd") or 0.0
    f24 = record.get("net_flow_24h_usd") or 0.0
    f7 = record.get("net_flow_7d_usd") or 0.0
    f30 = record.get("net_flow_30d_usd") or 0.0
    weekly_rate = f7 / 7.0
    monthly_rate = f30 / 30.0
    base = abs(monthly_rate) if abs(monthly_rate) > 1.0 else 1.0
    return {
        "net_1h": f1h,
        "net_24h": f24,
        "net_7d": f7,
        "net_30d": f30,
        "weekly_rate": weekly_rate,
        "monthly_rate": monthly_rate,
        "accel_ratio": round(weekly_rate / base, 3),
        "trader_count": record.get("trader_count") or 0,
        "market_cap": record.get("market_cap_usd"),
        "chain": record.get("chain"),
    }
