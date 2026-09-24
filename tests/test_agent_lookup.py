"""Unit tests: agent token lookup (ship_or_exit/agent.py).

Covers the live-run failure modes seen 2026-09-23: native symbols sent
as address filters (HTTP 422), empty address-filtered results, and
non-matching rows misattributed via the records[0] fallback.
"""
import unittest

from ship_or_exit import agent


ADDR = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"


def _row(symbol, net_7d):
    return {"token_symbol": symbol, "net_flow_1h_usd": 0.0,
            "net_flow_24h_usd": 0.0, "net_flow_7d_usd": net_7d,
            "net_flow_30d_usd": net_7d * 2, "trader_count": 5,
            "market_cap_usd": 1_000_000_000, "chain": "ethereum"}


class FakeNansen:
    """Scripted netflow: filtered vs unfiltered responses + call capture."""

    def __init__(self, filtered, unfiltered):
        self.filtered = filtered
        self.unfiltered = unfiltered
        self.calls = []

    def netflow(self, chains, token_address=None, per_page=100, **kwargs):
        self.calls.append({"chains": chains, "token_address": token_address,
                           "per_page": per_page,
                           "native_tokens": kwargs.get("native_tokens", False)})
        if token_address:
            return list(self.filtered)
        return list(self.unfiltered)


class FakeGitHub:
    def commits(self, repo, since, until):
        return []


def _run(symbol, token_address, nansen):
    watchlist = [{"symbol": symbol, "chain": "ethereum",
                  "token_address": token_address, "repo": None}]
    return agent.run(watchlist, nansen, FakeGitHub())


class TestAgentLookup(unittest.TestCase):
    def test_native_symbol_skips_address_filter(self):
        nansen = FakeNansen(filtered=[], unfiltered=[_row("ETH", 5_000_000)])
        verdicts = _run("ETH", None, nansen)
        self.assertEqual(len(nansen.calls), 1)
        self.assertIsNone(nansen.calls[0]["token_address"])
        self.assertTrue(nansen.calls[0]["native_tokens"])
        self.assertEqual(nansen.calls[0]["per_page"], 1000)
        self.assertEqual(verdicts[0]["flow"], "ACCUMULATING")
        self.assertTrue(any("5,000,000" in r for r in verdicts[0]["reasons"]))

    def test_contract_address_hit_makes_no_fallback_call(self):
        nansen = FakeNansen(filtered=[_row("UNI", 4_200_000)], unfiltered=[])
        verdicts = _run("UNI", ADDR, nansen)
        self.assertEqual(len(nansen.calls), 1)
        self.assertEqual(nansen.calls[0]["token_address"], ADDR)
        self.assertEqual(verdicts[0]["flow"], "ACCUMULATING")

    def test_address_miss_falls_back_to_symbol_match(self):
        nansen = FakeNansen(filtered=[],
                            unfiltered=[_row("OTHER", 9_999_999),
                                        _row("UNI", 4_200_000)])
        verdicts = _run("UNI", ADDR, nansen)
        self.assertEqual(len(nansen.calls), 2)
        self.assertIsNone(nansen.calls[1]["token_address"])
        self.assertEqual(nansen.calls[1]["per_page"], 1000)
        self.assertEqual(verdicts[0]["flow"], "ACCUMULATING")
        self.assertTrue(any("4,200,000" in r for r in verdicts[0]["reasons"]))
        self.assertFalse(any("9,999,999" in r for r in verdicts[0]["reasons"]))

    def test_fallback_includes_native_tokens_for_l2_natives(self):
        # ARB/OP are gas tokens on their chains: excluded server-side
        # unless the fallback sets native_tokens.
        nansen = FakeNansen(filtered=[],
                            unfiltered=[_row("ARB", -172_328)])
        watchlist = [{"symbol": "ARB", "chain": "arbitrum",
                      "token_address": "0x912Ce59144191C1204E64559fE8253a0e49E6548",
                      "repo": None}]
        verdicts = agent.run(watchlist, nansen, FakeGitHub())
        self.assertEqual(len(nansen.calls), 2)
        self.assertTrue(nansen.calls[1]["native_tokens"])
        self.assertEqual(verdicts[0]["flow"], "NEUTRAL")

    def test_no_match_anywhere_is_insufficient_not_misattributed(self):
        nansen = FakeNansen(filtered=[_row("OTHER", 9_999_999)],
                            unfiltered=[_row("OTHER", 9_999_999)])
        verdicts = _run("UNI", ADDR, nansen)
        self.assertEqual(verdicts[0]["verdict"], "INSUFFICIENT_DATA")
        self.assertTrue(any("No Nansen netflow record" in r
                            for r in verdicts[0]["reasons"]))
        self.assertFalse(any("9,999,999" in r for r in verdicts[0]["reasons"]))

    def test_lowercase_symbol_matches_uppercase_row(self):
        nansen = FakeNansen(filtered=[], unfiltered=[_row("uni", 4_200_000)])
        verdicts = _run("UNI", ADDR, nansen)
        self.assertEqual(verdicts[0]["flow"], "ACCUMULATING")


if __name__ == "__main__":
    unittest.main()
