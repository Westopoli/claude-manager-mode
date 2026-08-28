#!/usr/bin/env python3
"""Extract per-cascade test-audit ledgers from a project's .swarm/ tree.

For every cascade under <swarm-dir> (per-slug subdir with briefs/, or the legacy
flat layout where .swarm/briefs/ holds everything), build one JSON + one MD
ledger joining:

  spec ACs  ->  briefs (leaf, impl/test files, spec_lines)
            ->  test files (# spec: header, test fns, assertion counts, kind tags)
            ->  audit findings (TEST-AUDIT.md any dialect, wave-N.AUDIT.md legacy)
            ->  gate evidence (leaf-NN.GATES.md), post-review-log rows, backups
            ->  BOUNDARIES.md rows, SWEEP/REPORT "Skill observation" blocks

Everything is quoted or cited with a path; nothing is judged here. Judgment
(does admitted impl violate an uncovered rule? was a finding material?) is the
B3 pass, which reads these ledgers.

Usage:
  python3 extract_ledgers.py --repo-root /path/to/repo --repo-name agora \
      [--swarm-dir /other/.swarm] [--only cascade-driver] [--out ledgers]
"""
from __future__ import annotations

import argparse
import ast
import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SEV = {"🔴": "red", "🟡": "yellow", "🟢": "green"}
SEV_RX = re.compile("[🔴🟡🟢]")
AC_RX = re.compile(r"\b(?:[A-Z]\d+-)?AC-(\d+[a-z]?)\b")
SPEC_LINK_RX = re.compile(r"^\s*(?:#|//|--|/\*|\*)\s*spec:\s*(\S+?)::(.+?)::(AC-[^\s,]+(?:\s*,\s*AC-[^\s,]+)*)", re.M)
TEST_FILE_RX = re.compile(r"((?:tests?|spec)/[\w./\-]+\.(?:py|mjs|js|ts|tsx|cjs))")
TEST_FN_RX = re.compile(r"\b(test_[A-Za-z0-9_]+)\b")


# ---------------------------------------------------------------- helpers
def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    key = None
    for line in parts[1].splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val == "" or val == "|":
                fm[key] = []
            else:
                fm[key] = val.strip("\"'")
            continue
        m = re.match(r"^\s+-\s+(.*)$", line)
        if m and key is not None and isinstance(fm.get(key), list):
            fm[key].append(m.group(1).strip().strip("\"'"))
    return fm


def as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def brief_paths(fm: dict) -> tuple[list[str], list[str]]:
    tests = as_list(fm.get("test_files")) or as_list(fm.get("test_file"))
    impls = as_list(fm.get("impl_files")) or as_list(fm.get("impl_file"))
    return tests, impls


# ---------------------------------------------------------------- spec
def parse_spec(spec_text: str) -> dict[str, dict]:
    """Return {AC-N: {text, line_start, line_end, section}}."""
    acs: dict[str, dict] = {}
    lines = spec_text.splitlines()
    has_heading = bool(re.search(r"(?m)^##\s+Acceptance", spec_text, re.I))
    in_ac = not has_heading  # no heading → scan the whole document for AC labels
    cur = None
    section = ""
    for i, line in enumerate(lines, 1):
        if re.match(r"^##\s+Acceptance", line, re.I):
            in_ac = True
            continue
        if not has_heading and line.startswith("## "):
            section = line[3:].strip()
        if in_ac and has_heading and re.match(r"^##\s", line):
            if cur:
                acs[cur]["line_end"] = i - 1
            break
        if not in_ac:
            continue
        if line.startswith("### "):
            section = line[4:].strip()
        m = re.match(r"^\s*(?:\d+\.\s*)?(?:[-*]\s*)?\**\s*(?:\|\s*)?((?:[A-Z]\d+-)?AC-\d+[a-z]?)\b", line)
        if m:
            if cur:
                acs[cur]["line_end"] = i - 1
            cur = m.group(1)
            acs[cur] = {"text": line.strip(), "line_start": i, "line_end": i, "section": section}
            continue
        if cur and line.strip():
            acs[cur]["text"] += " " + line.strip()
    if cur and acs[cur]["line_end"] == acs[cur]["line_start"]:
        acs[cur]["line_end"] = len(lines)
    for ac in acs.values():
        ac["text"] = re.sub(r"\s+", " ", ac["text"])[:1200]
    return acs


# ---------------------------------------------------------------- tests
def parse_test_file(path: Path, text: str) -> dict:
    out = {"path": str(path), "exists": bool(text), "lines": text.count("\n") + 1 if text else 0,
           "spec_link": None, "spec_acs": [], "tests": [], "assertions": 0, "kinds": []}
    if not text:
        return out
    m = SPEC_LINK_RX.search(text[:2000])
    if m:
        out["spec_link"] = f"{m.group(1)}::{m.group(2)}::{m.group(3)}"
        out["spec_acs"] = [a.strip() for a in m.group(3).split(",")]
    suffix = path.suffix
    kinds = set()
    if suffix == ".py":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                    n_assert = sum(1 for n in ast.walk(node) if isinstance(n, ast.Assert))
                    n_raises = sum(1 for n in ast.walk(node) if isinstance(n, ast.withitem)
                                   and "raises" in ast.unparse(n.context_expr))
                    src = ast.get_source_segment(text, node) or ""
                    acs = sorted(set(AC_RX.findall(src)))
                    out["tests"].append({"name": node.name, "line": node.lineno,
                                         "assertions": n_assert + n_raises, "acs_mentioned": [f"AC-{a}" for a in acs]})
                    out["assertions"] += n_assert + n_raises
        except SyntaxError as e:
            out["parse_error"] = str(e)
        if re.search(r"read_text\(|\.read\(\)|inspect\.getsource|open\(", text) and re.search(r"(src|scripts)/", text):
            kinds.add("source-grep")
        if re.search(r"ast\.parse|ast\.walk", text):
            kinds.add("ast-structural")
    else:  # JS/TS
        for m in re.finditer(r"^\s*(?:test|it)\(\s*(['\"`])(.+?)\1", text, re.M):
            out["tests"].append({"name": m.group(2)[:120], "line": text[:m.start()].count("\n") + 1,
                                 "assertions": None, "acs_mentioned": [f"AC-{a}" for a in sorted(set(AC_RX.findall(m.group(2))))]})
        out["assertions"] = len(re.findall(r"\bexpect\(|\bassert\.\w+\(|\bassert\(", text))
        if re.search(r"readFileSync|readFile\(", text) and re.search(r"(src|scripts)/", text):
            kinds.add("source-grep")
    if re.search(r"scale_assert|growth|ratio", text, re.I) and re.search(r"time\.|perf_counter|performance\.now", text):
        kinds.add("scale-ratio")
    if re.search(r"monkeypatch|mock|MagicMock|jest\.fn|vi\.fn|sinon", text):
        kinds.add("uses-mocks")
    out["kinds"] = sorted(kinds)
    return out


# ---------------------------------------------------------------- audits
def split_passes(text: str) -> list[tuple[str, str]]:
    """Split a TEST-AUDIT.md into (pass_label, body) by '## Re-audit' style headings."""
    parts = re.split(r"(?m)^(## (?:Re-audit|Re-Audit|Follow-up|Updated counts|Second pass)[^\n]*)$", text)
    passes = [("pass-1", parts[0])]
    for i in range(1, len(parts), 2):
        passes.append((parts[i].strip("# ").strip()[:60], parts[i + 1] if i + 1 < len(parts) else ""))
    return passes


def verdict_line(text: str) -> str:
    m = re.search(r"(?im)^\s*\**\s*verdict\s*[:—-]\s*\**\s*(.+)$", text)
    if m:
        return m.group(1).strip()[:160]
    m = re.search(r"(?im)^(.*(?:clear to spawn|cleared to spawn|BLOCKED|PASS —).*)$", text)
    return m.group(1).strip()[:160] if m else ""


def parse_findings(body: str) -> list[dict]:
    """Dialect-tolerant finding extraction.

    1. Table rows whose cells contain a severity emoji.
    2. '### <id> — <title>' headings under a '## <emoji>' section, or headings that carry an emoji.
    3. Bullet lines starting with an emoji (legacy AUDIT.md).
    """
    findings: list[dict] = []
    seen = set()
    cur_sev = None
    in_counts = False
    lines = body.splitlines()
    for i, line in enumerate(lines, 1):
        h2 = re.match(r"^##\s+(.*)$", line)
        if h2:
            e = SEV_RX.search(h2.group(1))
            cur_sev = SEV[e.group(0)] if e else None
            in_counts = bool(re.search(r"count|summary|total|verdict|index|resolution", h2.group(1), re.I))
            continue
        # inline "**🟡 F1**" / "**F1** ... 🟡" findings in prose or numbered lists
        if not line.startswith("|") and not line.startswith("#"):
            for m in re.finditer(r"([🔴🟡🟢])\s*\**\s*([A-Z]{1,2}-?\d+[a-z]?)\b|\*\*([A-Z]{1,2}-?\d+[a-z]?)\*\*[^\n]{0,40}?([🔴🟡🟢])", line):
                fid = m.group(2) or m.group(3)
                sev = SEV[m.group(1) or m.group(4)]
                if fid.startswith("AC") or fid.startswith("L") or fid.startswith("Q"):
                    continue
                findings.append({"id": fid, "severity": sev, "line": i, "kind": "inline", "text": line.strip()[:400],
                                 "test_files": sorted(set(TEST_FILE_RX.findall(line))),
                                 "test_fns": sorted(set(TEST_FN_RX.findall(line))),
                                 "acs": sorted({f"AC-{a}" for a in AC_RX.findall(line)})})
            continue
        # table row
        if line.startswith("|") and SEV_RX.search(line) and not re.match(r"^\|\s*-", line) and not in_counts:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if any(c.lower() in ("severity", "count") for c in cells):
                continue
            # summary rows like "| 🔴 blocks | 1 |" — skip (2 cells, numeric second)
            if len(cells) <= 2 and cells[-1].strip().isdigit():
                continue
            sev = SEV[SEV_RX.search(line).group(0)]
            fid = cells[0][:20]
            key = ("row", i)
            if key in seen:
                continue
            seen.add(key)
            findings.append({"id": fid, "severity": sev, "line": i, "kind": "table",
                             "text": " | ".join(cells)[:600],
                             "test_files": sorted(set(TEST_FILE_RX.findall(line))),
                             "test_fns": sorted(set(TEST_FN_RX.findall(line))),
                             "acs": sorted({f"AC-{a}" for a in AC_RX.findall(line)})})
            continue
        h3 = re.match(r"^###\s+(.*)$", line)
        if h3:
            title = h3.group(1)
            e = SEV_RX.search(title)
            sev = SEV[e.group(0)] if e else cur_sev
            idm = re.match(r"^\s*\**\s*([RYGrygA-Z]{1,2}-?\d+[a-z]?)\b", title)
            if not sev and not idm:
                continue
            if not sev and idm:
                c = idm.group(1)[0].upper()
                sev = {"R": "red", "Y": "yellow", "G": "green"}.get(c)
            if not sev:
                continue
            block = "\n".join(lines[i:i + 40])
            findings.append({"id": (idm.group(1) if idm else title[:20]), "severity": sev, "line": i, "kind": "heading",
                             "text": title[:400],
                             "test_files": sorted(set(TEST_FILE_RX.findall(title + block))),
                             "test_fns": sorted(set(TEST_FN_RX.findall(title + block)))[:8],
                             "acs": sorted({f"AC-{a}" for a in AC_RX.findall(title + block[:800])})})
            continue
        b = re.match(r"^\s*[-*]\s*([🔴🟡🟢])\s*(.*)$", line)
        if b:
            findings.append({"id": f"b{i}", "severity": SEV[b.group(1)], "line": i, "kind": "bullet",
                             "text": b.group(2)[:400],
                             "test_files": sorted(set(TEST_FILE_RX.findall(line))),
                             "test_fns": sorted(set(TEST_FN_RX.findall(line))),
                             "acs": sorted({f"AC-{a}" for a in AC_RX.findall(line)})})
    # dedupe by identifier within a pass (table row + heading + inline mention of the same F3)
    merged: dict[str, dict] = {}
    out: list[dict] = []
    for f in findings:
        key = f["id"].upper() if re.match(r"^[A-Z]{1,2}-?\d+[a-z]?$", f["id"]) else f"{f['kind']}:{f['line']}"
        if key in merged:
            m = merged[key]
            for k in ("test_files", "test_fns", "acs"):
                m[k] = sorted(set(m[k]) | set(f[k]))
            if m["kind"] == "inline" and f["kind"] != "inline":
                m.update({"kind": f["kind"], "text": f["text"], "line": f["line"]})
            continue
        merged[key] = f
        out.append(f)
    return out


def parse_audit(path: Path) -> dict:
    text = read(path)
    passes = []
    for label, body in split_passes(text):
        f = parse_findings(body)
        cnt = collections.Counter(x["severity"] for x in f)
        passes.append({"label": label, "verdict": verdict_line(body), "findings": f,
                       "red": cnt["red"], "yellow": cnt["yellow"], "green": cnt["green"],
                       "chars": len(body)})
    # declared counts in prose, e.g. "1 🔴, 8 🟡, 6 🟢" or "🔴0 / 🟡2 / 🟢2"
    declared = {}
    for m in re.finditer(r"(\d+)\s*([🔴🟡🟢])|([🔴🟡🟢])\s*(\d+)|([🔴🟡🟢])\s*[a-z ]*\|\s*(\d+)\s*\|", text[:3000]):
        n = m.group(1) or m.group(4) or m.group(6)
        e = m.group(2) or m.group(3) or m.group(5)
        declared.setdefault(SEV[e], int(n))
    dialect = "table" if re.search(r"(?m)^\|\s*id\s*\|\s*severity", text) else (
        "check-sections" if re.search(r"(?m)^## Check \d", text) else (
            "stage-legacy" if re.search(r"(?m)^## Stage [A-C]", text) else "prose"))
    return {"path": str(path), "lines": text.count("\n") + 1, "dialect": dialect,
            "declared_counts": declared, "mentions_test_design_ref": "test-design.md" in text,
            "ran_tests": bool(re.search(r"\b(all \d+ tests were run|pytest|failed in|passed in|RED\b.*\bright reason)", text)),
            "passes": passes}


def parse_boundaries(path: Path) -> dict:
    text = read(path)
    rows = [l for l in text.splitlines() if l.startswith("|") and not re.match(r"^\|\s*-", l)]
    rows = [r for r in rows if "symbol" not in r.split("|")[1].lower()] if rows else []
    silent = sum(1 for r in rows if re.search(r"\|\s*—\s*\|", r))
    escalated = sum(1 for r in rows if re.search(r"question|Q\d", r, re.I))
    not_covered = sum(1 for r in rows if re.search(r"not covered|NOT covered", r))
    return {"path": str(path), "rows": len(rows), "spec_silent_rows": silent,
            "escalated_rows": escalated, "not_covered_rows": not_covered}


def parse_gates(path: Path) -> dict:
    text = read(path)
    rows = {}
    for m in re.finditer(r"(?m)^\|\s*([^|]+?)\s*\|\s*(PASS|FAIL|WARN|SKIP|ADVISORY)\s*\|\s*([^|]*)\|", text):
        rows[m.group(1).strip()] = {"result": m.group(2), "evidence": m.group(3).strip()[:200]}
    v = re.search(r"\*\*Verdict:\s*([^*]+)\*\*", text)
    return {"path": str(path), "verdict": v.group(1).strip() if v else "", "gates": rows,
            "waiver": bool(re.search(r"waiver", text, re.I)),
            "fails": [k for k, r in rows.items() if r["result"] == "FAIL"]}


def parse_log(path: Path) -> list[dict]:
    text = read(path)
    out = []
    for line in text.splitlines():
        if not line.startswith("|") or re.match(r"^\|\s*-", line) or "leaf_id" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7:
            continue
        out.append({"wave": cells[0], "shard": cells[1], "leaf": cells[2], "files": cells[3],
                    "delta": cells[4], "timestamp": cells[5], "status": cells[6][:120]})
    return out


def skill_observations(text: str) -> str:
    m = re.search(r"(?ms)^##+\s*Skill observation.*?(?=^## |\Z)", text)
    return m.group(0).strip()[:4000] if m else ""


# ---------------------------------------------------------------- cascade
def discover_cascades(swarm: Path) -> list[tuple[str, Path]]:
    out = []
    if (swarm / "briefs").is_dir():
        out.append(("_flat", swarm))
    for d in sorted(swarm.iterdir()):
        if d.is_dir() and (d / "briefs").is_dir():
            out.append((d.name, d))
    return out


def extract(repo_root: Path, swarm: Path, slug: str, cdir: Path, repo_name: str) -> dict:
    briefs_dir = cdir / "briefs"
    briefs = {}
    for bp in sorted(briefs_dir.glob("leaf-*.md")):
        if bp.name.endswith(".ASSUMPTIONS.md"):
            continue
        fm = frontmatter(read(bp))
        tests, impls = brief_paths(fm)
        briefs[bp.stem] = {
            "path": str(bp), "leaf": bp.stem, "spec_file": fm.get("spec_file", ""),
            "spec_lines": fm.get("spec_lines", ""), "wave": str(fm.get("wave", "1")),
            "shard": fm.get("shard", "default"), "test_files": tests, "impl_files": impls,
            "test_owned_by": fm.get("test_owned_by", ""), "impl_line_budget": fm.get("impl_line_budget", ""),
            "test_assertion_budget": fm.get("test_assertion_budget", ""),
            "has_assumptions": (briefs_dir / f"{bp.stem}.ASSUMPTIONS.md").exists(),
            "post_review_regression": "## Post-review regression" in read(bp),
        }
    spec_files = sorted({b["spec_file"] for b in briefs.values() if b["spec_file"]})
    specs = {}
    for sf in spec_files:
        sp = repo_root / sf
        specs[sf] = {"path": str(sp), "exists": sp.exists(), "acs": parse_spec(read(sp)) if sp.exists() else {}}

    # tests
    tests = {}
    for b in briefs.values():
        for t in b["test_files"]:
            if t in tests:
                continue
            tp = repo_root / t
            txt = read(tp)
            if not txt:  # fall back to backups/pending copies inside the cascade
                for alt in [cdir / "backups" / b["leaf"] / t, cdir / "pending" / b["leaf"] / t,
                            cdir / "pending" / b["shard"] / b["leaf"] / t]:
                    if alt.exists():
                        txt = read(alt)
                        tp = alt
                        break
            tests[t] = parse_test_file(tp, txt)
            tests[t]["leaf"] = b["leaf"]

    # impl presence
    impls = {}
    for b in briefs.values():
        for f in b["impl_files"]:
            ip = repo_root / f
            impls[f] = {"exists": ip.exists(), "lines": read(ip).count("\n") + 1 if ip.exists() else 0, "leaf": b["leaf"]}

    # audits (any depth under cdir/audits, plus legacy swarm/audits/wave-N/<slug>/ and swarm/wave-N.AUDIT.md)
    audit_paths = sorted(cdir.glob("audits/**/TEST-AUDIT.md")) + sorted(cdir.glob("audits/**/AUDIT.md"))
    audit_paths += sorted(cdir.glob("audits/**/auditor.md")) + sorted(cdir.glob("audits/**/POST-MORTEM.md"))
    audit_paths += sorted(swarm.glob(f"audits/wave-*/{slug}/TEST-AUDIT.md"))
    if slug == "_flat":
        audit_paths += sorted(swarm.glob("wave-*.AUDIT.md"))
    # root-level audits that name one of this cascade's test files (older layouts kept audits at .swarm/audits/)
    own_tests = {t for b in briefs.values() for t in b["test_files"]}
    if cdir != swarm:
        for p in sorted(swarm.glob("audits/**/*.md")):
            if p.name in ("TEST-AUDIT.md", "AUDIT.md", "auditor.md", "POST-MORTEM.md") and p not in audit_paths:
                txt = read(p)
                if any(t in txt or Path(t).name in txt for t in own_tests):
                    audit_paths.append(p)
    audits = [parse_audit(p) for p in audit_paths]
    for a, p in zip(audits, audit_paths):
        a["kind"] = "pre-spawn" if p.name == "TEST-AUDIT.md" else ("post-admission" if p.name in ("auditor.md", "POST-MORTEM.md") or "batch" in str(p) else "legacy-wave-audit")
    for a, p in zip(audits, audit_paths):
        bp = p.with_name("TEST-AUDIT-BRIEF.md") if p.name == "TEST-AUDIT.md" else p.with_name(p.name.replace("AUDIT.md", "AUDIT-BRIEF.md"))
        a["brief_lines"] = read(bp).count("\n") + 1 if bp.exists() else 0
        a["brief_dialect"] = ("inlined" if a["brief_lines"] > 200 else "path-list") if bp.exists() else "none"
        a["shard"] = p.parent.name
    boundaries = [parse_boundaries(p) for p in sorted(cdir.glob("audits/**/BOUNDARIES.md"))]
    gates = {p.stem.replace(".GATES", ""): parse_gates(p) for p in sorted(cdir.glob("audits/**/*.GATES.md"))}

    # log rows: per-cascade log, or root log filtered by shard==slug / any
    log_rows = []
    for lp in [cdir / "post-review-log.md", swarm / "post-review-log.md"]:
        if lp.exists():
            rows = parse_log(lp)
            if lp.parent == swarm and slug != "_flat":
                rows = [r for r in rows if r["shard"] == slug or r["shard"].startswith(slug)]
                if not rows:
                    # Agora style: shard column is shard-A etc.; match by leaf files instead
                    # test files are unique per cascade; impl files are shared across cascades
                    leaf_tests = {f for b in briefs.values() for f in b["test_files"]}
                    rows = [r for r in parse_log(lp) if any(f in r["files"] for f in leaf_tests)]
            log_rows = rows
            break

    backups = {}
    for bd in sorted((cdir / "backups").glob("leaf-*")) if (cdir / "backups").is_dir() else []:
        files = [str(p.relative_to(bd)) for p in bd.rglob("*") if p.is_file()]
        backups[bd.name] = {"files": len(files), "absent_markers": sum(1 for f in files if f.endswith(".ABSENT"))}

    obs = {}
    for p in list(cdir.glob("wave-*.SWEEP.md")) + list(cdir.glob("REPORT.md")) + list(cdir.glob("STATE.md")):
        o = skill_observations(read(p))
        if o:
            obs[str(p)] = o

    # AC join
    ac_index: dict[str, dict] = {}
    for sf, s in specs.items():
        for ac, meta in s["acs"].items():
            ac_index[ac] = {"spec": sf, **meta, "tests": [], "findings": [], "leaves": []}
    for t, td in tests.items():
        for ac in td["spec_acs"]:
            if ac in ac_index:
                ac_index[ac]["tests"].append(t)
                if td["leaf"] not in ac_index[ac]["leaves"]:
                    ac_index[ac]["leaves"].append(td["leaf"])
        for fn in td["tests"]:
            for ac in fn["acs_mentioned"]:
                if ac in ac_index and t not in ac_index[ac]["tests"]:
                    ac_index[ac]["tests"].append(t)
    for a in audits:
        for ps in a["passes"]:
            for f in ps["findings"]:
                for ac in f["acs"]:
                    if ac in ac_index:
                        ac_index[ac]["findings"].append({"audit": a["path"], "pass": ps["label"], "id": f["id"], "severity": f["severity"]})
    # leaf outcome
    outcomes = {}
    for leaf, b in briefs.items():
        rows = [r for r in log_rows if r["leaf"] == leaf and (r["wave"] == b["wave"] or slug == "_flat")]
        outcomes[leaf] = {
            "log_rows": rows, "admitted": any(r["status"].startswith("clean") for r in rows),
            "reverted": any("REVERT" in r["delta"] or "REVERT" in r["status"] for r in rows),
            "gates_verdict": gates.get(leaf, {}).get("verdict", ""), "gate_fails": gates.get(leaf, {}).get("fails", []),
            "gate_waiver": gates.get(leaf, {}).get("waiver", False),
            "backup": backups.get(leaf), "impl_exists": all(impls[f]["exists"] for f in b["impl_files"]) if b["impl_files"] else None,
        }

    n_find = sum(len(ps["findings"]) for a in audits for ps in a["passes"])
    total_acs = len(ac_index)
    covered = sum(1 for ac in ac_index.values() if ac["tests"])
    summary = {
        "leaves": len(briefs), "waves": sorted({b["wave"] for b in briefs.values()}),
        "shards": sorted({b["shard"] for b in briefs.values()}),
        "spec_acs": total_acs, "acs_with_tests": covered, "acs_without_tests": [k for k, v in ac_index.items() if not v["tests"]],
        "test_files": len(tests), "test_files_found": sum(1 for t in tests.values() if t["exists"]),
        "test_fns": sum(len(t["tests"]) for t in tests.values()), "assertions": sum(t["assertions"] or 0 for t in tests.values()),
        "audits": len(audits), "audit_passes": sum(len(a["passes"]) for a in audits), "findings": n_find,
        "findings_by_sev": dict(collections.Counter(f["severity"] for a in audits for ps in a["passes"] for f in ps["findings"])),
        "audit_dialects": sorted({a["dialect"] for a in audits}), "audit_kinds": dict(collections.Counter(a["kind"] for a in audits)), "brief_dialects": sorted({a["brief_dialect"] for a in audits}),
        "boundaries_rows": sum(b["rows"] for b in boundaries), "gates_files": len(gates),
        "gate_waivers": sum(1 for g in gates.values() if g["waiver"]), "gate_fail_rows": sum(len(g["fails"]) for g in gates.values()),
        "log_rows": len(log_rows), "admitted": sum(1 for o in outcomes.values() if o["admitted"]),
        "reverted": sum(1 for o in outcomes.values() if o["reverted"]),
        "delta_zero_rows": sum(1 for r in log_rows if re.match(r"^\+0\b", r["delta"])),
        "has_skill_observations": bool(obs),
        "era": ("audited" if audits else "unaudited"),
    }
    return {"repo": repo_name, "cascade": slug, "cascade_dir": str(cdir), "repo_root": str(repo_root),
            "extracted_at": dt.datetime.now().isoformat(timespec="seconds"),
            "summary": summary, "specs": specs, "briefs": briefs, "tests": tests, "impls": impls,
            "audits": audits, "boundaries": boundaries, "gates": gates, "log_rows": log_rows,
            "backups": backups, "ac_index": ac_index, "outcomes": outcomes, "skill_observations": obs}


def render_md(L: dict) -> str:
    s = L["summary"]
    out = [f"# Ledger — {L['repo']} / {L['cascade']}", "",
           f"Extracted {L['extracted_at']} from `{L['cascade_dir']}` (repo root `{L['repo_root']}`).", "",
           "## Summary", "", "| key | value |", "|---|---|"]
    for k, v in s.items():
        out.append(f"| {k} | {v} |")
    out += ["", "## Leaves", "", "| leaf | wave | shard | impl_files | test_files | admitted | reverted | gates | fails | waiver |", "|---|---|---|---|---|---|---|---|---|---|"]
    for leaf, b in L["briefs"].items():
        o = L["outcomes"][leaf]
        out.append(f"| {leaf} | {b['wave']} | {b['shard']} | {', '.join(b['impl_files'])} | {', '.join(b['test_files'])} | {o['admitted']} | {o['reverted']} | {o['gates_verdict']} | {', '.join(o['gate_fails'])} | {o['gate_waiver']} |")
    out += ["", "## ACs", "", "| AC | spec lines | tests | findings | text |", "|---|---|---|---|---|"]
    for ac, m in L["ac_index"].items():
        fs = " ".join(f"{f['severity'][0].upper()}:{f['id']}" for f in m["findings"])
        out.append(f"| {ac} | {m['line_start']}-{m['line_end']} | {', '.join(m['tests'])} | {fs} | {m['text'][:140].replace('|', '/')} |")
    out += ["", "## Audits", ""]
    for a in L["audits"]:
        out.append(f"### `{a['path']}` — dialect {a['dialect']}, brief {a['brief_dialect']} ({a['brief_lines']} lines), ran_tests={a['ran_tests']}")
        for ps in a["passes"]:
            out.append(f"- **{ps['label']}** — {ps['red']}🔴 {ps['yellow']}🟡 {ps['green']}🟢 — verdict: {ps['verdict']}")
            for f in ps["findings"]:
                out.append(f"  - {f['severity']} `{f['id']}` L{f['line']} {', '.join(f['acs'])} {', '.join(f['test_fns'][:3])} — {f['text'][:160].replace('|', '/')}")
        out.append("")
    if L["skill_observations"]:
        out += ["## Skill observations (verbatim)", ""]
        for p, o in L["skill_observations"].items():
            out += [f"### `{p}`", "", o, ""]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--repo-name", required=True)
    ap.add_argument("--swarm-dir", default=None, help="defaults to <repo-root>/.swarm")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--out", default=str(HERE / "ledgers"))
    args = ap.parse_args()
    root = Path(args.repo_root).resolve()
    swarm = Path(args.swarm_dir).resolve() if args.swarm_dir else root / ".swarm"
    if not swarm.is_dir():
        print("no .swarm at", swarm, file=sys.stderr)
        return 1
    out_dir = Path(args.out) / args.repo_name
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for slug, cdir in discover_cascades(swarm):
        if args.only and slug not in args.only:
            continue
        L = extract(root, swarm, slug, cdir, args.repo_name)
        (out_dir / f"{slug}.json").write_text(json.dumps(L, indent=1, default=str))
        (out_dir / f"{slug}.md").write_text(render_md(L))
        s = L["summary"]
        print(f"{args.repo_name}/{slug}: leaves={s['leaves']} acs={s['spec_acs']} tests={s['test_files_found']}/{s['test_files']} "
              f"audits={s['audits']} findings={s['findings']} {s['findings_by_sev']} log={s['log_rows']} admitted={s['admitted']} reverted={s['reverted']}")
        n += 1
    print(f"{n} ledgers → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
