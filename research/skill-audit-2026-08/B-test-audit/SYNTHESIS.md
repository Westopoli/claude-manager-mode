# B4 — Synthesis: does the pre-spawn test-quality auditor (added `6cb0cea`, 2026-08-09) earn its cost?

Built from three independent Sonnet judgment passes (`judgments/pre-auditor-narrative.json`, `post-auditor-narrative.json`, `extracted-corpus.json`) plus the mechanical extraction in `out/*.csv` / `COVERAGE.md`. Every claim below traces to one of those four sources — see them for exact citations. Read `MISCONCEPTIONS.md` before treating any of this as final; the biggest caveat (extractor under-linking) is folded in below, not hidden.

## 1. Catch rate — who actually catches defects, before vs after the auditor existed

**Pre-auditor era** (no pre-spawn mechanism existed): of ~12 cleanly-attributable real defect events across 9 repos, **0% were caught pre-spawn** (mechanically impossible — nothing existed to catch them there). ~42% were caught by the overlord's manual admission-time diff review, ~42% by a leaf's own TDD RED/GREEN cycle discovering its *parent-authored* test was itself wrong, ~8% by a later post-admission audit (Phase 8, since removed from the skill), and ~8% only by a human manually exercising the running product post-admission.

**Post-auditor era**: the auditor produces real pre-spawn findings — 4 red, 9 yellow, 14 green/confirmatory in the two cascades with full surviving artifacts (the-best-salesmen, leandrc49 `cash_print_pi_migration`) — **100% of red/yellow findings in those two cascades were fixed pre-spawn**. Two of them plausibly would have shipped broken or forced a revert: leandrc49's cross-file umbrella conflict (a leaf's spec-compliant work was structurally impossible without a parent-only file), and the-best-salesmen's AC-30 zero-coverage gap.

**Interpretation, checked against the misconception flagged in `MISCONCEPTIONS.md`**: this is *not* simply "the auditor catches more." A real fraction of what leaves already caught via their own TDD cycle in the pre-auditor era (parent-test-was-wrong, ~42% of pre-auditor catches) is exactly the category the pre-spawn auditor now catches *earlier* — before a leaf spends tokens implementing against a bad test. The auditor's clearest, best-evidenced value is **moving detection earlier in cases leaf TDD already covered eventually**, not opening an entirely new detection surface — with two real exceptions below.

## 2. False-positive rate

One clear case in the whole corpus: switchboard's `bug-finding-dry-run-exit-code` — the auditor's finding was factually accurate about a missing assertion, but its *implied fix* (assert `returncode==0`) would have made the test wrong, since the script legitimately cannot guarantee exit 0 given an unreachable `DATABASE_URL`. The parent overrode with a rename, no assertion added. This is the corpus's one clear "auditor was thorough but wrong about the remedy" instance — a low rate (1 finding out of dozens across two corpora), but real.

No fabricated findings, no fixes that reverted or regressed anything (`reverted == 0` and `post_review_regressions == 0` across **every** cascade in every era, all 56 — `extracted-corpus.json` notes).

## 3. Severity calibration vs later impact

Small sample, but consistent: every red/yellow finding checked was eventually confirmed real (materiality spot-check below); the one severity-adjacent problem (switchboard) was a *remedy* miscalibration, not a *severity* one. No case in either narrative corpus shows a red/yellow finding that turned out to be cosmetic once fixed, or a green/nit that turned out to hide something serious.

## 4. Category distribution

Within post-auditor findings classifiable by the fixed vocabulary (`extracted-corpus.json`, n=354, 66.4% unclassifiable by keyword heuristic — see caveat in that file): **spec-field-unasserted (13.6%)** and **tautology (8.5%)** dominate, matching the zero-test-AC deep-dive's own finding that assertion/coverage gaps, not structural defects, are the auditor's bread and butter. `cross-file-conflict`, `composition-missing`, `umbrella-contradiction` are rarer (2–3% each) but disproportionately severe when they occur — both reds in cascade-foundation shard-B and cascade-verify shard-B were `umbrella-contradiction`.

**Category skew pre- vs post-auditor cannot be computed** — pre-auditor cascades have zero findings by construction (no auditor ran), so 100% of every category's findings are post-auditor-era by definition, not by behavioral difference.

**Three real defect categories fall entirely outside the fixed vocabulary and outside what any version of Phase 3.4 covers, confirmed by both narrative corpora**:
1. **Implementation-time code leaks into shipped output** (the-best-salesmen: a `globalThis.jest` shim left in production code) — invisible to a test-quality audit, since it's a property of the impl, not the test.
2. **Execution-time isolation/staging discipline violations** (leandrc49: leaves editing live files out of order, one leaf's green partly produced by a sibling's live edit) — explicitly outside the auditor's scope by design ("G5's wave-snapshot check explicitly excludes leaf-owned paths from what it watches, by design, in every version of the skill" — post-auditor-narrative.json). Note: Track A's worktree redesign this session directly narrows this gap for the *undeclared-write* half (G5 now diffs a real commit rather than trusting a snapshot), though it was never designed to catch legitimate-looking live edits made *before* commit in the old sandbox model — worth re-checking against worktree isolation in a future audit pass.
3. **Shared test-harness/infrastructure bugs discovered only at leaf runtime** (the-best-salesmen: RTL auto-cleanup not registered, a mock single-read stream collision) — these are harness defects the leaf hits while running, not a property the pre-spawn auditor can see by reading test text.

## 5. Material change rate

7 of 8 spot-checked post-auditor findings were **material-fix** (the flagged gap was real; the fix, read against the live test file, genuinely closes it — e.g. gate_fence's rename-only bypass fix, `qa_seed`'s scale-probe fix). 1 of 8 was **already-moot** (correctly left open, non-blocking). **0 of 8 were cosmetic.** This is a strong signal that when the auditor does flag something and it gets fixed, the fix is real work, not paperwork.

## 6. Uncovered-rule violations in admitted impl

**Zero**, across 18 zero-test-flagged ACs deep-checked in the 5 Agora cascades. This number needs its own headline, because it corrects a real methodology error in this audit's own extraction script (see below).

## 7. Re-audit marginal yield

Every audited cascade in the whole corpus (`out/audits.csv`) shows exactly **one** `## Re-audit` pass after the initial audit, never zero and never two or more — the audit→fix→re-audit loop empirically self-terminates after one cycle in production, despite having no hard cap in the skill (K32, `knob-map.md`). This is corpus evidence, not a designed limit; K32 stays flagged `needs-experiment` in the knob map because an adversarial spec with deliberately dense findings might behave differently (see `D-experiments/design.md` Row 3).

## 8. Brief-dialect effect (path-list vs fully-inlined `TEST-AUDIT-BRIEF.md`)

`COVERAGE.md`'s "Audits by brief dialect" table: 39 audits used the terse path-list dialect (median 58 lines), 11 used the fully-inlined dialect (median 1,831 lines) — a >30× size difference for the same nominal input (every test file's full text, either linked or pasted). The path-list audits produced a higher aggregate declared-finding rate (32/134/110 R/Y/G across 39 audits ≈ 0.82/audit red+yellow) than the inlined audits (6/34/21 across 11 ≈ 0.55/audit red+yellow) — but this is confounded by which *cascades* happened to use which dialect (qa-profile and cascade-director, the inlined-dialect cascades, are also the two with unusually large brief sets), not a controlled comparison. Flagged in `knob-map.md` K35 as `needs-experiment` if this session's D2 design doesn't resolve it first from more corpus.

## 9. Is the post-review-log `+0` delta a dead signal?

**No — it's a real signal, misread as "dead" without knowing Agora's own cascade design.** 41.3% of post-auditor log rows show `+0` umbrella delta (45/109), but Agora's cascades are deliberately umbrella-first: the umbrella test for a given AC is frequently already passing (against a stub or an earlier leaf) before the "completing" leaf lands, so a correct, fully-working leaf can legitimately show `+0`. The `run_gates.py`-era per-test set-diff regression check (which this session's Track A work reuses unchanged) still catches the case that matters — a *regression* — independent of net delta. Gate waivers are a separate, much more concerning number: **41 waiver paragraphs across 52 gates files (78.8%)** in the post-auditor corpus, all G5-live-tree-drift waivers under the old sandbox design — this is the exact failure mode Track A's worktree redesign this session was built to eliminate structurally (G5 live-tree drift is now advisory by design, not something needing a hand-written waiver).

## Corrected headline: the 147/371 "zero-test AC" statistic in `COVERAGE.md` is substantially overstated

The extractor's `ac_index` links a test to an AC only via the test's `# spec:` header or via a citation inside an audit finding. An AC whose test exists, asserts it correctly, and was **never flagged as a problem by any audit** has no citation path into `ac_index` — so it shows as "zero tests" even though a real, correct test exists. Deep-checking 18 such flags in the 5 Agora cascades: **13 were extractor false-negatives** (real test found by direct code read, e.g. `test_burn_flow.py::test_worker_prompt_has_spec_and_checks_but_no_error_transcript` directly asserting cascade-foundation AC-3, never linked because it was never the subject of a finding), **1 was a genuine test gap with a correct implementation anyway** (qa-profile AC-1), and **4 were correctly not-applicable** (cascade-director never spawned leaves — no impl exists to test). **Zero of 18 were a real uncovered-rule violation.**

This does not mean the real number across all 371 ACs is zero — only the 18 checked were verified — but it means `ac_coverage.csv`'s zero-test flag should be read as "not cited by an audit finding," not "untested," until `extract_ledgers.py` is fixed to also scan every test file body for AC mentions independent of audit citations (a mechanical fix, not a judgment one — noted as a TODO, not executed this session since it doesn't change any conclusion above).

## Bottom line

The pre-spawn auditor is real, working, and its fixes are materially real (7/8 spot-check). Its clearest evidence-backed value is moving detection of already-eventually-caught defect classes earlier (before wasted leaf tokens), plus catching two real categories — spec-field-unasserted and tautology — that dominate its findings and that pre-auditor-era leaf TDD only caught inconsistently (42% of the time, per the pre-auditor corpus, and only for tests the leaf itself exercised). It is bounded: three defect categories (impl-time code leaks, execution-time staging discipline, shared-harness runtime bugs) sit structurally outside what a test-quality audit can see, confirmed independently in both eras' corpora, and no amount of auditor tuning changes that — those need a different mechanism (a post-admission diff review, or better test-harness isolation, which Track A's worktree redesign directly improves for the staging-discipline category).
