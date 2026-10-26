#!/usr/bin/env python3
"""Run a test command and parse per-test states (stdlib only).

Shared by degenerate_sweep.py and sabotage_run.py (Phase 3.5). Understands
pytest (`-rA` summary lines) and unittest (`-v` lines). Anything else yields a
TestRun with empty `states`; callers treat that as "not collected".
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_PYTEST_RE = re.compile(r"^(PASSED|FAILED|ERROR)\s+(\S+::\S+)(?:\s+-\s+(.*))?$")
_UT_BLOCK_RE = re.compile(r"^(FAIL|ERROR): (\w+) \(([\w.]+)\)\n-{70}\n(.*?)(?=^={70}|\Z)", re.M | re.S)
_STATE = {"PASSED": "PASS", "FAILED": "FAIL", "ERROR": "ERROR", "ok": "PASS", "FAIL": "FAIL"}


@dataclass
class TestRun:
    __test__ = False  # not a pytest class
    cmd: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    states: dict[str, str] = field(default_factory=dict)
    failure_text: dict[str, str] = field(default_factory=dict)
    collected: bool = False


def _prepare(cmd: str | list[str]) -> list[str]:
    argv = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
    joined = " ".join(argv)
    if "pytest" in joined and "-v" not in argv:
        argv += ["-v", "-rA", "--tb=short", "-p", "no:cacheprovider"]
    elif "unittest" in joined and "-v" not in argv:
        argv.append("-v")
    return argv


def _ut_id(name: str, qual: str) -> str:
    """3.11+ prints `name (pkg.Class.name)`; older prints `name (pkg.Class)`."""
    return qual if qual.endswith("." + name) else f"{qual}.{name}"


def parse(text: str) -> tuple[dict[str, str], dict[str, str]]:
    states: dict[str, str] = {}
    fails: dict[str, str] = {}
    for line in text.splitlines():
        m = _PYTEST_RE.match(line.strip())
        if m:
            states[m.group(2)] = _STATE[m.group(1)]
            if m.group(3):
                fails[m.group(2)] = m.group(3)
    for m in re.finditer(r"^(\w+) \(([\w.]+)\)[^\n]*? \.\.\. (ok|FAIL|ERROR)\b", text, re.M):
        states[_ut_id(m.group(1), m.group(2))] = _STATE[m.group(3)]
    for m in _UT_BLOCK_RE.finditer(text):
        fails[_ut_id(m.group(2), m.group(3))] = m.group(4)
    # pytest --tb=short prints per-test blocks; attach full text so NotImplementedError is visible
    for m in re.finditer(r"^_{3,} (\S+) _{3,}\n(.*?)(?=^_{3,} |^={3,} |\Z)", text, re.M | re.S):
        name = m.group(1)
        for tid in states:
            if tid.endswith("::" + name) or tid == name:
                fails[tid] = fails.get(tid, "") + "\n" + m.group(2)
    return states, fails


def run_tests(cmd: str | list[str], cwd: Path, timeout: int = 120,
              env: dict[str, str] | None = None) -> TestRun:
    argv = _prepare(cmd)
    full_env = {**os.environ, **(env or {}), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, env=full_env)
    except subprocess.TimeoutExpired as e:
        return TestRun(argv, -1, str(e.stdout or ""), str(e.stderr or ""))
    except FileNotFoundError as e:
        return TestRun(argv, -1, "", str(e))
    text = proc.stdout + "\n" + proc.stderr
    states, fails = parse(text)
    return TestRun(argv, proc.returncode, proc.stdout, proc.stderr, states, fails,
                   collected=bool(states))
