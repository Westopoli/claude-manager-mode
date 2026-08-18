---
name: manager-mode-hardcore
description: Stricter sibling of /manager-mode for delicate, high-consequence codebases where an extra verification pass is worth the token cost — production data pipelines, payment/auth code, migrations, anything where a wrong admit is expensive to unwind. It retains the complete normal Manager Mode builder, sweep, and G1–G10 admission flow (G8's mutation, G9's complexity, and G10's algorithmic-scale findings all block here, not just advisory), then doubles the pre-impl test audit — two independent fresh-context test-auditors per shard, adjudicated by a third — before any leaf spawns. Use when the user says things like "this is delicate, use hardcore mode", "I want a stricter cascade for this", "run manager-mode-hardcore", "this touches production data, double-check everything before it lands", or is working somewhere a silent bad admit would be costly to discover later. Do not use for ordinary feature work — use /manager-mode instead.
---

# /manager-mode-hardcore — doubled pre-impl test audit

Hardcore is `/manager-mode` with one deliberately narrow replacement: its Phase 3.4 test-quality audit uses two independent auditors plus a fresh adjudicating reviewer per shard, instead of base's single auditor. It does **not** add any post-admission review and does not remove any normal safeguard — hardcore's extra rigor is spent entirely on catching a bad test before any leaf ever implements against it, which is strictly cheaper than catching it after N leaves have already run.

Theory, brief template, and config schema use the same shared assets as `/manager-mode`. Resolve `SWARM_SHARED_DIR` with `/manager-mode`'s Shared asset resolver, then use `$SWARM_SHARED_DIR/references/playbook.md`, `brief-template.md`, and `config.md`. Nothing here duplicates those; Hardcore only changes Phase 3.4 and how many roles participate in it.

Read `/manager-mode` first and execute its Phases 0–7 unchanged EXCEPT Phase 3.4, which this file replaces: preflight, lite-discovery, the blocking Phase 1.5 plan-consistency pass, shard-test-writer per-leaf RED tests, the rest of Phase 3's invariant audit (non-overlap, no-design, no-contradiction, sizing, shard-sizing, spec-link, codebase-preconditions), dependency map + consolidation pass + 16-leaf sizing limit, parent ownership, the Phase 4.0 wave baseline and per-leaf sandboxes, parallel builder dispatch, sandbox harvest + sweep, questions/proposals, bypass detection and its per-leaf gate evidence, G1–G10, file-match, umbrella pre/post checks, admit-or-revert, apex testing, and reporting.

Two differences within that unchanged flow. First, Phase 6.5's runner takes `--strict`:

```bash
python "$SWARM_SHARED_DIR/scripts/run_gates.py" --leaf leaf-NN --cascade <cascade-slug> --strict
```

That propagates to G8 (`test_quality_gate.py`), G9 (`complexity_gate.py`) and G10 (`scale_gate.py`), so a mutation finding, a complexity/nesting finding, or a scale-antipattern finding blocks admission the same as a reachability finding — hardcore's whole premise is that a wrong admit is expensive, so a heuristic these lite gates happened to catch is worth stopping for even if it might occasionally be an unlucky pick. It also promotes a missing `BOUNDARIES.md` from advisory to blocking: a shard whose boundary sweep left no record is a shard whose edges nobody checked, and that is precisely the class of gap hardcore exists to refuse.

## Phase 3.4 (hardcore) — Doubled test audit, then adjudicate

Runs where base `/manager-mode`'s single-auditor 3.4 would run: once a shard's tests exist (2.6) and pass the invariant audit (3.0–3.3), before any leaf spawns. Records live at:

```
.swarm/<cascade-slug>/audits/wave-<wave>/<shard-or-default>/
```

Records live under the cascade's own directory, per `/manager-mode`'s canonical layout. The overlord writes `TEST-AUDIT-BRIEF.md` exactly as base 3.4.1 describes (umbrella test, shard's stated goal + brief set, tests under audit, composition-relevant contract excerpts, sibling-shard awareness, anything already litigated).

### 3.4.1 (hardcore) Two independent test-auditors

Spawn two fresh-context auditors per shard in parallel, and dispatch shards in parallel (shards already don't share footprint). Neither auditor may see the other's prompt, report, reasoning, or findings. Use `caveman:cavecrew-reviewer` where available; otherwise a fresh `general-purpose` reviewer with the same adversarial instruction.

Both receive only `TEST-AUDIT-BRIEF.md` and the tests under audit. They never edit files. Posture and report requirements are identical to base 3.4.2's three checks (goal fidelity, umbrella alignment, test quality), with the same evidence requirement: every finding needs a quote from the test, the umbrella, or the spec.

Persist reports as `test-auditor-1.md` and `test-auditor-2.md` in the shard's audit directory. Fresh context and disk-only reports are mandatory: the second auditor must not inherit the first's framing.

If either report is missing, malformed, or arrives after the configured wait/retry limit, do not spawn the adjudicator and do not report the shard's tests as audit-clean. Persist `AUDIT-FAILURE.md` with the missing role and wait/retry evidence; escalate.

### 3.4.2 (hardcore) Adjudication

Only after both reports exist, spawn a third fresh-context reviewer. Give it `TEST-AUDIT-BRIEF.md`, both reports, the tests under audit, and the umbrella/spec/contract excerpts. It independently evaluates **every** claim from both auditors — does not trust either just because they agree.

For every claim it records `CONFIRMED`, `DENIED`, or `UNVERIFIED`, plus its own source/spec citation and rationale. It does not implement anything — this is still pre-impl, there is no code to repair yet, only the test. If any claim resolves `CONFIRMED` at 🔴/🟡 severity, the shard's tests are **not** audit-clean: a fresh spawn revises the flagged test(s) — base 3.4.3's sizing applies, so a verbatim-quoted one-line fix may be applied by the overlord and anything larger goes to a Sonnet test-fixer — confirms RED again, and 3.4.1–3.4.2 re-run in full — both auditors again, not just a re-check of the fixed line, since a fix can introduce a new problem the first pass didn't have a reason to look for.

The adjudicator writes its verdict to `TEST-AUDIT-ADJUDICATION.md` in the shard's audit directory.

### 3.4.3 (hardcore) Reporting

The overlord aggregates the shard's audit directory into `.swarm/audits/wave-<wave>/<shard-or-default>/PRE-IMPL-AUDIT-SUMMARY.md`, containing both auditors' report paths, the adjudicator's verdict, any revise-and-re-audit cycles and their count, and final audit-clean status per shard. Update the normal Phase 7 report with those same counts.

No audit record belongs in `post-review-log.md`; it remains the append-only normal-admission history. Shards remain file-disjoint and retain separate wave snapshots and sweeps. No phase may bypass the base skill's existing gates.
