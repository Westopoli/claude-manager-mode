#!/usr/bin/env python3
"""Pins the dedupe rule: streamed assistant chunks repeat `usage`; only the
last record per message.id counts. Also pins role classification priority."""
import json
import tempfile
import unittest
from pathlib import Path

import mine_transcripts as mt


def w(path, records):
    with open(path, "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


class MineTranscriptsTests(unittest.TestCase):
    def test_dedupe_keeps_only_last_chunk_per_message_id(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "agent-x.jsonl"
            w(p, [
                {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "hi"}},
                {"type": "assistant", "timestamp": "2026-01-01T00:00:01Z",
                 "message": {"id": "m1", "model": "claude-sonnet-5",
                            "usage": {"input_tokens": 100, "cache_read_input_tokens": 0, "output_tokens": 1},
                            "content": [{"type": "text", "text": "a"}]}},
                {"type": "assistant", "timestamp": "2026-01-01T00:00:02Z",
                 "message": {"id": "m1", "model": "claude-sonnet-5",
                            "usage": {"input_tokens": 100, "cache_read_input_tokens": 0, "output_tokens": 40},
                            "content": [{"type": "text", "text": "a full text"}]}},
                {"type": "assistant", "timestamp": "2026-01-01T00:00:03Z",
                 "message": {"id": "m2", "model": "claude-sonnet-5",
                            "usage": {"input_tokens": 5, "cache_read_input_tokens": 200, "output_tokens": 10},
                            "content": [{"type": "tool_use", "name": "Bash", "input": {}}]}},
            ])
            m = mt.mine_agent(p)
            # naive sum over all 3 assistant lines would double-count m1
            self.assertEqual(m["turns"], 2)
            self.assertEqual(m["output_tokens"], 40 + 10)  # last m1 chunk (40) + m2 (10), not 1+40+10
            self.assertEqual(m["input_tokens"], 100 + 5)
            self.assertEqual(m["cache_read_tokens"], 200)
            self.assertEqual(m["tool_calls"], 1)

    def test_role_classifier_priority(self):
        self.assertEqual(mt.classify("leaf-03: implement cache.py"), "leaf")
        self.assertEqual(mt.classify("Shard-test-writer: write RED tests for wave-1"), "shard-test-writer")
        self.assertEqual(mt.classify("Test-quality audit: shard default"), "test-auditor")
        self.assertEqual(mt.classify("Fix 4 audit findings in parent-owned test files"), "test-fixer")
        self.assertEqual(mt.classify("Adjudicate shard-A findings"), "adjudicator")
        self.assertEqual(mt.classify("Explore the codebase for X"), "non-cascade")
        self.assertEqual(mt.classify("something with no signal at all"), "unclassified")

    def test_prompt_fallback_when_description_silent(self):
        role = mt.classify("", "You are leaf-02 of a TDD cascade. Read your brief at .swarm/x/briefs/leaf-02.md")
        self.assertEqual(role, "leaf")

    def test_cascade_slug_extraction(self):
        self.assertEqual(mt.cascade_slug("work at .swarm/cash_print_sheets_queue/worktrees/leaf-01/"), "cash_print_sheets_queue")
        self.assertEqual(mt.cascade_slug("no swarm path here"), "")

    def test_cost_usd_uses_rates_and_prefix_match(self):
        rates = {"claude-sonnet-5": {"input": 2, "cache_write_5m": 2.5, "cache_write_1h": 4, "cache_read": 0.2, "output": 10}}
        row = {"model": "claude-sonnet-5-20260101", "input_tokens": 1_000_000, "cache_write_5m": 0,
               "cache_write_1h": 0, "cache_read_tokens": 1_000_000, "output_tokens": 1_000_000}
        self.assertEqual(mt.cost_usd(row, rates), "12.2000")  # 2 + 0.2 + 10


if __name__ == "__main__":
    unittest.main()
