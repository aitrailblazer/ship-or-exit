"""Orchestrates one full Ship-or-Exit run over a watchlist.

For each token: pull the Nansen smart-money netflow record, pull the
mapped protocol repo's commits, score both sides, fuse into a verdict.
Failures are per-token and never kill the run.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import metrics, scoring
from .github import is_human

COMMIT_WINDOW_DAYS = 112  # 28d recent + 84d baseline


def _is_contract_address(token: str) -> bool:
    """True when token looks like an EVM contract address (0x + 40 hex)."""
    if not isinstance(token, str) or not token.startswith(("0x", "0X")):
        return False
    hexpart = token[2:]
    return len(hexpart) == 40 and all(c in "0123456789abcdefABCDEF"
                                     for c in hexpart)


def _match_symbol(records: list, symbol: str) -> dict | None:
    """Return the record for symbol, never another token's row."""
    want = (symbol or "").upper()
    return next((r for r in records or []
                 if (r.get("token_symbol") or "").upper() == want), None)


def _fetch_record(nansen, chain: str, symbol: str, token: str) -> dict | None:
    """Fetch one token's netflow record.

    Native gas tokens (ETH, SOL, ...) have no contract address and the
    API rejects symbols in the address filter (HTTP 422); they also need
    include_native_tokens, which defaults to false server-side. Contract
    tokens query by address first (client lowercases the address); when
    that returns nothing usable, one full-page fallback query retries
    via symbol match before giving up.
    """
    if _is_contract_address(token):
        record = _match_symbol(nansen.netflow([chain], token_address=token),
                               symbol)
        if record is not None:
            return record
        # Fallback scans the full page: include native gas tokens so L2
        # natives like ARB/OP (excluded server-side by default) match.
        return _match_symbol(
            nansen.netflow([chain], per_page=1000, native_tokens=True),
            symbol)
    return _match_symbol(
        nansen.netflow([chain], per_page=1000, native_tokens=True), symbol)


def run(watchlist: list, nansen, github) -> list:
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=COMMIT_WINDOW_DAYS)).isoformat()
    until = now.isoformat()
    verdicts: list = []

    for entry in watchlist:
        symbol = entry["symbol"]
        chain = entry.get("chain", "ethereum")
        token = entry.get("token_address") or symbol
        try:
            record = _fetch_record(nansen, chain, symbol, token)
        except Exception as exc:  # noqa: BLE001 - per-token isolation
            verdicts.append({"symbol": symbol, "verdict": "ERROR", "score": 0,
                             "flow": "-", "shipping": "-",
                             "reasons": [f"Nansen error: {exc}"]})
            continue
        if record is None:
            verdicts.append(scoring.fuse(symbol, "NEUTRAL", "UNKNOWN",
                                         ["No Nansen netflow record returned."],
                                         ["Skipped commit pull without flow data."]))
            continue

        flow = metrics.flow_momentum(record)
        flow_label, flow_reasons = scoring.classify_flow(flow)

        repo = entry.get("repo")
        if not repo:
            ship_label, ship_reasons = "UNKNOWN", ["No repo mapped for this token."]
        else:
            try:
                commits = [c for c in github.commits(repo, since, until)
                           if is_human(c)]
            except Exception as exc:  # noqa: BLE001 - per-token isolation
                ship_label, ship_reasons = "UNKNOWN", [f"GitHub error: {exc}"]
            else:
                ship_label, ship_reasons = scoring.classify_shipping(
                    metrics.commit_metrics(commits, now))

        verdicts.append(scoring.fuse(symbol, flow_label, ship_label,
                                     flow_reasons, ship_reasons))

    verdicts.sort(key=lambda v: v["score"], reverse=True)
    return verdicts
