"""Unit tests: Nansen response parsing (ship_or_exit/nansen.py + metrics.py)."""
import unittest

from ship_or_exit import metrics
from ship_or_exit.nansen import NansenClient


class TestFlowMomentum(unittest.TestCase):
    def test_acceleration_math(self):
        # 7d net 700k -> weekly rate 100k; 30d net 600k -> monthly rate 20k.
        m = metrics.flow_momentum({"net_flow_1h_usd": 1_000,
                                   "net_flow_24h_usd": 50_000,
                                   "net_flow_7d_usd": 700_000,
                                   "net_flow_30d_usd": 600_000,
                                   "trader_count": 10,
                                   "market_cap_usd": 1_000_000_000,
                                   "chain": "ethereum"})
        self.assertEqual(m["net_1h"], 1_000)
        self.assertEqual(m["net_24h"], 50_000)
        self.assertEqual(m["net_7d"], 700_000)
        self.assertEqual(m["net_30d"], 600_000)
        self.assertAlmostEqual(m["weekly_rate"], 100_000.0)
        self.assertAlmostEqual(m["monthly_rate"], 20_000.0)
        self.assertAlmostEqual(m["accel_ratio"], 5.0)
        self.assertEqual(m["trader_count"], 10)
        self.assertEqual(m["market_cap"], 1_000_000_000)
        self.assertEqual(m["chain"], "ethereum")

    def test_missing_windows_default_to_zero(self):
        m = metrics.flow_momentum({})
        self.assertEqual((m["net_1h"], m["net_24h"], m["net_7d"], m["net_30d"]),
                         (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(m["trader_count"], 0)
        self.assertIsNone(m["market_cap"])
        self.assertIsNone(m["chain"])

    def test_none_windows_default_to_zero(self):
        m = metrics.flow_momentum({"net_flow_7d_usd": None,
                                   "net_flow_30d_usd": None})
        self.assertEqual(m["net_7d"], 0.0)
        self.assertEqual(m["accel_ratio"], 0.0)

    def test_tiny_monthly_base_does_not_explode(self):
        # monthly rate ~0 would divide by ~0; the floor keeps it bounded.
        m = metrics.flow_momentum({"net_flow_7d_usd": 7_000,
                                   "net_flow_30d_usd": 3.0})
        self.assertAlmostEqual(m["accel_ratio"], 1000.0)

    def test_negative_flows_keep_sign(self):
        m = metrics.flow_momentum({"net_flow_7d_usd": -2_100_000,
                                   "net_flow_30d_usd": -3_000_000})
        self.assertEqual(m["net_7d"], -2_100_000)
        self.assertLess(m["accel_ratio"], 0)


class TestNetflowParsing(unittest.TestCase):
    def _client_with(self, response_data):
        client = NansenClient(api_key="test-key", log_path="/dev/null")
        captured = {}

        def fake_request(method, path, payload):
            captured.update({"method": method, "path": path, "payload": payload})
            return {"data": response_data}, {"credits_used": 5,
                                             "credits_remaining": 1,
                                             "ms": 1.0}

        client._request = fake_request
        return client, captured

    def test_netflow_returns_data_list(self):
        rows = [{"token_symbol": "UNI", "net_flow_7d_usd": 100}]
        client, captured = self._client_with(rows)
        self.assertEqual(client.netflow(["ethereum"], token_address="0xabc"), rows)
        self.assertEqual(captured["path"], "/api/v1/smart-money/netflow")
        self.assertEqual(captured["payload"]["filters"]["token_address"], ["0xabc"])

    def test_netflow_missing_data_key_returns_empty(self):
        client, _ = self._client_with(None)
        client._request = lambda m, p, pl: ({}, None)
        self.assertEqual(client.netflow(["ethereum"]), [])

    def test_token_address_list_passes_through(self):
        client, captured = self._client_with([])
        client.netflow(["ethereum"], token_address=["0xa", "0xb"])
        self.assertEqual(captured["payload"]["filters"]["token_address"],
                         ["0xa", "0xb"])

    def test_labels_land_in_filters(self):
        client, captured = self._client_with([])
        client.netflow(["ethereum"], labels=["Fund"])
        self.assertEqual(captured["payload"]["filters"]["include_smart_money_labels"],
                         ["Fund"])

    def test_native_tokens_flag_lands_in_filters(self):
        client, captured = self._client_with([])
        client.netflow(["ethereum"], native_tokens=True)
        self.assertTrue(
            captured["payload"]["filters"]["include_native_tokens"])

    def test_native_and_stablecoin_flags_absent_by_default(self):
        client, captured = self._client_with([])
        client.netflow(["ethereum"], token_address="0xabc")
        self.assertNotIn("include_native_tokens",
                         captured["payload"]["filters"])
        self.assertNotIn("include_stablecoins",
                         captured["payload"]["filters"])

    def test_token_address_normalized_to_lowercase(self):
        client, captured = self._client_with([])
        client.netflow(["ethereum"],
                       token_address="0x1F9840A85D5AF5BF1D1762F925BDADDC4201F984")
        self.assertEqual(captured["payload"]["filters"]["token_address"],
                         ["0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"])


if __name__ == "__main__":
    unittest.main()


class TestTokenAddressFilter(unittest.TestCase):
    def _client_with_capture(self):
        client = NansenClient(api_key="test-key", log_path="/tmp/test-calls.jsonl")
        captured = {}
        def fake_request(method, path, payload):
            captured.update(payload)
            return {"data": []}, 200
        client._request = fake_request
        return client, captured

    def test_token_address_lowercased_in_filter(self):
        # Regression: the API matches token_address case-sensitively against
        # lowercase contract addresses; a checksummed address returned 0 rows.
        client, captured = self._client_with_capture()
        client.netflow(["ethereum"],
                       token_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984")
        self.assertEqual(captured["filters"]["token_address"],
                         ["0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"])

    def test_token_address_list_all_lowercased(self):
        client, captured = self._client_with_capture()
        client.netflow(["ethereum"],
                       token_address=["0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
                                      "0x5a98fcbea516cf06857215779fd812ca3bef1b32"])
        self.assertEqual(captured["filters"]["token_address"],
                         ["0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
                          "0x5a98fcbea516cf06857215779fd812ca3bef1b32"])

    def test_no_filter_when_no_token_address(self):
        client, captured = self._client_with_capture()
        client.netflow(["ethereum"])
        self.assertNotIn("filters", captured)
