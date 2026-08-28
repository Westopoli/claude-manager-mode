#!/usr/bin/env python3
"""Record one cascade's cost and outcome. Invoked by /manager-mode Phase 7.2.

Why this exists
---------------
The 2026-08 skill audit found that the overlord chat — not the sub-agents — is
~78% of a cascade's dollar cost, and that nobody had ever measured it because
the only mining pass looked at sub-agent transcripts. This script closes that
gap for every future cascade, at zero LLM cost: it reads the local Claude Code
transcripts for the window the cascade ran in, attributes tokens to overlord
vs each cascade role, joins that to the cascade's own artifacts (gates,
audits, log rows), and writes the result next to the cascade *and* into a
per-user ledger that survives a gitignored `.swarm/`.

Window: from the first line of `.swarm/<slug>/git-ops.log` (Phase 0.0
preflight is the cascade's first git call) to its last line, or `--until now`.
Only assistant messages timestamped inside the window count, so a long mixed
session is charged for the cascade only — not for whatever came before it.

Dedupe rule (load-bearing, same as the audit's miner): streamed assistant
messages are written once per chunk, each carrying `usage`. Only the LAST
record per `message.id` counts. Naive summing over-counts ~2x.

Rates: `rates.json` beside this script, model id -> USD per MTok. Unknown
model -> cost left blank, tokens still recorded. Never hard-code rates here.

Outputs
  .swarm/<slug>/METRICS.json   machine-readable, one object
  .swarm/<slug>/METRICS.md     the table Phase 7.2 pastes into the report
  <ledger-dir>/<date>-<project>-<slug>.json   same object, cross-project ledger
                                              (default ~/.claude/swarm-metrics/)

Exit 0 written; 1 written but with a gap (no transcript found for the window,
no git-ops.log); 2 resolution/config error.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# ---------- role classification (ported verbatim from the audit miner) ----------

ROLE_RULES: list[tuple[str, str]] = [
    ("adjudicator", r"adjudicat"),
    ("admission-runner", r"admission[- ]runner|^admit leaf|run_gates.*admit"),
    ("sweep-runner", r"sweep[- ]runner"),
    ("test-fixer", r"fix \d+ audit finding|test[- ]fixer|^fix .*\btests?\b|^revise .*(test|assert)|fix .*audit"),
    ("test-auditor", r"test[- ]quality[- ]audit|test audit|audit shard|pre-spawn .*audit|adversarial audit|TEST-AUDIT|^(re-)?audit .*(tests?|wave)|^re-audit"),
    ("shard-test-writer", r"shard[- ]test[- ]writer|write .*\bRED\b|failing tests|^write .*tests?\b|^independent .*tests"),
    ("leaf", r"^leaf[- ]?[a-z]?\d+|\bleaf[- ][a-z]?\d+\b.*(build|impl|green)|\bL\d+:"),
    ("dep-map", r"dependency map|dep[- ]map"),
    ("consolidation", r"consolidat"),
    ("ambiguity", r"ambigu"),
    ("sweep", r"assumption[- ]sweep|\bsweep\b"),
]

PROMPT_RULES: list[tuple[str, str]] = [
    ("leaf", r"You are leaf-\S+ of a TDD cascade|Read your brief at|Your brief is inlined|impl_files? IN PLACE"),
    ("admission-runner", r"admission-runner|run_gates\.py.*admit"),
    ("sweep-runner", r"sweep-runner|assumption[- ]sweep"),
    ("test-auditor", r"TEST-AUDIT|GOAL FIDELITY|UMBRELLA ALIGNMENT|test-quality audit|fresh-context.*audit"),
    ("shard-test-writer", r"shard-test-writer|test_owned_by|write .*failing tests|BOUNDARIES\.md"),
    ("test-fixer", r"audit finding|TEST-AUDIT\.md.*fix|repair the test"),
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
    return "other"


# ---------- transcript helpers ----------

def parse_ts(s: str) -> dt.datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        m = re.match(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})", s)
        if not m:
            return None
        d = dt.datetime.fromisoformat(m.group(1))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


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


def usage_of(msg: dict) -> dict[str, int]:
    u = msg.get("usage") or {}
    ccd = u.get("cache_creation") or {}
    return {
        "input_tokens": u.get("input_tokens", 0) or 0,
        "cache_write_5m": ccd.get("ephemeral_5m_input_tokens", 0) or 0,
        "cache_write_1h": ccd.get("ephemeral_1h_input_tokens", 0) or 0,
        "cache_write_tokens": u.get("cache_creation_input_tokens", 0) or 0,
        "cache_read_tokens": u.get("cache_read_input_tokens", 0) or 0,
        "output_tokens": u.get("output_tokens", 0) or 0,
    }


def zero_usage() -> dict[str, int]:
    return {k: 0 for k in ("input_tokens", "cache_write_5m", "cache_write_1h",
                           "cache_write_tokens", "cache_read_tokens", "output_tokens", "turns")}


def add_usage(acc: dict[str, int], u: dict[str, int]) -> None:
    for k, v in u.items():
        acc[k] = acc.get(k, 0) + v
    acc["turns"] = acc.get("turns", 0) + 1


def mine_transcript(path: Path, since: dt.datetime | None, until: dt.datetime | None,
                    slug: str = "") -> tuple[dict[str, int], collections.Counter, list[dict], dt.datetime | None, dt.datetime | None, int]:
    """Deduped usage for assistant messages inside [since, until].

    Returns (usage, model_counter, task_calls, first_ts, last_ts, slug_mentions).
    slug_mentions counts in-window records (any type) whose text names the
    cascade slug — how a session proves it is this cascade's overlord, since a
    cascade can be driven from a cwd other than the project root. task_calls is
    every `Task` tool_use in the window with its input — the parent side of the
    sub-agent join, and the source of "which model did the overlord actually
    ask for" per role.
    """
    by_id: dict[str, dict] = {}
    order: list[str] = []
    ts_of: dict[str, dt.datetime | None] = {}
    first = last = None
    mentions = 0
    for rec in iter_jsonl(path):
        ts = parse_ts(rec.get("timestamp") or "")
        if since and ts and ts < since:
            continue
        if until and ts and ts > until:
            continue
        if slug and rec.get("type") in ("user", "assistant") and slug in json.dumps(rec.get("message") or {}):
            mentions += 1
        if rec.get("type") != "assistant":
            continue
        if ts is not None:
            first = first or ts
            last = ts
        msg = rec.get("message") or {}
        mid = msg.get("id") or rec.get("uuid")
        if mid not in by_id:
            order.append(mid)
        by_id[mid] = msg
        ts_of[mid] = ts
    usage = zero_usage()
    models: collections.Counter = collections.Counter()
    tasks: list[dict] = []
    for mid in order:
        msg = by_id[mid]
        add_usage(usage, usage_of(msg))
        if msg.get("model"):
            models[msg["model"]] += 1
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Task":
                inp = block.get("input") or {}
                tasks.append({
                    "tool_use_id": block.get("id", ""),
                    "description": inp.get("description", ""),
                    "prompt": inp.get("prompt", ""),
                    "model": inp.get("model", ""),
                    "subagent_type": inp.get("subagent_type", ""),
                    "ts": ts_of.get(mid).isoformat() if ts_of.get(mid) else "",
                })
    return usage, models, tasks, first, last, mentions


# ---------- cost ----------

def load_rates(path: Path) -> dict:
    if not path.exists():
        return {}
    return {k: v for k, v in json.loads(path.read_text()).items() if not k.startswith("_")}


def cost_usd(model: str, u: dict[str, int], rates: dict) -> float | None:
    r = rates.get(model)
    if not r:
        for k, v in rates.items():
            if model and model.startswith(k):
                r = v
                break
    if not r:
        return None
    # cache_write_tokens is the total; the 5m/1h split is only present on newer
    # records. Bill the split when we have it, else everything at the 5m rate.
    split = u.get("cache_write_5m", 0) + u.get("cache_write_1h", 0)
    if split:
        cw = u["cache_write_5m"] * r["cache_write_5m"] + u["cache_write_1h"] * r["cache_write_1h"]
    else:
        cw = u.get("cache_write_tokens", 0) * r["cache_write_5m"]
    usd = (u["input_tokens"] * r["input"] + cw + u["cache_read_tokens"] * r["cache_read"]
           + u["output_tokens"] * r["output"]) / 1_000_000
    return round(usd, 4)


# ---------- cascade artifacts ----------

def read_window(cdir: Path) -> tuple[dt.datetime | None, dt.datetime | None]:
    log = cdir / "git-ops.log"
    if not log.exists():
        return None, None
    first = last = None
    for line in log.read_text(errors="replace").splitlines():
        if line.startswith(" "):
            continue
        ts = parse_ts(line.split(" | ", 1)[0])
        if ts is None:
            continue
        first = first or ts
        last = ts
    return first, last


def count_marks(text: str) -> dict[str, int]:
    return {"red": text.count("🔴"), "yellow": text.count("🟡"), "green": text.count("🟢")}


def scan_artifacts(root: Path, cdir: Path, since: dt.datetime | None = None,
                   until: dt.datetime | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    briefs = sorted(p for p in cdir.rglob("leaf-*.md") if "." not in p.stem and "briefs" in p.parts)
    out["leaves"] = len(briefs)
    leaf_ids = {p.stem for p in briefs}
    shards: dict[str, dict[str, Any]] = {}
    gates = {"FAIL": 0, "ADVISORY": 0, "PASS": 0, "files": 0}
    for p in sorted(cdir.rglob("*")):
        if not p.is_file():
            continue
        name = p.name
        if name.startswith("TEST-AUDIT") and name.endswith(".md") and name != "TEST-AUDIT-BRIEF.md":
            sh = shards.setdefault(p.parent.name, {"rounds": 0, "red": 0, "yellow": 0, "green": 0})
            sh["rounds"] += 1
            for k, v in count_marks(p.read_text(errors="replace")).items():
                sh[k] += v
        elif name.endswith(".GATES.md"):
            gates["files"] += 1
            txt = p.read_text(errors="replace")
            for k in ("FAIL", "ADVISORY", "PASS"):
                gates[k] += len(re.findall(rf"\|\s*{k}\s*\|", txt))
    out["audits"] = shards
    out["gates"] = gates
    out["questions"] = len(list((cdir / "questions").glob("*.md"))) if (cdir / "questions").is_dir() else 0
    out["answers"] = len(list((cdir / "answers").glob("*.md"))) if (cdir / "answers").is_dir() else 0
    out["proposals"] = len(list((cdir / "proposals").glob("*.md"))) if (cdir / "proposals").is_dir() else 0
    flagged = None
    for p in cdir.glob("wave-*.SWEEP.md"):
        m = re.search(r"Flagged:\s*(\d+)", p.read_text(errors="replace"))
        if m:
            flagged = (flagged or 0) + int(m.group(1))
        elif "clean" in p.read_text(errors="replace").lower():
            flagged = flagged or 0
    out["sweep_flagged"] = flagged
    log = root / ".swarm" / "post-review-log.md"
    status: collections.Counter = collections.Counter()
    if log.exists():
        for line in log.read_text(errors="replace").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 7 or cells[0] in ("wave", "------"):
                continue
            leaf = cells[2]
            if leaf not in leaf_ids:
                continue
            # the log is global and leaf ids repeat across cascades: only rows
            # stamped inside this cascade's window belong to it
            ts = parse_ts(cells[5])
            if since and ts and ts < since:
                continue
            if until and ts and ts > until:
                continue
            status[cells[6].split()[0].lower() if cells[6] else "?"] += 1
    out["log_rows"] = dict(status)
    return out


# ---------- skill fingerprint ----------

def skill_fingerprint() -> dict[str, str]:
    fp: dict[str, str] = {}
    skill_md = HERE.parent.parent / "manager-mode" / "SKILL.md"
    if skill_md.exists():
        fp["manager_mode_sha256"] = hashlib.sha256(skill_md.read_bytes()).hexdigest()[:16]
    try:
        out = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            fp["skills_commit"] = out.stdout.strip()
    except Exception:
        pass
    return fp


# ---------- main ----------

def project_dir_name(root: Path) -> str:
    return str(root.resolve()).replace("/", "-")


def fmt_int(n: int) -> str:
    return f"{n:,}"


def render_md(m: dict[str, Any]) -> str:
    L = [f"# Cascade metrics — `{m['cascade']}`", ""]
    L.append(f"- window: {m['window']['since'] or '?'} → {m['window']['until'] or '?'} "
             f"({m['window']['wall_clock_min']} min)")
    L.append(f"- overlord session: `{m['overlord']['session'] or 'NOT FOUND'}` "
             f"model={m['overlord']['model'] or '?'}  variant={m['variant'] or '-'}  "
             f"skill={m['skill'].get('skills_commit', '?')}/{m['skill'].get('manager_mode_sha256', '?')}")
    L.append("")
    L.append("| role | model | n | turns | fresh | cache_read | output | $ |")
    L.append("|---|---|---|---|---|---|---|---|")
    o = m["overlord"]
    u = o["usage"]
    L.append(f"| overlord | {o['model'] or '?'} | 1 | {u['turns']} | {fmt_int(u['input_tokens'] + u['cache_write_tokens'])} "
             f"| {fmt_int(u['cache_read_tokens'])} | {fmt_int(u['output_tokens'])} | {o['cost_usd'] if o['cost_usd'] is not None else '?'} |")
    for r in m["by_role"]:
        u = r["usage"]
        L.append(f"| {r['role']} | {r['model']} | {r['n']} | {u['turns']} | {fmt_int(u['input_tokens'] + u['cache_write_tokens'])} "
                 f"| {fmt_int(u['cache_read_tokens'])} | {fmt_int(u['output_tokens'])} | {r['cost_usd'] if r['cost_usd'] is not None else '?'} |")
    t = m["totals"]
    L.append(f"| **total** | | {t['agents'] + 1} | {t['turns']} | | | | **{t['cost_usd'] if t['cost_usd'] is not None else '?'}** |")
    if t["cost_usd"] and m["overlord"]["cost_usd"]:
        L.append(f"\noverlord share of $: **{100 * m['overlord']['cost_usd'] / t['cost_usd']:.1f}%**")
    a = m["artifacts"]
    L.append("")
    L.append(f"- leaves {a['leaves']} · log rows {a['log_rows']} · gates FAIL {a['gates']['FAIL']} / ADVISORY {a['gates']['ADVISORY']} "
             f"/ PASS {a['gates']['PASS']} over {a['gates']['files']} files")
    for sh, v in a["audits"].items():
        L.append(f"- audit {sh}: {v['rounds']} round(s), 🔴{v['red']} 🟡{v['yellow']} 🟢{v['green']}")
    L.append(f"- questions {a['questions']} / answers {a['answers']} · proposals {a['proposals']} · sweep flagged {a['sweep_flagged']}")
    if m["gaps"]:
        L.append("")
        L.append("GAPS: " + "; ".join(m["gaps"]))
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="record a cascade's token cost + outcome")
    p.add_argument("--cascade", required=True, help="cascade slug (.swarm/<slug>/)")
    p.add_argument("--root", type=Path, default=Path.cwd(), help="project root (the user's checkout)")
    p.add_argument("--projects-root", type=Path, default=Path(os.path.expanduser("~/.claude/projects")))
    p.add_argument("--ledger-dir", type=Path, default=Path(os.path.expanduser("~/.claude/swarm-metrics")))
    p.add_argument("--rates", type=Path, default=HERE / "rates.json")
    p.add_argument("--since", help="override window start (ISO)")
    p.add_argument("--until", help="override window end (ISO); default: git-ops.log last line, or now with --live")
    p.add_argument("--live", action="store_true", help="window ends now (use when finish has not run yet)")
    p.add_argument("--session", help="force a main-session id instead of auto-detecting")
    p.add_argument("--variant", default="", help="free label for the skill variant under test (e.g. C0, C2)")
    p.add_argument("--no-ledger", action="store_true")
    args = p.parse_args(argv)

    root = args.root.resolve()
    cdir = root / ".swarm" / args.cascade
    if not cdir.is_dir():
        print(f"cascade dir not found: {cdir}", file=sys.stderr)
        return 2
    gaps: list[str] = []

    since, until = read_window(cdir)
    if since is None:
        gaps.append("no git-ops.log — window unknown; pass --since/--until")
    if args.since:
        since = parse_ts(args.since)
    if args.until:
        until = parse_ts(args.until)
    elif args.live or until is None:
        until = dt.datetime.now(dt.timezone.utc)
    if since:
        since = since - dt.timedelta(minutes=2)  # preflight is the first git call; Phase 0 starts just before it

    pdir = args.projects_root / project_dir_name(root)
    rates = load_rates(args.rates)

    # --- overlord: across EVERY project dir (a cascade may be driven from another cwd),
    # the main-session transcript that names this slug most inside the window;
    # ties (or no mentions anywhere) fall back to most assistant turns in-window.
    best: tuple[tuple[int, int], Path | None] = ((0, 0), None)
    if args.session:
        candidates = sorted(args.projects_root.glob(f"*/{args.session}.jsonl"))
    elif args.projects_root.is_dir():
        candidates = sorted(args.projects_root.glob("*/*.jsonl"))
    else:
        candidates = []
    for sp in candidates:
        if since:
            try:
                mtime = dt.datetime.fromtimestamp(sp.stat().st_mtime, dt.timezone.utc)
            except OSError:
                continue
            if mtime < since:
                continue
        u, _, _, _, _, mentions = mine_transcript(sp, since, until, args.cascade)
        score = (mentions, u["turns"])
        if u["turns"] and score > best[0]:
            best = (score, sp)
    o_usage = zero_usage()
    o_models: collections.Counter = collections.Counter()
    tasks: list[dict] = []
    session_id = ""
    session_path: Path | None = best[1]
    if session_path is not None:
        o_usage, o_models, tasks, _, _, mentions = mine_transcript(session_path, since, until, args.cascade)
        session_id = session_path.stem
        if not mentions:
            gaps.append(f"overlord session {session_id} never names `{args.cascade}` in-window — picked by turn count only")
    else:
        gaps.append(f"no main-session transcript with turns in window under {args.projects_root}")
    o_model = o_models.most_common(1)[0][0] if o_models else ""

    # --- sub-agents spawned in the window, joined to their Task call by toolUseId
    task_by_id = {t["tool_use_id"]: t for t in tasks}
    agents: list[dict] = []
    sub_globs = ([session_path.parent / session_id / "subagents"] if session_path else []) 
    if args.projects_root.is_dir():
        sub_globs += [d for d in args.projects_root.glob("*/*/subagents") if d not in sub_globs]
    for sdir in sub_globs:
        for jl in sorted(sdir.glob("agent-*.jsonl")):
            try:
                if since and dt.datetime.fromtimestamp(jl.stat().st_mtime, dt.timezone.utc) < since:
                    continue
            except OSError:
                continue
            meta_p = jl.with_suffix(".meta.json")
            meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
            t = task_by_id.get(meta.get("toolUseId", ""), {})
            u, models, _, first, last, mentions = mine_transcript(jl, None, None, args.cascade)
            if first is None:
                continue
            if since and first < since:
                continue
            if until and first > until:
                continue
            own = jl.parent.parent.name == session_id
            if not own and not mentions and args.cascade not in (meta.get("description") or ""):
                continue  # some other session's unrelated sub-agent that happened to run in the window
            desc = meta.get("description") or t.get("description", "")
            role = classify(desc, t.get("prompt", ""))
            model = models.most_common(1)[0][0] if models else (t.get("model") or "")
            agents.append({
                "agent_id": jl.stem.replace("agent-", ""),
                "session": jl.parent.parent.name,
                "role": role,
                "description": desc[:120],
                "model": model,
                "requested_model": t.get("model", ""),
                "subagent_type": meta.get("agentType") or t.get("subagent_type", ""),
                "usage": u,
                "cost_usd": cost_usd(model, u, rates),
                "duration_s": round((last - first).total_seconds(), 1) if first and last else None,
            })

    by_role_acc: dict[tuple[str, str], dict[str, Any]] = {}
    for a in agents:
        key = (a["role"], a["model"])
        acc = by_role_acc.setdefault(key, {"role": a["role"], "model": a["model"], "n": 0, "usage": zero_usage(), "cost_usd": 0.0, "_priced": True})
        acc["n"] += 1
        for k, v in a["usage"].items():
            acc["usage"][k] += v
        if a["cost_usd"] is None:
            acc["_priced"] = False
        else:
            acc["cost_usd"] += a["cost_usd"]
    by_role = []
    for acc in sorted(by_role_acc.values(), key=lambda r: (r["role"], r["model"])):
        acc["cost_usd"] = round(acc["cost_usd"], 4) if acc.pop("_priced") else None
        by_role.append(acc)

    o_cost = cost_usd(o_model, o_usage, rates) if o_model else None
    sub_cost = sum(r["cost_usd"] for r in by_role if r["cost_usd"] is not None)
    all_priced = o_cost is not None and all(r["cost_usd"] is not None for r in by_role)
    total_cost = round(o_cost + sub_cost, 4) if all_priced else None
    if not all_priced:
        gaps.append("one or more models missing from rates.json — $ incomplete")

    requested = collections.defaultdict(collections.Counter)
    for t in tasks:
        requested[classify(t["description"], t["prompt"])][t["model"] or "(inherit)"] += 1

    metrics: dict[str, Any] = {
        "schema": 1,
        "cascade": args.cascade,
        "project": project_dir_name(root),
        "root": str(root),
        "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "variant": args.variant,
        "skill": skill_fingerprint(),
        "window": {
            "since": since.isoformat(timespec="seconds") if since else None,
            "until": until.isoformat(timespec="seconds") if until else None,
            "wall_clock_min": round((until - since).total_seconds() / 60, 1) if since and until else None,
        },
        "overlord": {"session": session_id, "model": o_model, "usage": o_usage, "cost_usd": o_cost},
        "requested_models": {r: dict(c) for r, c in requested.items()},
        "by_role": by_role,
        "agents": agents,
        "totals": {
            "agents": len(agents),
            "turns": o_usage["turns"] + sum(a["usage"]["turns"] for a in agents),
            "cost_usd": total_cost,
            "subagent_cost_usd": round(sub_cost, 4),
        },
        "artifacts": scan_artifacts(root, cdir, since, until),
        "gaps": gaps,
    }

    (cdir / "METRICS.json").write_text(json.dumps(metrics, indent=1) + "\n")
    (cdir / "METRICS.md").write_text(render_md(metrics))
    ledger = None
    if not args.no_ledger:
        args.ledger_dir.mkdir(parents=True, exist_ok=True)
        day = (since or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%d")
        ledger = args.ledger_dir / f"{day}-{project_dir_name(root).strip('-')}-{args.cascade}.json"
        ledger.write_text(json.dumps(metrics, indent=1) + "\n")

    share = f"{100 * o_cost / total_cost:.0f}%" if (o_cost and total_cost) else "?"
    print(f"--- {args.cascade}: overlord {o_model or '?'} ${o_cost if o_cost is not None else '?'} ({share}), "
          f"{len(agents)} sub-agents ${round(sub_cost, 2)}, total ${total_cost if total_cost is not None else '?'}, "
          f"{metrics['window']['wall_clock_min']} min, {len(gaps)} gap(s) ---")
    print(f"METRICS written to {cdir / 'METRICS.md'}" + (f" and {ledger}" if ledger else ""))
    for g in gaps:
        print(f"GAP: {g}", file=sys.stderr)
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
