"""Deterministic synthetic fixtures for demo mode.

No network, no keys. The six tokens cover every verdict the engine can
produce, so the demo recording shows the full behavior. Clearly labeled
as synthetic; live mode uses real Nansen + GitHub data.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

# Synthetic Nansen netflow records (7d/30d windows in USD).
NETFLOW = {
    "UNI": {"token_symbol": "UNI", "net_flow_1h_usd": 40_000,
            "net_flow_24h_usd": 900_000, "net_flow_7d_usd": 4_200_000,
            "net_flow_30d_usd": 3_000_000, "trader_count": 214,
            "market_cap_usd": 3_800_000_000},
    "LDO": {"token_symbol": "LDO", "net_flow_1h_usd": 60_000,
            "net_flow_24h_usd": 1_400_000, "net_flow_7d_usd": 5_800_000,
            "net_flow_30d_usd": 2_200_000, "trader_count": 188,
            "market_cap_usd": 900_000_000},
    "AAVE": {"token_symbol": "AAVE", "net_flow_1h_usd": -30_000,
             "net_flow_24h_usd": -700_000, "net_flow_7d_usd": -3_100_000,
             "net_flow_30d_usd": -1_500_000, "trader_count": 176,
             "market_cap_usd": 2_100_000_000},
    "LINK": {"token_symbol": "LINK", "net_flow_1h_usd": -20_000,
             "net_flow_24h_usd": -500_000, "net_flow_7d_usd": -2_400_000,
             "net_flow_30d_usd": -3_800_000, "trader_count": 240,
             "market_cap_usd": 6_500_000_000},
    "ARB": {"token_symbol": "ARB", "net_flow_1h_usd": 500,
            "net_flow_24h_usd": 10_000, "net_flow_7d_usd": 120_000,
            "net_flow_30d_usd": 400_000, "trader_count": 150,
            "market_cap_usd": 1_900_000_000},
    "MKR": {"token_symbol": "MKR", "net_flow_1h_usd": 4_000,
            "net_flow_24h_usd": 90_000, "net_flow_7d_usd": 800_000,
            "net_flow_30d_usd": 1_100_000, "trader_count": 64,
            "market_cap_usd": 1_200_000_000},
}

# Which synthetic commit profile each demo repo gets.
REPO_PROFILE = {
    "Uniswap/uniswap-v4-core": "shipping",     # UNI  -> HIGH_CONVICTION
    "lidofinance/lido-dao": "dormant",         # LDO  -> EXIT_LIQUIDITY_RISK
    "aave/aave-v3-core": "shipping",           # AAVE -> CONTRARIAN_WATCH
    "smartcontractkit/chainlink": "quiet",     # LINK -> AVOID
    "OffchainLabs/nitro": "steady",            # ARB  -> NEUTRAL
}

DEMO_WATCHLIST = [
    {"symbol": "UNI", "chain": "ethereum", "token_address": "UNI",
     "repo": "Uniswap/uniswap-v4-core"},
    {"symbol": "LDO", "chain": "ethereum", "token_address": "LDO",
     "repo": "lidofinance/lido-dao"},
    {"symbol": "AAVE", "chain": "ethereum", "token_address": "AAVE",
     "repo": "aave/aave-v3-core"},
    {"symbol": "LINK", "chain": "ethereum", "token_address": "LINK",
     "repo": "smartcontractkit/chainlink"},
    {"symbol": "ARB", "chain": "arbitrum", "token_address": "ARB",
     "repo": "OffchainLabs/nitro"},
    {"symbol": "MKR", "chain": "ethereum", "token_address": "MKR",
     "repo": None},  # unmapped on purpose: shows INSUFFICIENT_DATA
]

_AUTHORS = ["alice", "bob", "carol", "dave", "erin", "frank"]
_MESSAGES = ["feat: route optimizer", "fix: off-by-one in fee calc",
             "refactor: split pool manager", "test: fuzz swap paths",
             "perf: cache slot reads", "feat: hook registry",
             "fix: revert on zero liquidity", "chore: lint pass"]


def synthetic_commits(profile: str, seed: int = 7):
    """Generate human commits for a profile over the last 112 days.

    Each profile is a list of (first_week_back, last_week_back,
    commits_per_week, author_count) bands. Quiet/dormant profiles place
    all commits deep in the baseline window, which is exactly what the
    recency metric must detect.
    """
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    bands = {
        "shipping": [(0, 15, 11, 6)],
        "steady": [(0, 3, 4, 4), (4, 15, 6, 4)],
        "quiet": [(10, 15, 2, 2)],
        "dormant": [(13, 15, 3, 3)],
    }[profile]
    commits = []

    def add(days_ago, author):
        dt = now - timedelta(days=days_ago,
                             hours=rng.randint(0, 23),
                             minutes=rng.randint(0, 59))
        commits.append({
            "sha": f"{rng.getrandbits(160):040x}",
            "date": dt.isoformat(),
            "author_login": author,
            "author_name": author.title(),
            "message": rng.choice(_MESSAGES),
            "is_merge": False,
        })

    for week_start, week_end, per_wk, n_authors in bands:
        for week in range(week_start, week_end + 1):
            for _ in range(per_wk):
                add(week * 7 + rng.randint(0, 6),
                    rng.choice(_AUTHORS[:n_authors]))
    return sorted(commits, key=lambda c: c["date"])


class FixtureNansen:
    """Drop-in stand-in for NansenClient in demo mode."""

    def __init__(self):
        self.calls = 0

    def netflow(self, chains, token_address=None, **kwargs):
        self.calls += 1
        if token_address is None:
            # Unfiltered page query (native-token path): return the whole
            # page like the real API; the agent matches on symbol.
            return [dict(rec, chain=chains[0])
                    for rec in NETFLOW.values()]
        addrs = (token_address if isinstance(token_address, list)
                 else [token_address])
        out = []
        for addr in addrs:
            for sym, rec in NETFLOW.items():
                if addr and addr.upper() == sym:
                    out.append(dict(rec, chain=chains[0]))
        return out

    def call_count(self):
        return self.calls


class FixtureGitHub:
    """Drop-in stand-in for GitHubClient in demo mode."""

    def commits(self, repo, since, until):
        profile = REPO_PROFILE.get(repo, "steady")
        return synthetic_commits(profile, seed=abs(hash(repo)) % 10000)
