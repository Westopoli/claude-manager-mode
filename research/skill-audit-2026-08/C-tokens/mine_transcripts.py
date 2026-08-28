#!/usr/bin/env python3
"""Mine local Claude Code subagent transcripts for per-agent token usage.

Walks ~/.claude/projects/<project>/<session>/subagents/agent-*.jsonl (+ .meta.json),
joins each agent to the parent session transcript's `Task` tool_use (by
meta.toolUseId) to recover description / prompt / model / cwd / timestamp,
classifies the cascade role from the description, and writes:

  out/agents.csv      one row per subagent
  out/by_role.csv     aggregates per role (and per role×model)
  out/by_cascade.csv  aggregates per (project, cascade slug, wave, role)
  SUMMARY.md          human summary incl. dedupe stats + unclassified list

Dedupe rule (load-bearing): streamed assistant messages are written once per
chunk, each carrying a `usage` block. Only the LAST record per `message.id`
counts. Naive summing over-counts ~2-2.5x.

Cost: `rates.json` next to this script maps model id -> USD per MTok for
input / cache_write_5m / cache_write_1h / cache_read / output. Unknown model ->
cost columns empty. Never hard-code rates here.

Usage: python3 mine_transcripts.py [--projects-root ~/.claude/projects]
                                   [--claude-swarm /Users/westley/Projects/claude-swarm]
                                   [--out-dir out]
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

ROLE_RULES: list[tuple[str, str]] = [
    # (role, regex on description, case-insensitive) — first match wins
    ("adjudicator", r"adjudicat"),
    ("test-fixer", r"fix \d+ audit finding|test[- ]fixer|^fix .*\btests?\b|^revise .*(test|assert)|fix .*audit"),
    ("test-auditor", r"test[- ]quality[- ]audit|test audit|audit shard|pre-spawn .*audit|adversarial audit|TEST-AUDIT|^(re-)?audit .*(tests?|wave)|^re-audit"),
    ("shard-test-writer", r"shard[- ]test[- ]writer|write .*\bRED\b|failing tests|^write .*tests?\b|^independent .*tests"),
    ("leaf", r"^leaf[- ]?[a-z]?\d+|\bleaf[- ][a-z]?\d+\b.*(build|impl|green)|\bL\d+:|^S\d+ "),
    ("dep-map", r"dependency map|dep[- ]map"),
    ("consolidation", r"consolidat"),
    ("ambiguity", r"ambigu"),
    ("sweep", r"assumption[- ]sweep|\bsweep\b"),
    ("experiment-leaf", r"^(leaf|builder) [A-Z]\d|phase[- ][A-H]\b|rung"),
    ("non-cascade", r"explore|investigat|research|\bmap\b|search|find |locate|summar|review PR|guide|lane [a-z] batch|harvest|design .*plan|decide|survey|look up|track [a-z]"),
]

PROMPT_RULES: list[tuple[str, str]] = [
    # fallback on the first ~4000 chars of the parent Task prompt
    ("leaf", r"You are leaf-\S+ of a TDD cascade|Read your brief at|working inside your own sandbox|impl_files? IN PLACE"),
    ("test-auditor", r"TEST-AUDIT|GOAL FIDELITY|UMBRELLA ALIGNMENT|test-quality audit|adversarial audit|fresh-context.*audit"),
    ("shard-test-writer", r"shard-test-writer|test_owned_by|write .*failing tests|BOUNDARIES\.md"),
    ("test-fixer", r"audit finding|TEST-AUDIT\.md.*fix|repair the test"),
    ("sweep", r"assumption[- ]sweep|ASSUMPTIONS\.md"),
]


def classify(desc: str, prompt: str = "") -> str:
    d = desc or ""
    for role, rx in ROLE_RULES:
        if re.search(rx, d, re.I):
            return role
    head = (prompt or "")[:4000]
    for role, rx in PROMPT_RULES:
        if re.search(rx, head, re.I):
            return role
    return "unclassified"


SLUG_SKIP = {"briefs", "pending", "sandbox", "backups", "audits", "questions", "answers",
             "proposals", "worktrees", "post-review-log.md", "escalations"}


def cascade_slug(text: str) -> str:
    for m in re.finditer(r"\.swarm/([A-Za-z0-9_.\-]+)/", text or ""):
        s = m.group(1)
        if s not in SLUG_SKIP and not s.startswith("wave-"):
            return s
    return ""


def wave_of(text: str) -> str:
    m = re.search(r"wave[- ](\d+)", text or "", re.I)
    return m.group(1) if m else ""


def shard_of(text: str) -> str:
    m = re.search(r"shard[- ]([A-Za-z0-9]+)", text or "", re.I)
    return m.group(1) if m else ""


def iter_jsonl(path: Path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_parent_task(parent_path: Path, tool_use_id: str) -> dict:
    """Return {description, prompt, model, subagent_type, timestamp, cwd} for the Task call."""
    if not tool_use_id or not parent_path.exists():
        return {}
    for rec in iter_jsonl(parent_path):
        msg = rec.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") == tool_use_id:
                inp = block.get("input") or {}
                return {
                    "description": inp.get("description", ""),
                    "prompt": inp.get("prompt", ""),
                    "task_model": inp.get("model", ""),
                    "subagent_type": inp.get("subagent_type", ""),
                    "parent_ts": rec.get("timestamp", ""),
                    "parent_cwd": rec.get("cwd", ""),
                    "parent_version": rec.get("version", ""),
                    "parent_branch": rec.get("gitBranch", ""),
                }
    return {}


def mine_agent(jsonl: Path) -> dict:
    by_id: dict[str, dict] = {}
    order: list[str] = []
    tool_counts: collections.Counter = collections.Counter()
    thinking_chars = 0
    text_chars = 0
    first_user_chars = 0
    first_ts = last_ts = ""
    models: collections.Counter = collections.Counter()
    n_assistant_lines = 0
    user_turns = 0
    for rec in iter_jsonl(jsonl):
        t = rec.get("type")
        ts = rec.get("timestamp") or ""
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        msg = rec.get("message") or {}
        if t == "user":
            user_turns += 1
            if first_user_chars == 0:
                c = msg.get("content")
                first_user_chars = len(c) if isinstance(c, str) else len(json.dumps(c))
            continue
        if t != "assistant":
            continue
        n_assistant_lines += 1
        mid = msg.get("id") or rec.get("uuid")
        if mid not in by_id:
            order.append(mid)
        by_id[mid] = msg  # keep last chunk
        if msg.get("model"):
            models[msg["model"]] += 1
    inp = cc = cc5 = cc1h = cr = out = 0
    for mid in order:
        for block in by_id[mid].get("content") or []:
            if not isinstance(block, dict):
                continue
            bt = block.get("type")
            if bt == "tool_use":
                tool_counts[block.get("name", "?")] += 1
            elif bt == "thinking":
                thinking_chars += len(block.get("thinking") or "")
            elif bt == "text":
                text_chars += len(block.get("text") or "")
        u = (by_id[mid].get("usage") or {})
        inp += u.get("input_tokens", 0) or 0
        cc += u.get("cache_creation_input_tokens", 0) or 0
        ccd = u.get("cache_creation") or {}
        cc5 += ccd.get("ephemeral_5m_input_tokens", 0) or 0
        cc1h += ccd.get("ephemeral_1h_input_tokens", 0) or 0
        cr += u.get("cache_read_input_tokens", 0) or 0
        out += u.get("output_tokens", 0) or 0
    dur = ""
    try:
        if first_ts and last_ts:
            a = dt.datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            b = dt.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            dur = round((b - a).total_seconds(), 1)
    except ValueError:
        pass
    return {
        "turns": len(order),
        "assistant_lines": n_assistant_lines,
        "user_turns": user_turns,
        "input_tokens": inp,
        "cache_write_tokens": cc,
        "cache_write_5m": cc5,
        "cache_write_1h": cc1h,
        "cache_read_tokens": cr,
        "output_tokens": out,
        "fresh_tokens": inp + cc,
        "thinking_chars": thinking_chars,
        "text_chars": text_chars,
        "first_user_chars": first_user_chars,
        "tool_calls": sum(tool_counts.values()),
        "tool_top": ";".join(f"{k}:{v}" for k, v in tool_counts.most_common(5)),
        "msg_model": models.most_common(1)[0][0] if models else "",
        "first_ts": first_ts,
        "last_ts": last_ts,
        "duration_s": dur,
    }


def load_rates(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


def cost_usd(row: dict, rates: dict) -> str:
    r = rates.get(row["model"])
    if not r:
        # try prefix match (e.g. claude-sonnet-4-6 vs claude-sonnet-4-6-20260101)
        for k, v in rates.items():
            if row["model"].startswith(k):
                r = v
                break
    if not r:
        return ""
    usd = (row["input_tokens"] * r["input"] + row["cache_write_5m"] * r["cache_write_5m"]
           + row["cache_write_1h"] * r["cache_write_1h"] + row["cache_read_tokens"] * r["cache_read"]
           + row["output_tokens"] * r["output"]) / 1_000_000
    return f"{usd:.4f}"


_commit_cache: dict[str, str] = {}


def skill_commit_guess(ts: str, swarm_repo: Path) -> str:
    if not ts or not swarm_repo.exists():
        return ""
    day = ts[:10]
    if day in _commit_cache:
        return _commit_cache[day]
    try:
        out = subprocess.run(["git", "-C", str(swarm_repo), "log", "-1", "--before", ts, "--format=%h %ad", "--date=short"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        out = ""
    _commit_cache[day] = out
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects-root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--claude-swarm", default="/Users/westley/Projects/claude-swarm")
    ap.add_argument("--out-dir", default=str(HERE / "out"))
    ap.add_argument("--rates", default=str(HERE / "rates.json"))
    args = ap.parse_args()

    root = Path(args.projects_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rates = load_rates(Path(args.rates))
    swarm_repo = Path(args.claude_swarm)

    rows: list[dict] = []
    for jsonl in sorted(root.glob("*/*/subagents/agent-*.jsonl")):
        session_dir = jsonl.parent.parent
        project = session_dir.parent.name
        session = session_dir.name
        meta_path = jsonl.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        parent = load_parent_task(session_dir.parent / f"{session}.jsonl", meta.get("toolUseId", ""))
        m = mine_agent(jsonl)
        desc = meta.get("description") or parent.get("description") or ""
        prompt = parent.get("prompt", "")
        model = m["msg_model"] or meta.get("model") or parent.get("task_model") or ""
        row = {
            "project": project,
            "session": session,
            "agent_id": jsonl.stem.replace("agent-", ""),
            "agent_type": meta.get("agentType") or parent.get("subagent_type") or "",
            "model": model,
            "model_source": "message" if m["msg_model"] else ("meta" if meta.get("model") else ("task" if parent.get("task_model") else "")),
            "role": classify(desc, prompt),
            "description": desc[:160].replace("\n", " "),
            "cascade": cascade_slug(prompt) or cascade_slug(desc),
            "wave": wave_of(desc) or wave_of(prompt[:2000]),
            "shard": shard_of(desc),
            "prompt_chars": len(prompt),
            "spawn_depth": meta.get("spawnDepth", ""),
            "parent_ts": parent.get("parent_ts", ""),
            "parent_cwd": parent.get("parent_cwd", ""),
            "cc_version": parent.get("parent_version", ""),
            "skill_commit_guess": skill_commit_guess(parent.get("parent_ts") or m["first_ts"], swarm_repo),
            **m,
        }
        row["cost_usd"] = cost_usd(row, rates)
        row["path"] = str(jsonl)
        rows.append(row)

    if not rows:
        print("no subagent transcripts found under", root, file=sys.stderr)
        return 1

    fields = list(rows[0].keys())
    with open(out_dir / "agents.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # aggregates
    def agg(group_keys: list[str], fname: str):
        groups: dict[tuple, list[dict]] = collections.defaultdict(list)
        for r in rows:
            groups[tuple(r[k] for k in group_keys)].append(r)
        out = []
        for key, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            def med(k):
                return int(statistics.median(x[k] for x in rs))

            def p90(k):
                xs = sorted(x[k] for x in rs)
                return xs[min(len(xs) - 1, int(0.9 * len(xs)))]
            costs = [float(x["cost_usd"]) for x in rs if x["cost_usd"]]
            out.append({
                **dict(zip(group_keys, key)),
                "n": len(rs),
                "fresh_med": med("fresh_tokens"), "fresh_p90": p90("fresh_tokens"),
                "cache_read_med": med("cache_read_tokens"), "cache_read_p90": p90("cache_read_tokens"),
                "output_med": med("output_tokens"), "output_p90": p90("output_tokens"),
                "turns_med": med("turns"), "tool_calls_med": med("tool_calls"),
                "first_user_chars_med": med("first_user_chars"),
                "prompt_chars_med": med("prompt_chars"),
                "cost_usd_sum": round(sum(costs), 2) if costs else "",
                "cost_usd_med": round(statistics.median(costs), 3) if costs else "",
                "cost_n": len(costs),
            })
        with open(out_dir / fname, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        return out

    by_role = agg(["role"], "by_role.csv")
    by_role_model = agg(["role", "model"], "by_role_model.csv")
    by_cascade = agg(["project", "cascade", "wave", "role"], "by_cascade.csv")

    total_lines = sum(r["assistant_lines"] for r in rows)
    total_turns = sum(r["turns"] for r in rows)
    uncl = [r for r in rows if r["role"] == "unclassified"]
    uncl_desc = collections.Counter(r["description"][:80] for r in uncl)

    def table(recs: list[dict], cols: list[str]) -> str:
        head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
        return head + "".join("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n" for r in recs)

    summary = [
        "# Token mining summary", "",
        f"Generated {dt.datetime.now().isoformat(timespec='seconds')} from `{root}`.", "",
        f"- agents: **{len(rows)}**; projects: {len({r['project'] for r in rows})}; sessions: {len({r['session'] for r in rows})}",
        f"- dedupe: {total_lines} assistant lines → {total_turns} unique message ids (naive sum would over-count ×{total_lines / max(total_turns, 1):.2f})",
        f"- rates loaded for models: {sorted(rates) if rates else 'NONE — cost columns empty'}",
        f"- model source: " + ", ".join(f"{k}={v}" for k, v in collections.Counter(r['model_source'] for r in rows).items()),
        "", "## By role", "",
        table(by_role, ["role", "n", "fresh_med", "fresh_p90", "cache_read_med", "cache_read_p90", "output_med", "output_p90", "turns_med", "tool_calls_med", "first_user_chars_med", "prompt_chars_med", "cost_usd_med", "cost_usd_sum", "cost_n"]),
        "", "## By role × model", "",
        table(by_role_model, ["role", "model", "n", "fresh_med", "cache_read_med", "output_med", "turns_med", "cost_usd_med", "cost_usd_sum"]),
        "", "## Cascade roles by project", "",
        table([r for r in by_cascade if r["role"] not in ("non-cascade", "unclassified")][:60],
              ["project", "cascade", "wave", "role", "n", "fresh_med", "cache_read_med", "output_med", "turns_med", "cost_usd_sum"]),
        "", f"## Unclassified descriptions ({len(uncl)})", "",
        "\n".join(f"- {n}× `{d}`" for d, n in uncl_desc.most_common(60)),
        "", "## Columns", "",
        "`fresh_tokens` = input_tokens + cache_write_tokens (what was actually sent uncached). `cache_read_tokens` billed at the cache-read rate. "
        "`first_user_chars` = size of the first user message in the subagent transcript (the payload the skill fed). `prompt_chars` = the parent Task `prompt` field length. "
        "`skill_commit_guess` = last claude-swarm commit before the spawn timestamp (assumes the installed skill tracked HEAD; low confidence).",
    ]
    (HERE / "SUMMARY.md").write_text("\n".join(summary) + "\n")
    print(f"{len(rows)} agents → {out_dir}/agents.csv; SUMMARY.md written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
