"""Unit tests: Nansen call-ledger counting (ship_or_exit/nansen.py)."""
import json
import os
import tempfile
import unittest

from ship_or_exit.nansen import NansenClient


def _row(ok=True, credits_used=5, note=None):
    return {"ts": "2026-09-23T00:00:00+00:00", "endpoint": "/api/v1/smart-money/netflow",
            "ok": ok, "credits_used": credits_used, "credits_remaining": 999,
            "ms": 12.5, "request_hash": "abc123", "note": note}


class TestCallLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, "calls.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def _client(self):
        return NansenClient(api_key="test-key", log_path=self.log)

    def _write(self, rows, raw_lines=()):
        with open(self.log, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
            for line in raw_lines:
                fh.write(line + "\n")

    def test_missing_log_counts_zero(self):
        client = self._client()
        self.assertEqual(client.call_count(), 0)
        self.assertEqual(client.credits_spent(), 0)

    def test_counts_only_successful_calls(self):
        self._write([_row(True), _row(True), _row(False)])
        client = self._client()
        self.assertEqual(client.call_count(), 2)

    def test_malformed_lines_ignored(self):
        self._write([_row(True)], raw_lines=["{not json", "", "42"])
        client = self._client()
        self.assertEqual(client.call_count(), 1)
        self.assertEqual(client.credits_spent(), 5)

    def test_credits_sum_successful_only(self):
        self._write([_row(True, 5), _row(True, 5), _row(False, 5),
                     _row(True, None)])
        client = self._client()
        self.assertEqual(client.credits_spent(), 10)

    def test_log_appends_valid_json(self):
        client = self._client()
        client._log("/api/v1/smart-money/netflow", True, 5, 999, 12.5, "abc", None)
        with open(self.log, encoding="utf-8") as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 1)
        row = json.loads(lines[0])
        self.assertEqual(row["endpoint"], "/api/v1/smart-money/netflow")
        self.assertTrue(row["ok"])
        self.assertEqual(row["credits_used"], 5)
        self.assertEqual(client.call_count(), 1)


if __name__ == "__main__":
    unittest.main()
