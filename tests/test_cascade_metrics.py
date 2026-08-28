#!/usr/bin/env python3
"""Tests for cascade_metrics.py — the Phase 7.2 cost/outcome recorder.

Synthetic ~/.claude/projects tree + synthetic .swarm/<slug>/ dir; every case
pins a rule the script's docstring states (dedupe by message.id, window from
git-ops.log, cross-project overlord detection by slug mention, global log
filtered by window, ledger written).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/swarm-shared/scripts/cascade_metrics.py"
sys.path.insert(0, str(SCRIPT.parent))
import cascade_metrics as cm  # noqa: E402

T0 = "2026-08-28T10:00:00Z"
T1 = "2026-08-28T10:10:00Z"
T2 = "2026-08-28T10:20:00Z"
T_BEFORE = "2026-08-28T09:00:00Z"
T_AFTER = "2026-08-28T11:00:00Z"


def rec(kind: str, ts: str, content, mid: str = "", model: str = "", usage: dict | None = None) -> str:
    msg: dict = {"role": kind, "content": content}
    if kind == "assistant":
        msg["id"] = mid
        msg["model"] = model
        msg["usage"] = usage or {"input_tokens": 100, "cache_creation_input_tokens": 50,
                                 "cache_read_input_tokens": 1000, "output_tokens": 20}
    return json.dumps({"type": kind, "timestamp": ts, "message": msg}) + "\n"


def task_block(tid: str, desc: str, prompt: str, model: str) -> list:
    return [{"type": "tool_use", "id": tid, "name": "Task",
             "input": {"description": desc, "prompt": prompt, "model": model, "subagent_type": "general-purpose"}}]


class Fixture:
    def __init__(self, tmp: Path, slug: str = "demo"):
        self.tmp = tmp
        self.slug = slug
        self.root = tmp / "proj"
        self.cdir = self.root / ".swarm" / slug
        (self.cdir / "briefs").mkdir(parents=True)
        (self.cdir / "audits" / "wave-1" / "default").mkdir(parents=True)
        for n in (1, 2):
            (self.cdir / "briefs" / f"leaf-0{n}.md").write_text("---\nleaf_id: leaf-0%d\n---\n" % n)
        (self.cdir / "briefs" / "leaf-01.ASSUMPTIONS.md").write_text("- x\n")
        (self.cdir / "git-ops.log").write_text(
            f"{T0} | {self.root} | git status --porcelain | exit 0\n"
            f"{T2} | {self.root} | git merge --no-ff x | exit 0\n")
        (self.cdir / "audits/wave-1/default/TEST-AUDIT.md").write_text("🔴 one\n🟡 two\n🟢 three\n")
        (self.cdir / "audits/wave-1/default/TEST-AUDIT-ROUND2.md").write_text("🟢 clear\n")
        (self.cdir / "audits/wave-1/leaf-01.GATES.md").write_text(
            "| gate | result |\n|---|---|\n| G1 | PASS |\n| G8 | ADVISORY |\n")
        (self.root / ".swarm" / "post-review-log.md").write_text(
            "| wave | shard | leaf_id | files | delta | timestamp | status | a | b |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
            f"| 1 | default | leaf-01 | f | +1 | {T1} | clean | s | m |\n"
            f"| 1 | default | leaf-02 | f | +1 | {T_BEFORE} | clean | s | m |\n"   # older cascade, same leaf id
        )
        self.projects = tmp / "projects"
        self.ledger = tmp / "ledger"

    def session(self, project_dir: str, sid: str, lines: str) -> Path:
        d = self.projects / project_dir
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{sid}.jsonl"
        p.write_text(lines)
        return p

    def subagent(self, project_dir: str, sid: str, aid: str, desc: str, tool_use_id: str, lines: str) -> None:
        d = self.projects / project_dir / sid / "subagents"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"agent-{aid}.jsonl").write_text(lines)
        (d / f"agent-{aid}.meta.json").write_text(json.dumps(
            {"agentType": "general-purpose", "description": desc, "toolUseId": tool_use_id, "spawnDepth": 1}))

    def run(self, *extra: str) -> tuple[int, str, str, dict]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--cascade", self.slug, "--root", str(self.root),
             "--projects-root", str(self.projects), "--ledger-dir", str(self.ledger),
             "--rates", str(SCRIPT.parent / "rates.json"), *extra],
            capture_output=True, text=True)
        mpath = self.cdir / "METRICS.json"
        data = json.loads(mpath.read_text()) if mpath.exists() else {}
        return proc.returncode, proc.stdout, proc.stderr, data


class CascadeMetricsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _overlord_lines(self, slug_mention: bool = True) -> str:
        text = f"running .swarm/{self.fx.slug}/ now" if slug_mention else "unrelated"
        return (
            rec("assistant", T_BEFORE, [{"type": "text", "text": "old work"}], "m0", "claude-opus-5")
            + rec("user", T0, text)
            # streamed chunks: same message.id twice — must count once
            + rec("assistant", T1, task_block("tu1", "leaf-01: build add", "You are leaf-01 of a TDD cascade", "claude-sonnet-4-6"),
                  "m1", "claude-opus-5", {"input_tokens": 1, "cache_read_input_tokens": 1, "output_tokens": 1})
            + rec("assistant", T1, task_block("tu1", "leaf-01: build add", "You are leaf-01 of a TDD cascade", "claude-sonnet-4-6"),
                  "m1", "claude-opus-5", {"input_tokens": 100, "cache_creation_input_tokens": 50,
                                          "cache_read_input_tokens": 1000, "output_tokens": 20})
            + rec("assistant", T2, [{"type": "text", "text": "done"}], "m2", "claude-opus-5")
            + rec("assistant", T_AFTER, [{"type": "text", "text": "later"}], "m3", "claude-opus-5")
        )

    def _leaf_lines(self) -> str:
        return (rec("user", T1, "You are leaf-01 of a TDD cascade")
                + rec("assistant", T1, [{"type": "text", "text": "green"}], "a1", "claude-sonnet-4-6"))

    def test_dedupes_and_windows_overlord(self):
        proj = cm.project_dir_name(self.fx.root)
        self.fx.session(proj, "sess1", self._overlord_lines())
        self.fx.subagent(proj, "sess1", "aaa", "leaf-01: build add", "tu1", self._leaf_lines())
        code, out, err, m = self.fx.run()
        self.assertEqual(code, 0, err)
        self.assertEqual(m["overlord"]["session"], "sess1")
        # m0 (before window) and m3 (after) excluded; m1 counted once with its LAST chunk; m2 counted
        self.assertEqual(m["overlord"]["usage"]["turns"], 2)
        self.assertEqual(m["overlord"]["usage"]["input_tokens"], 200)
        self.assertEqual(m["overlord"]["usage"]["cache_read_tokens"], 2000)
        self.assertEqual(m["overlord"]["model"], "claude-opus-5")
        self.assertIsNotNone(m["overlord"]["cost_usd"])
        self.assertEqual(m["window"]["wall_clock_min"], 22.0)  # 20 min + 2 min preflight pad

    def test_subagent_joined_and_classified(self):
        proj = cm.project_dir_name(self.fx.root)
        self.fx.session(proj, "sess1", self._overlord_lines())
        self.fx.subagent(proj, "sess1", "aaa", "leaf-01: build add", "tu1", self._leaf_lines())
        _, _, _, m = self.fx.run()
        self.assertEqual(len(m["agents"]), 1)
        a = m["agents"][0]
        self.assertEqual(a["role"], "leaf")
        self.assertEqual(a["model"], "claude-sonnet-4-6")
        self.assertEqual(a["requested_model"], "claude-sonnet-4-6")
        self.assertEqual(m["requested_models"]["leaf"], {"claude-sonnet-4-6": 1})
        self.assertEqual(m["by_role"][0]["role"], "leaf")
        self.assertEqual(m["totals"]["agents"], 1)

    def test_overlord_found_in_other_project_dir_by_slug_mention(self):
        # cascade driven from a different cwd: transcript lives under another project dir,
        # and a same-root session with MORE turns but no slug mention must lose
        proj = cm.project_dir_name(self.fx.root)
        noise = rec("assistant", T1, [{"type": "text", "text": "x"}], "n1", "claude-sonnet-5") * 1
        noise = "".join(rec("assistant", T1, [{"type": "text", "text": "x"}], f"n{i}", "claude-sonnet-5") for i in range(10))
        self.fx.session(proj, "noisy", noise)
        self.fx.session("-Users-someone-elsewhere", "real", self._overlord_lines())
        self.fx.subagent("-Users-someone-elsewhere", "real", "bbb", "leaf-01: build add", "tu1", self._leaf_lines())
        code, _, _, m = self.fx.run()
        self.assertEqual(m["overlord"]["session"], "real")
        self.assertEqual(len(m["agents"]), 1)
        self.assertEqual(code, 0)

    def test_unrelated_subagent_in_window_excluded(self):
        proj = cm.project_dir_name(self.fx.root)
        self.fx.session(proj, "sess1", self._overlord_lines())
        self.fx.subagent(proj, "sess1", "aaa", "leaf-01: build add", "tu1", self._leaf_lines())
        # another session's sub-agent, same window, never mentions the slug
        self.fx.session(proj, "other", rec("assistant", T1, [{"type": "text", "text": "y"}], "o1", "claude-sonnet-5"))
        self.fx.subagent(proj, "other", "zzz", "Research pricing", "tuX",
                         rec("user", T1, "look things up") + rec("assistant", T1, [{"type": "text", "text": "ok"}], "z1", "claude-haiku-4-5"))
        _, _, _, m = self.fx.run()
        self.assertEqual([a["agent_id"] for a in m["agents"]], ["aaa"])

    def test_artifacts_scanned_and_log_filtered_by_window(self):
        proj = cm.project_dir_name(self.fx.root)
        self.fx.session(proj, "sess1", self._overlord_lines())
        _, _, _, m = self.fx.run()
        a = m["artifacts"]
        self.assertEqual(a["leaves"], 2)
        self.assertEqual(a["audits"]["default"], {"rounds": 2, "red": 1, "yellow": 1, "green": 2})
        self.assertEqual(a["gates"], {"FAIL": 0, "ADVISORY": 1, "PASS": 1, "files": 1})
        # leaf-02's row is from an older cascade (timestamp outside window) and must not count
        self.assertEqual(a["log_rows"], {"clean": 1})

    def test_gap_when_no_git_ops_log_and_no_session(self):
        (self.fx.cdir / "git-ops.log").unlink()
        code, out, err, m = self.fx.run("--since", T0, "--until", T2)
        self.assertEqual(code, 1)
        self.assertTrue(any("git-ops.log" in g for g in m["gaps"]))
        self.assertTrue(any("no main-session" in g for g in m["gaps"]))
        self.assertIn("GAP:", err)
        self.assertTrue((self.fx.cdir / "METRICS.md").exists())

    def test_ledger_written_and_no_ledger_flag(self):
        proj = cm.project_dir_name(self.fx.root)
        self.fx.session(proj, "sess1", self._overlord_lines())
        self.fx.run("--variant", "C2")
        files = list(self.fx.ledger.glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].name.startswith("2026-08-28-"))
        self.assertTrue(files[0].name.endswith("-demo.json"))
        self.assertEqual(json.loads(files[0].read_text())["variant"], "C2")
        (self.fx.ledger / files[0].name).unlink()
        self.fx.run("--no-ledger")
        self.assertEqual(list(self.fx.ledger.glob("*.json")), [])

    def test_missing_cascade_dir_exit_2(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--cascade", "nope", "--root", str(self.fx.root),
                               "--projects-root", str(self.fx.projects)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_classify_new_runner_roles(self):
        self.assertEqual(cm.classify("admission-runner leaf-03"), "admission-runner")
        self.assertEqual(cm.classify("sweep-runner wave 1"), "sweep-runner")
        self.assertEqual(cm.classify("leaf-07: build parser"), "leaf")
        self.assertEqual(cm.classify("Something else", "Your brief is inlined below"), "leaf")
        self.assertEqual(cm.classify("Research pricing"), "other")


if __name__ == "__main__":
    unittest.main()
