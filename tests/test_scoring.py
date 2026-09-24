"""Unit tests: fusion scoring thresholds (ship_or_exit/scoring.py)."""
import unittest

from ship_or_exit import scoring


def _flow(net_7d, accel=1.0, traders=0):
    return {"net_7d": net_7d, "accel_ratio": accel, "trader_count": traders}


def _ship(ratio, rec, recent_wk=5.0, base_wk=5.0, contribs=3):
    return {"velocity_ratio": ratio, "recency_days": rec,
            "velocity_recent_wk": recent_wk, "velocity_base_wk": base_wk,
            "contributors_recent": contribs}


class TestClassifyFlow(unittest.TestCase):
    def test_inflow_accelerating_at_threshold(self):
        label, reasons = scoring.classify_flow(
            _flow(scoring.MIN_FLOW_USD, scoring.ACCEL_THRESHOLD))
        self.assertEqual(label, "ACCUMULATING")
        self.assertTrue(any("accelerating" in r for r in reasons))

    def test_inflow_steady_below_accel_threshold(self):
        label, reasons = scoring.classify_flow(
            _flow(scoring.MIN_FLOW_USD, scoring.ACCEL_THRESHOLD - 0.01))
        self.assertEqual(label, "ACCUMULATING")
        self.assertTrue(any("steady" in r for r in reasons))

    def test_below_min_flow_is_noise(self):
        label, _ = scoring.classify_flow(_flow(scoring.MIN_FLOW_USD - 1, 5.0))
        self.assertEqual(label, "NEUTRAL")

    def test_outflow_at_threshold_distributes(self):
        label, _ = scoring.classify_flow(_flow(-scoring.MIN_FLOW_USD, 0.1))
        self.assertEqual(label, "DISTRIBUTING")

    def test_small_outflow_is_noise(self):
        label, _ = scoring.classify_flow(_flow(-scoring.MIN_FLOW_USD + 1, 0.1))
        self.assertEqual(label, "NEUTRAL")

    def test_trader_count_mentioned_when_present(self):
        _, reasons = scoring.classify_flow(_flow(10_000_000, 2.0, traders=42))
        self.assertTrue(any("42" in r for r in reasons))

    def test_no_trader_line_when_zero(self):
        _, reasons = scoring.classify_flow(_flow(10_000_000, 2.0, traders=0))
        self.assertFalse(any("traders active" in r for r in reasons))


class TestClassifyShipping(unittest.TestCase):
    def test_shipping_at_boundary(self):
        self.assertEqual(scoring.classify_shipping(_ship(0.8, 14))[0], "SHIPPING")

    def test_just_below_shipping_ratio_is_steady(self):
        self.assertEqual(scoring.classify_shipping(_ship(0.79, 14))[0], "STEADY")

    def test_steady_at_boundary(self):
        self.assertEqual(scoring.classify_shipping(_ship(0.4, 45))[0], "STEADY")

    def test_stale_but_elevated_ratio_falls_through_to_steady(self):
        # ratio >= 0.4 but recency past the STEADY window: no QUIET/DORMANT
        # branch matches, so the default holds it at STEADY, not SHIPPING.
        self.assertEqual(scoring.classify_shipping(_ship(0.9, 46))[0], "STEADY")

    def test_quiet(self):
        self.assertEqual(scoring.classify_shipping(_ship(0.1, 60))[0], "QUIET")

    def test_dormant(self):
        self.assertEqual(scoring.classify_shipping(_ship(0.1, 91))[0], "DORMANT")

    def test_old_but_not_dormant_ratio_is_quiet(self):
        self.assertEqual(scoring.classify_shipping(_ship(0.3, 200))[0], "QUIET")

    def test_no_commits_is_unknown(self):
        label, reasons = scoring.classify_shipping(_ship(0.0, None))
        self.assertEqual(label, "UNKNOWN")
        self.assertTrue(any("no commits" in r for r in reasons))


class TestFuse(unittest.TestCase):
    def _fuse(self, flow, ship):
        return scoring.fuse("TST", flow, ship, ["flow-r"], ["ship-r"])

    def test_high_conviction(self):
        for ship in ("SHIPPING", "STEADY"):
            v = self._fuse("ACCUMULATING", ship)
            self.assertEqual(v["verdict"], "HIGH_CONVICTION")
            self.assertEqual(v["score"], 88)

    def test_exit_liquidity_risk(self):
        for ship in ("QUIET", "DORMANT"):
            v = self._fuse("ACCUMULATING", ship)
            self.assertEqual(v["verdict"], "EXIT_LIQUIDITY_RISK")
            self.assertEqual(v["score"], 22)

    def test_contrarian_watch(self):
        for ship in ("SHIPPING", "STEADY"):
            v = self._fuse("DISTRIBUTING", ship)
            self.assertEqual(v["verdict"], "CONTRARIAN_WATCH")
            self.assertEqual(v["score"], 60)

    def test_avoid(self):
        for ship in ("QUIET", "DORMANT"):
            v = self._fuse("DISTRIBUTING", ship)
            self.assertEqual(v["verdict"], "AVOID")
            self.assertEqual(v["score"], 15)

    def test_insufficient_data_unknown_shipping(self):
        v = self._fuse("ACCUMULATING", "UNKNOWN")
        self.assertEqual((v["verdict"], v["score"]), ("INSUFFICIENT_DATA", 50))

    def test_neutral_flow_with_known_shipping_is_neutral(self):
        for ship in ("SHIPPING", "STEADY", "QUIET", "DORMANT"):
            v = self._fuse("NEUTRAL", ship)
            self.assertEqual((v["verdict"], v["score"]), ("NEUTRAL", 50))

    def test_neutral_fallback(self):
        v = self._fuse("NEUTRAL", "UNKNOWN")
        self.assertEqual(v["verdict"], "INSUFFICIENT_DATA")

    def test_reasons_carry_thesis_and_inputs(self):
        v = self._fuse("ACCUMULATING", "SHIPPING")
        self.assertIn("flow-r", v["reasons"])
        self.assertIn("ship-r", v["reasons"])
        self.assertEqual(v["symbol"], "TST")


if __name__ == "__main__":
    unittest.main()
