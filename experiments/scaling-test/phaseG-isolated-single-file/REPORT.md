# Phase G — isolated single-file validation (post-redesign)

Redoes Phase F correctly. Phase F's fatal flaw: one `general-purpose` agent played shard-test-writer *and* builder sequentially in the same session — self-grading was structurally possible the whole run. Phase G uses genuinely separate `Agent` spawns per role (test-writer → fresh test-auditor → builder), no shared context between any two, matching the redesigned `/manager-mode`'s actual pipeline (see `/Users/westley/.claude/plans/this-has-me-thinking-happy-moth.md`, Part 1). Every result below independently re-verified — reran pytest, hand-computed contradiction arithmetic myself, grepped actual call sites — never taken on any agent's report alone.

Same order-pricing domain as Phase E/F (`../phaseE-leaf-ceiling-v2/MODULES.md`), `impl_files: 1` throughout, extended with new complexity to force real LOC growth instead of Phase F's mostly-unused budget headroom (9% utilization at F3): an order-lifecycle state machine (G2+), a shared audit-log helper called from 4 sites (G3+), and multi-currency settlement with a second, precedent-free seeded ambiguity (G4).

## Results

| Rung | Scope | Impl LOC / budget | Utilization | Tests | Coupon-order resolution | Currency-timing resolution | Audit outcome |
|---|---|---|---|---|---|---|---|
| G1 | = E1/F1 | 164 / 220 | 75% | 22/22 | coupon-last (E1 precedent) | n/a | REVISE → fixed → PASS |
| G2 | = E3/F2 | 220 / 480 | 46% | 65/65 | coupon-first (E3 precedent) | n/a | PASS |
| G3 | = E5/F3 | 339 / 900 | 38% | 59/59 | coupon-last (E5 precedent) | n/a | PASS (but see gap below) |
| G4 | superset of G3 | 339 / 1400 | 24% | 47/47 | coupon-last (own reasoning, no direct precedent citation) | convert-last | PASS |

Budget utilization at 24-75% (mean ~46%) vs. Phase F's flat 9% — the tighter, complexity-driven budgets worked as intended. G4 came in lower than the 30-45% target range; the domain's genuine complexity ceiling for this scope may sit below 1400 lines rather than the budget being too loose — worth noting for any future rung design, not re-litigated here.

## Finding 1 — the pre-impl test audit works: caught a real defect before any builder touched the code

G1's first-pass test-auditor (fresh context, zero visibility into the test-writer's reasoning) flagged the coupon-order discriminating test as landing on an exact floating-point `.xx5` rounding tie: `102.5 * 0.93` sits precisely on the boundary where `amt*(1-rate)` rounds to `95.32` but the mathematically-equivalent `amt-amt*rate` rounds to `95.33` — identical to the pinned order's expected value. A wrong-order implementation coded the second way would have passed the test anyway. Verdict: REVISE. A **new** fresh test-writer spawn (no memory of authoring the original) picked a new numeric case, verified robust under both arithmetic styles (checked a grid of 19 other qty/tier combinations to confirm the fix pattern generalized, not just a one-off lucky pick). A **new** fresh auditor (not the one that flagged it) re-audited from scratch and independently reproduced the same 4 numbers, confirming PASS. This is the redesign's core thesis working exactly as designed: a real, subtle test-quality defect caught and fixed entirely before any implementation existed, by a process that never let the same context grade its own work.

## Finding 2 — cross-rung contradiction drift is orthogonal to isolation quality

3 of 4 rungs (G1, G3, G4) resolved the coupon-order contradiction as coupon-last; G2 resolved it coupon-first — the same fundamental split Phase E and Phase F both showed, now reproduced under genuinely isolated 3-agent pipelines instead of Phase F's flawed solo-agent version. **Real isolation did not change this behavior.** Each rung's test-writer independently cited a different scope-matched Phase E precedent (G1→E1, G2→E3, G3→E5) as its tiebreaker, and Phase E's own 5 rungs were never mutually consistent in the first place (E1/E5 coupon-last, E2/E3/E4 coupon-first — confirmed by direct grep in the prior Phase F session). Isolation quality and cross-run consistency are answering different questions: isolation determines whether a single run's test genuinely proves its own claim; consistency requires comparing across runs, which nothing in this pipeline — old or redesigned — does automatically. The redesign's new "Delegated drafting passes" / reviewed-authorship model doesn't touch this either, since precedent-citation across independent experiment rungs isn't a manager-mode phase, it's an artifact of how this specific experiment was structured (each rung told to consult prior rungs' code as a tiebreaker option).

## Finding 3 — the pre-impl audit has a real, honest gap: it missed an ordinary test-authoring bug outside the contradiction it was tuned to check

G3's builder refused to force a test green and correctly escalated: `test_low_stock_alert_empty_when_all_above_threshold` asserted `low_stock_alert(catalog, threshold=1) == []`, but the catalog's `gizmo` has `stock: 0`, and "strictly below threshold" means `0 < 1` is `True` — gizmo should be included, not excluded. This has nothing to do with either seeded contradiction; it's an ordinary test-writer arithmetic slip in a function explicitly marked "standalone, lower scrutiny." G3's fresh test-auditor (a real agent, PASS verdict, correctly caught the *harder* audit-log-helper interaction test and the coupon-order arithmetic) missed this one. **Neither the test-writer nor the auditor caught it — only the builder did, by trying to make a spec-faithful implementation pass and failing.** Fixed directly as a mechanical, evidence-backed correction (0 < 1 is not a design-decision ambiguity) rather than routed back through another test-writer/auditor cycle, per the redesigned 3.4.3's provision for mechanical fixes — recorded in the test file itself.

This is the concrete, first real-world instance of the gap the redesign's own plan document flagged in advance: removing Phase 8's Stage-C (code-quality review of finished implementation) trades away a safety net, accepted by the user as a known cost. This experiment shows the pre-impl audit is not a full substitute — it's excellent at the specific failure mode it's built to catch (does this test actually prove what it claims about a stated ambiguity) and offers no particular protection against an ordinary authoring slip elsewhere in the same file. The **builder** ended up being the real backstop here, which is a coincidence of TDD's own RED/GREEN discipline (a correct implementation cannot satisfy an incorrect test), not a designed safety layer — a differently-shaped bug (one where a plausible-but-wrong implementation coincidentally satisfies a wrong test) would not get this same protection.

## Finding 4 — token cost, isolation vs. Phase E's file-count scaling

Summed per-rung token cost (all roles — test-writer, auditor, builder, plus G1's extra revision+re-audit cycle):

| Rung | Total tokens (all roles) |
|---|---|
| G1 | 261,537 (includes 1 revise/re-audit cycle) |
| G2 | 186,560 |
| G3 | 200,822 |
| G4 | 198,451 |

**This is not a clean re-test of the file-count-vs-LOC finding** — Phase G's per-rung cost includes 3-5 separate agent spawns (isolation itself has overhead: each fresh context re-reads the same contract excerpts, brief, and domain spec from scratch) versus Phase E/F's 1 solo agent per rung. G1's cost (261k) exceeds every Phase E rung's cost (89k-151k) despite G1 covering the *smallest* scope of any rung in either phase — that's the isolation/coordination tax, not a scope-driven cost. A fair re-test of "does file-count or LOC drive token cost" would need to hold agent-count-per-rung constant across the comparison, which this experiment didn't do (by design — the whole point was adding isolation, not controlling for its cost). What can be said: isolation has a real, non-trivial token cost of its own, separate from and additive to whatever the file-count/LOC axis contributes. Worth a dedicated future comparison (same isolated 3-agent structure, deliberately varied file count vs. LOC) if that specific number is wanted.

## Verdict

Correctness held at every rung once test-audit findings were addressed (G1's REVISE, G3's builder-caught defect) — 193/193 tests pass across all 4 rungs, largest single file 339 LOC with zero unresolved defects. The large-single-file preference from the redesigned `playbook.md` Sizing section is not contradicted by anything here — no rung showed a builder losing track of an earlier same-file decision as LOC grew (G4, the largest, explicitly reported no such drift, matching Phase E's own top-rung finding that complexity strain — when it appeared at all — showed up in spec/test-authoring, not implementation). The real news this phase produced is about the audit's actual reach, not file size: it's precise and effective at the specific contradiction-discrimination problem it was designed for (Finding 1), doesn't resolve cross-run inconsistency because that was never its job (Finding 2), and has a genuine blind spot for ordinary authoring mistakes outside its focus area (Finding 3) — a known, accepted tradeoff per the redesign plan, now demonstrated concretely rather than theoretically.
