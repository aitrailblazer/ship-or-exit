"""Nansen API client with a persistent, auditable call counter.

Every request is appended to a JSONL call log carrying the endpoint,
credits used, credits remaining, latency, and a request hash. The log is
the entrant-side evidence for the buildathon's 1,000-call entry gate
(Nansen also counts on their side).

Only low-cost endpoints are used: smart-money netflow (5 credits).
Premium labels and agent endpoints are deliberately avoided.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone

import requests

BASE_URL = "https://api.nansen.ai"
DEFAULT_LOG = os.environ.get("SHIP_OR_EXIT_CALL_LOG", ".call_log.jsonl")


class NansenError(Exception):
    """API-level failure with an actionable message."""


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class NansenClient:
    def __init__(self, api_key: str | None = None, log_path: str = DEFAULT_LOG,
                 timeout: int = 60):
        key = api_key or os.environ.get("NANSEN_API_KEY")
        if not key:
            raise NansenError(
                "NANSEN_API_KEY is not set. Create a free key at "
                "https://app.nansen.ai/api and export NANSEN_API_KEY=<key>. "
                "Or run the zero-key demo: python demo.py"
            )
        self.api_key = key
        self.log_path = log_path
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"apikey": key, "Content-Type": "application/json"})

    # ---------------- low level ----------------
    def _request(self, method: str, path: str, payload: dict | None):
        url = BASE_URL + path
        body = json.dumps(payload or {}).encode()
        digest = hashlib.sha256(body).hexdigest()[:12]
        attempts = 0
        while True:
            attempts += 1
            start = time.time()
            try:
                resp = self.session.request(method, url, data=body, timeout=self.timeout)
            except requests.RequestException as exc:
                self._log(path, False, None, None, 0.0, digest, f"network: {exc}")
                raise NansenError(f"Network error calling {path}: {exc}") from exc
            ms = (time.time() - start) * 1000.0
            used = _int_or_none(resp.headers.get("X-Nansen-Credits-Used"))
            remaining = _int_or_none(resp.headers.get("X-Nansen-Credits-Remaining"))
            if resp.status_code == 429 and attempts <= 3:
                wait = _retry_after(resp)
                self._log(path, False, used, remaining, ms, digest, "429, retrying")
                time.sleep(wait)
                continue
            ok = 200 <= resp.status_code < 300
            try:
                data = resp.json()
            except ValueError:
                data = {"raw": resp.text[:300]}
            self._log(path, ok, used, remaining, ms, digest,
                      None if ok else f"HTTP {resp.status_code}")
            if resp.status_code == 401:
                raise NansenError(
                    "Invalid or missing Nansen API key (401). "
                    "Manage keys at https://app.nansen.ai/api")
            if resp.status_code == 403:
                msg = data.get("message", data) if isinstance(data, dict) else data
                raise NansenError(f"Forbidden (403): {msg}")
            if not ok:
                msg = data.get("message", data) if isinstance(data, dict) else data
                raise NansenError(f"Nansen API error HTTP {resp.status_code} on {path}: {msg}")
            return data, {"credits_used": used, "credits_remaining": remaining, "ms": ms}

    def _log(self, endpoint, ok, used, remaining, ms, digest, note):
        line = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "ok": ok,
            "credits_used": used,
            "credits_remaining": remaining,
            "ms": round(ms, 1),
            "request_hash": digest,
            "note": note,
        }
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")

    def call_count(self) -> int:
        """Number of successful calls recorded in the log."""
        if not os.path.exists(self.log_path):
            return 0
        n = 0
        with open(self.log_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and row.get("ok"):
                        n += 1
                except ValueError:
                    pass
        return n

    def credits_spent(self) -> int:
        total = 0
        if not os.path.exists(self.log_path):
            return 0
        with open(self.log_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                    if (isinstance(row, dict) and row.get("ok")
                            and row.get("credits_used")):
                        total += row["credits_used"]
                except ValueError:
                    pass
        return total

    # ---------------- Smart Money ----------------
    def netflow(self, chains, token_address=None, labels=None, per_page=100,
                order_field="net_flow_7d_usd", direction="DESC", page=1,
                native_tokens=False, stablecoins=False):
        """POST /api/v1/smart-money/netflow (5 credits).

        Returns the raw list of netflow records. Native gas tokens
        (ETH, SOL, ...) and stablecoins are excluded server-side unless
        explicitly requested via native_tokens/stablecoins.
        """
        payload: dict = {
            "chains": chains,
            "pagination": {"page": page, "per_page": per_page},
            "order_by": [{"field": order_field, "direction": direction}],
        }
        filters: dict = {}
        if token_address:
            addrs = token_address if isinstance(token_address, list) else [token_address]
            # API matches token_address case-sensitively against lowercase
            # contract addresses; normalize to avoid silent empty results.
            filters["token_address"] = [a.lower() for a in addrs]
        if labels:
            filters["include_smart_money_labels"] = labels
        if native_tokens:
            filters["include_native_tokens"] = True
        if stablecoins:
            filters["include_stablecoins"] = True
        if filters:
            payload["filters"] = filters
        data, _ = self._request("POST", "/api/v1/smart-money/netflow", payload)
        return data.get("data", [])

    def holdings(self, chains, labels=None, per_page=100, page=1):
        """POST /api/v1/smart-money/holdings (5 credits)."""
        payload: dict = {
            "chains": chains,
            "pagination": {"page": page, "per_page": per_page},
        }
        if labels:
            payload["filters"] = {"include_smart_money_labels": labels}
        data, _ = self._request("POST", "/api/v1/smart-money/holdings", payload)
        return data.get("data", [])


def _retry_after(resp) -> int:
    try:
        return max(1, int(resp.headers.get("Retry-After", "2")))
    except ValueError:
        return 2
