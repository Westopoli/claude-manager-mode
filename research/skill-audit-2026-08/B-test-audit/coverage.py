#!/usr/bin/env python3
"""Aggregate the per-cascade ledgers into flat CSVs for analysis.

  out/cascades.csv     one row per cascade (era, counts, dialects, outcomes)
  out/ac_coverage.csv  one row per (cascade, AC): tests claiming it, findings, leaf outcome
  out/findings.csv     one row per audit finding (severity, kind, pass, AC refs, test refs)
  out/audits.csv       one row per audit file (dialect, brief dialect/lines, declared vs parsed counts)
  COVERAGE.md          human summary tables

Era rule (from research/manager-mode-improvement + Agora runs/manager-mode-*-auditor/INDEX.md):
  pre-spawn TEST-AUDIT.md present  -> "post-auditor" (skill >= 6cb0cea, 2026-08-09)
  only post-admission auditor.md   -> "post-admission-audit" (Phase 8 era, removed later)
  no audit artefacts                -> "pre-auditor"
"""
from __future__ import annotations

import csv
import glob
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)


def era_of(L: dict) -> str:
    kinds = L["summary"].get("audit_kinds", {})
    if kinds.get("pre-spawn"):
        return "post-auditor"
    if kinds.get("post-admission") or kinds.get("legacy-wave-audit"):
        return "post-admission-audit"
    return "pre-auditor"


def main() -> int:
    ledgers = [json.load(open(p)) for p in sorted(glob.glob(str(HERE / "ledgers" / "*" / "*.json")))]
    cas, acs, fins, auds = [], [], [], []
    for L in ledgers:
        s = L["summary"]
        era = era_of(L)
        declared = {"red": 0, "yellow": 0, "green": 0}
        parsed = {"red": 0, "yellow": 0, "green": 0}
        for a in L["audits"]:
            d = a.get("declared_counts") or {}
            p1 = a["passes"][0] if a["passes"] else {}
            for k in declared:
                declared[k] += d.get(k, p1.get(k, 0))
                parsed[k] += p1.get(k, 0)
            auds.append({
                "repo": L["repo"], "cascade": L["cascade"], "era": era, "kind": a.get("kind", ""),
                "shard": a.get("shard", ""), "dialect": a["dialect"], "brief_dialect": a["brief_dialect"],
                "brief_lines": a["brief_lines"], "audit_lines": a["lines"], "passes": len(a["passes"]),
                "ran_tests": a["ran_tests"], "cites_test_design": a["mentions_test_design_ref"],
                "declared_red": d.get("red", ""), "declared_yellow": d.get("yellow", ""), "declared_green": d.get("green", ""),
                "parsed_red": p1.get("red", 0), "parsed_yellow": p1.get("yellow", 0), "parsed_green": p1.get("green", 0),
                "reaudit_red": sum(ps["red"] for ps in a["passes"][1:]), "reaudit_yellow": sum(ps["yellow"] for ps in a["passes"][1:]),
                "final_verdict": (a["passes"][-1]["verdict"] if a["passes"] else "")[:80],
                "path": a["path"],
            })
            for ps in a["passes"]:
                for f in ps["findings"]:
                    fins.append({"repo": L["repo"], "cascade": L["cascade"], "era": era, "audit_kind": a.get("kind", ""),
                                 "shard": a.get("shard", ""), "pass": ps["label"][:30], "id": f["id"], "severity": f["severity"],
                                 "kind": f["kind"], "acs": " ".join(f["acs"]), "test_files": " ".join(f["test_files"]),
                                 "test_fns": " ".join(f["test_fns"][:4]), "text": f["text"][:200].replace("\n", " ")})
        leaves = L["briefs"]
        cas.append({
            "repo": L["repo"], "cascade": L["cascade"], "era": era, "leaves": s["leaves"],
            "waves": len(s["waves"]), "shards": len(s["shards"]), "spec_acs": s["spec_acs"],
            "acs_with_tests": s["acs_with_tests"], "acs_without_tests": len(s["acs_without_tests"]),
            "test_files": s["test_files"], "test_files_found": s["test_files_found"], "test_fns": s["test_fns"],
            "assertions": s["assertions"],
            "test_owned_by_parent": sum(1 for b in leaves.values() if b["test_owned_by"] == "parent"),
            "audits": s["audits"], "audit_passes": s["audit_passes"],
            "declared_red": declared["red"], "declared_yellow": declared["yellow"], "declared_green": declared["green"],
            "parsed_red": parsed["red"], "parsed_yellow": parsed["yellow"], "parsed_green": parsed["green"],
            "audit_dialects": "+".join(s["audit_dialects"]), "brief_dialects": "+".join(s["brief_dialects"]),
            "boundaries_rows": s["boundaries_rows"], "gates_files": s["gates_files"], "gate_waivers": s["gate_waivers"],
            "gate_fail_rows": s["gate_fail_rows"], "log_rows": s["log_rows"], "admitted": s["admitted"],
            "reverted": s["reverted"], "delta_zero_rows": s["delta_zero_rows"],
            "post_review_regressions": sum(1 for b in leaves.values() if b["post_review_regression"]),
            "impl_exists": sum(1 for o in L["outcomes"].values() if o["impl_exists"]),
            "skill_observations": s["has_skill_observations"],
        })
        for ac, m in L["ac_index"].items():
            leaf_out = [L["outcomes"][l] for l in m["leaves"] if l in L["outcomes"]]
            acs.append({"repo": L["repo"], "cascade": L["cascade"], "era": era, "ac": ac, "section": m.get("section", "")[:60],
                        "spec_lines": f"{m['line_start']}-{m['line_end']}", "n_tests": len(m["tests"]),
                        "tests": " ".join(m["tests"]), "leaves": " ".join(m["leaves"]),
                        "n_findings": len(m["findings"]),
                        "findings_red": sum(1 for f in m["findings"] if f["severity"] == "red"),
                        "findings_yellow": sum(1 for f in m["findings"] if f["severity"] == "yellow"),
                        "leaf_admitted": any(o["admitted"] for o in leaf_out), "leaf_reverted": any(o["reverted"] for o in leaf_out),
                        "text": m["text"][:200].replace("|", "/")})

    def dump(name, rows):
        if not rows:
            return
        with open(OUT / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    dump("cascades.csv", cas)
    dump("ac_coverage.csv", acs)
    dump("findings.csv", fins)
    dump("audits.csv", auds)

    # summary
    def by(rows, key):
        g = {}
        for r in rows:
            g.setdefault(r[key], []).append(r)
        return g

    lines = ["# Coverage summary", "", f"{len(cas)} cascades, {len(acs)} AC rows, {len(fins)} findings, {len(auds)} audit files.", "",
             "## Cascades by era", "", "| era | cascades | leaves | spec ACs | ACs w/ tests | test fns | findings (declared R/Y/G) | admitted | reverted | log Δ=0 | gate waivers |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for era, rs in sorted(by(cas, "era").items()):
        lines.append(f"| {era} | {len(rs)} | {sum(r['leaves'] for r in rs)} | {sum(r['spec_acs'] for r in rs)} | {sum(r['acs_with_tests'] for r in rs)} | {sum(r['test_fns'] for r in rs)} | "
                     f"{sum(r['declared_red'] for r in rs)}/{sum(r['declared_yellow'] for r in rs)}/{sum(r['declared_green'] for r in rs)} | {sum(r['admitted'] for r in rs)} | {sum(r['reverted'] for r in rs)} | {sum(r['delta_zero_rows'] for r in rs)} | {sum(r['gate_waivers'] for r in rs)} |")
    lines += ["", "## Audits by brief dialect", "", "| brief dialect | audits | median brief lines | declared R/Y/G | median audit lines | ran tests |", "|---|---|---|---|---|---|"]
    for bd, rs in sorted(by(auds, "brief_dialect").items()):
        bl = sorted(r["brief_lines"] for r in rs)
        al = sorted(r["audit_lines"] for r in rs)
        red = sum(int(r["declared_red"] or r["parsed_red"]) for r in rs)
        yel = sum(int(r["declared_yellow"] or r["parsed_yellow"]) for r in rs)
        grn = sum(int(r["declared_green"] or r["parsed_green"]) for r in rs)
        lines.append(f"| {bd} | {len(rs)} | {bl[len(bl)//2]} | {red}/{yel}/{grn} | {al[len(al)//2]} | {sum(1 for r in rs if r['ran_tests'])} |")
    lines += ["", "## Audits by dialect", "", "| dialect | audits | declared R/Y/G |", "|---|---|---|"]
    for d, rs in sorted(by(auds, "dialect").items()):
        lines.append(f"| {d} | {len(rs)} | {sum(int(r['declared_red'] or r['parsed_red']) for r in rs)}/{sum(int(r['declared_yellow'] or r['parsed_yellow']) for r in rs)}/{sum(int(r['declared_green'] or r['parsed_green']) for r in rs)} |")
    lines += ["", "## Per cascade", "", "| repo | cascade | era | leaves | ACs | ACs w/ tests | test fns | audits | R/Y/G | admitted | reverted | Δ=0 | waivers | impl exists |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in cas:
        lines.append(f"| {r['repo']} | {r['cascade']} | {r['era']} | {r['leaves']} | {r['spec_acs']} | {r['acs_with_tests']} | {r['test_fns']} | {r['audits']} | {r['declared_red']}/{r['declared_yellow']}/{r['declared_green']} | {r['admitted']} | {r['reverted']} | {r['delta_zero_rows']} | {r['gate_waivers']} | {r['impl_exists']}/{r['leaves']} |")
    acs_zero = [r for r in acs if r["n_tests"] == 0]
    lines += ["", f"## ACs with zero tests claiming them: {len(acs_zero)} / {len(acs)}", ""]
    for r in acs_zero[:80]:
        lines.append(f"- {r['repo']}/{r['cascade']} {r['ac']} (L{r['spec_lines']}): {r['text'][:110]}")
    (HERE / "COVERAGE.md").write_text("\n".join(lines) + "\n")
    print(f"{len(cas)} cascades → {OUT}; COVERAGE.md written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
