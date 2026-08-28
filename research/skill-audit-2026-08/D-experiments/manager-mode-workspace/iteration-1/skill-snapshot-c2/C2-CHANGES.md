# C2 "context-diet" skill variant — what differs from C0 (repo HEAD 0be343c)

Models unchanged from C0 (overlord Opus 5, writer/auditor Opus 5, leaves/fixer Sonnet 4.6). Only prefix-side mechanics change; no gate, check, or judgment step is altered.

| opt | edit | finding it targets |
|---|---|---|
| 3 | `swarm-shared/scripts/build_audit_brief.py` (new); 3.4.1 builds TEST-AUDIT-BRIEF.md by script, overlord adds only §7/§8 by hand and never reads the brief back | F4 — overlord read+wrote 1.8–2.8k-line briefs at Opus output rate |
| 3 | 3.2 / 6.5 / 6.5a: surface summary line + exit code; render rows verbatim only on non-zero; never read GATES.md back on a clean pass | F6 — verbatim rendering accumulates in prefix |
| 5 | 2.6 writer prompt: spec/contract/brief excerpts inlined; impl read by `grep -n` + range, whole-file only <300 lines | F2 — fresh tokens = whole-file reads |
| 5 | 4.2 leaf prompt: brief + spec_lines excerpt inlined; "do not open the spec"; sibling-assumption check is one `grep -il` (brief-template.md updated to match) | F5 — 4–5 read turns before first edit |
| 2 | Return caps on every spawn: leaf 12 lines + `.swarm/<slug>/reports/leaf-NN.md`; writer 10; auditor counts + one line per 🔴/🟡; fixer 5; new "Return-message discipline" section | task-notifications of 25–40k chars each in overlord prefix |
| 1 | 5.1 commits in one shell loop; 5.2 sweep delegated to a Sonnet 4.6 **sweep-runner** (returns ≤15 lines); Phase 6 per-leaf **admission-runner** (Sonnet 4.6, sequential, runs run_gates + admit, never `--confirm-same`/`revert`, returns ≤10 lines); both added to Model defaults + phases-at-a-glance | F1/OVERLORD.md — prefix growth is accumulated tool output; runners are context boundaries |

Verification: full `tests/` suite (100) green against this snapshot (scratch tree with `skills/` → snapshot). `build_audit_brief.py` has no unit tests yet — smoke-run only; add before landing in repo.
