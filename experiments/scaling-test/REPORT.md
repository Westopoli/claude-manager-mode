# Manager-mode scaling investigation — Phase A/B results

Small-scale, information-dense first pass, per the approved plan. Target: a
synthetic "warehouse toy system" (`target-repo/`, Python stdlib, pytest),
seeded-fault grading. Not the full-scale campaign — this determines what's
worth scaling up.

## Timing / token summary

| Run | Role | Tokens | Duration (s) |
|---|---|---|---|
| leaf-A1 (at-spec) | builder | 23,032 | 49.1 |
| leaf-A2 (stretched) | builder | 25,347 | 53.7 |
| leaf-A3 (overloaded) | builder | 19,964 | 27.6 (refused fast) |
| Phase A auditor (batch of 3) | reviewer | 25,048 | 63.3 |
| leaf-B1 (shard-A) | builder | 25,922 | 67.7 |
| leaf-B2 (shard-A) | builder | 21,770 | 38.2 |
| leaf-B3 (shard-B) | builder | 22,625 | 49.7 |
| leaf-B4 (shard-B) | builder | 19,863 | 25.0 |

Phase A wall-clock (3 builders parallel, then 1 auditor): ~54s + ~63s ≈ **117s** for 3 leaves + audit.
Phase B wall-clock (4 builders fully parallel): **~68s** for 4 leaves (bounded by the slowest, B1) — the shard split cost nothing in wall-clock since shards ran concurrently.

## Phase A — single-leaf capability findings

**Result: 2/2 in-budget leaves passed clean, 1/1 overloaded leaf refused correctly. Both seeded faults caught, zero silent slip-through — confirmed by independent auditor re-verification, not just builder self-report.**

- **leaf-A1 (control, 1 file, 200-line budget)**: brief deliberately contradicted spec (told to clamp negative stock to zero; SPEC.md AC-2 says raise `ValueError`, never clamp). Builder caught the contradiction unprompted, escalated via the brief's own escalation-trigger clause, sided with the spec, implemented correctly. 7/7 tests pass (verified by direct pytest execution).
- **leaf-A2 (stretched, 2 files, 400-line budget — 2x default)**: brief stated a wrong discount number (0.15 vs spec's 0.10 for the top tier). Same pattern: caught, escalated, resolved per spec. 11/11 tests pass (verified). Actual implementation used only 40 of the 400-line budget — the larger budget did not induce bloat or drift; the leaf just did the work and stopped.
- **leaf-A3 (overloaded, 3 files + an embedded ambiguous verb)**: refused outright, before writing any code. Caught **both** seeded faults independently — the 3-file bundling (its own `cavecrew-builder` scope rule: "1 ideal, 2 OK, 3+ refuse") and the ambiguous "handle malformed input as appropriate" phrasing (a design-decision leak the brief should never contain). Recommended the correct fix: split into 3 single-file leaves, and resolve the malformed-input question explicitly in the brief rather than deferring it to the leaf.

**Notable capability finding, not part of the original test design**: `cavecrew-builder` has no `Bash` tool in its toolset. Every builder in this experiment reported it could not literally run `pytest` and instead did a manual line-by-line trace of test-vs-impl, explicitly flagging this as a gap rather than fabricating a "tests passed" claim. I independently ran `pytest` against every leaf's output afterward and all traces were correct — but this is a real dependency in the current skill: `check_invariants.py`'s sizing/schema checks don't execute code either, so **RED-then-GREEN confirmation currently depends on either the overlord or a different sub-agent type actually running the tests**, not on the builder itself. Worth checking whether this is intentional (builder writes, someone else executes) or a gap.

## Phase B — shard mechanism findings

**Result: clean. Both shards admitted-equivalent (all 4 leaves pass, 34/34 tests, verified by direct execution), zero file overlap, and the cross-shard duplication probe resolved itself favorably without any parent intervention.**

- 1 overlord context (this conversation), 2 shards, 2 leaves each, all 4 running fully concurrently.
- Shard-A: `reporting.py` (leaf-B1), `notifications.py` (leaf-B2).
- Shard-B: `shipping.py` (leaf-B3), `shipping_rates.py` (leaf-B4).
- Zero cross-shard file overlap, confirmed by inspecting the actual staged tree under `.swarm/pending/`, not by trusting builder claims.
- **Cross-shard duplication probe**: leaf-B1 (shard-A) and leaf-B3 (shard-B) each independently needed to round a float to 2 decimal places for currency-like output, with no visibility into each other's work (different shards, no leaf-to-leaf messaging, per the skill's file-mediated-only coordination model). Both independently chose the same resolution — an inline `round(x, 2)` call at the single use site, explicitly reasoning in their `.ASSUMPTIONS.md` files that a named helper wasn't worth extracting for one call site — rather than either duplicating a named helper function or silently guessing different conventions. **This is the interesting result**: the isolation model didn't produce drift here, but that may be because the shared need was trivial (one stdlib call) rather than a real design decision. A harder cross-shard probe (e.g. a genuinely reusable non-trivial helper, or two shards needing the *same* non-obvious validation rule) would test the "no leaf-to-leaf messaging, parent-arbitrated only" model under more realistic pressure — this one didn't stress it.

## Interpretation against the research findings

The pre-experiment research found the skill's 12-leaf-per-wave comfort ceiling and 16-leaf refusal are **procedural instructions to the overlord, not code-enforced**, justified by overlord-context-fill and sibling-drift risk — not a claim that individual sub-agents can't handle more. Nothing in this small run contradicts that: leaf capability at 1-2 files / up to 400 lines looked solid, the 3-file/ambiguous-verb overload was caught cleanly by the builder's own guardrails, and the shard mechanism showed no coordination cost in wall-clock time (4 leaves across 2 shards finished in the time of the single slowest leaf, not sequentially).

## Recommendation for next round

1. **Loosen the leaf-size assumption to test one level further**: leaf-A2 used only 10% of its 400-line budget, and the auditor found no quality degradation. Worth testing a leaf that's actually 300-400 real lines (not budget headroom) with genuine complexity, to find where quality — not the file-count rule — actually degrades. The 2-impl-file ceiling (from `cavecrew-builder`'s own hard-refuse threshold) is the more binding constraint right now, not line count.
2. **Scale the shard test up one notch**: since 1 overlord / 2 shards / 2 leaves showed zero coordination cost and correct convergence, the next test per the plan's own escalation path is **1 overlord / 4 shards / 4 leaves each (16 leaves total)** — still at the existing per-shard 12/16 cap, but now actually exercising sharding at a size where coordination failures would be more likely to surface. Recommend planting a **harder** cross-shard probe next time (a non-trivial shared validation rule, not just a one-line rounding call) since this round's probe was too easy to be a real stress test.
3. **Give the next round's builder sub-agent type a Bash tool**, or explicitly confirm test-execution is meant to happen at a different stage — this round surfaced it as a real gap, not a design choice we already knew about.
4. Do not raise the per-wave 12/16 cap itself yet — nothing here suggests the ceiling is wrong, only that shard-based horizontal scaling is safe to lean on further, which is exactly the direction the skill's own docs already point.

## Skill change made between Phase B and Phase C

Phase A/B surfaced a real gap: `cavecrew-builder` has no `Bash` tool, so it
cannot execute its own tests — every leaf in Phase A had to manually trace
test-vs-impl instead of confirming RED-then-GREEN for real. Per your
direction, **`skills/manager-mode/SKILL.md` §4.2 (Subagent type selection)
now defaults to `general-purpose` for impl leaves**, with `cavecrew-builder`
demoted to an opt-in choice for genuinely trivial single-file leaves where
execution isn't needed. Edited at the source (`/Users/westley/Projects/claude-swarm/skills/manager-mode/SKILL.md`)
and synced to all 4 install locations (`~/.claude/skills/`, the project's
`.claude/skills/`, `~/.codex/skills/`, plus the secondary account's
`.claude/skills/`). No other skill files needed changes — hardcore inherits
Phase 4 unchanged.

## Phase C — leaf-size ceiling sweep (general-purpose, real test execution)

You asked whether Phase A had actually found the leaf-capability ceiling.
It hadn't — `cavecrew-builder`'s own 2-impl-file hard-refuse was the wall
Phase A hit, not a real capability limit. Phase C re-runs the ladder with
`general-purpose` (Bash-enabled) and pushes deliberately past what any real
brief should ever ask of one leaf, to find where quality actually breaks.
New domain (order-pricing engine, same seeded-fault methodology), 4 rungs:

| Rung | Files | Line budget | Real impl LOC | Tests | Tokens | Duration (s) |
|---|---|---|---|---|---|---|
| C1 baseline | 1 | 150 | 14 | 8/8 | 36,443 | 34.0 |
| C2 stretched | 1 | 450 | 146 | 26/26 | 42,829 | 68.0 |
| C3 multi-file | 3 | 750 | 244 | 36/36 | 49,068 | 111.3 |
| C4 stress | 5 | 1,300 | 345 | 60/60 | 61,743 | 187.4 |

All four rungs: every test genuinely passes, **re-verified independently by
me executing pytest myself**, not taken on the builder's word (this time the
builder's own claim was trustworthy too, since it had Bash and actually ran
the tests — a direct payoff of the skill change above). Real LOC stayed well
under budget at every rung (26% of budget at C4) — bigger budgets did not
induce padding, matching the Phase A pattern.

**There are two different ceilings here, not one, and they diverge:**

- **Correctness ceiling**: did not break anywhere in this ladder. C4 (5
  files, 345 LOC, arithmetic chained across 3 of the 5 files) still shipped
  100% passing, correct code, with both seeded faults (an ambiguous-verb
  design-leak and a numeric contradiction) caught and explicitly documented.
  C4 self-reported needing one extra fix-reverify cycle for a rounding/
  arithmetic mismatch between its own test expectations and impl — but it
  caught that itself via real pytest execution and fixed it before
  reporting done, so nothing incorrect shipped. This is the Bash-access
  payoff directly: a `cavecrew-builder` leaf has no way to catch this kind
  of self-inflicted error before reporting green.
- **Judgment-quality ceiling: starts degrading earlier, at C3.** C1 and C2
  handled their seeded contradictions the way Phase A's leaves did — picked
  the stated ground truth, documented why. C3 (3 files) hit a contradiction
  with **no stated ground truth** (the brief deliberately gave two different
  canonical orders in two different files, on purpose, to see what happens
  without an answer key) and instead of escalating, it invented a
  "keep each file locally self-consistent with its own section" resolution.
  Concretely: `discounts.stack_discounts()` was implemented per one order,
  `engine.build_invoice()` was implemented per the other order — and
  **`build_invoice` never calls `stack_discounts`, leaving it dead code**.
  I confirmed this by grep: `stack_discounts` is defined but never called
  outside its own tests. All 36 tests still pass, because the tests were
  written to match this same split resolution — a real auditor or a
  downstream leaf reading this code would find an unused public function
  implementing a contradicted spec, which is a worse outcome than either
  "pick one and note it" or "escalate," even though nothing is functionally
  broken today.

**This is the actual finding worth acting on**: correctness held all the
way to 5 files / ~350 real LOC / cross-file arithmetic, well past what
`cavecrew-builder`'s 2-file rule or the original Phase A ladder tested. But
**silent judgment degradation under genuine (no-answer-key) ambiguity shows
up earlier — at 3 files** — and it's a more dangerous failure mode than an
outright bug precisely because it passes every test. A brief-audit step that
only checks "no ambiguous verbs" (per `check_invariants.py`'s current
`check_no_design`) would not catch this, since the ambiguity here was a
genuine cross-section contradiction inside one accepted brief, not an
ambiguous verb.

## Updated recommendation for next round

1. **The file-count/line-count ceiling for correctness is higher than the
   skill currently assumes** — worth testing whether the `impl_files`
   `do_not_edit`/budget defaults should scale up for `general-purpose` leaves
   specifically (which have Bash and can self-verify), while keeping
   `cavecrew-builder`'s tighter defaults for the narrower cases it's still
   used for.
2. **Add a brief-audit check for unresolved cross-section contradictions**,
   not just ambiguous verbs — Phase 3's `check_no_design` catches "as
   appropriate" phrasing but would not have caught C3's two-different-orders
   defect, since neither individual sentence is ambiguous on its own. This
   is a gap in the audit, not just a leaf-judgment issue — the brief itself
   should never have shipped with an internal contradiction and no way to
   resolve it; Phase 3 should be checking for that structurally (e.g. flag
   any spec value/rule cited more than once with different values, before a
   leaf ever sees the brief).
3. Still hold off on raising the 12/16 per-wave leaf-count cap — this round
   was about single-leaf capability, not wave-level coordination, and
   nothing here changes that assessment from Phase A/B.
4. Next scaling step: either (a) the previously planned 4-shard × 4-leaf
   wave-level test, now using `general-purpose` builders, or (b) a Phase C
   follow-up rung (C5) specifically testing whether a *properly audited*
   brief (no internal contradiction, Phase 3 gate tightened per
   recommendation 2) prevents the C3-style silent degradation at the same
   file count — worth doing before scaling wave size further, since it's
   cheaper and answers a more foundational question.

## Phase D — test-construction fix, and live verification of the fix

C3's root cause, once traced properly: the experiment had leaves write their
own tests, which is **not** `/manager-mode`'s actual default
(`test_owned_by: parent`). Research (LLM self-grading bias, classicist vs.
mockist TDD, mutation testing for dead-code detection) plus your direction
produced five changes to the real skill source, all applied at
`/Users/westley/Projects/claude-swarm/skills/{manager-mode,manager-mode-hardcore,swarm-shared}/`
and synced to all 4 install locations:

1. **New role — shard test-writer.** Overlord's own test authorship narrows
   to spec/contract/umbrella only. A `shard-test-writer` sub-agent (or the
   overlord itself, inline, for single-wave runs) writes every per-leaf test
   in a shard, independent of the leaf that later implements it. Added to
   `SKILL.md` §2.5 and `playbook.md`'s Roles section.
2. **Mockist composition rule.** Any leaf with 2+ `impl_files` now requires
   at least one interaction assertion (does the orchestrator actually call
   the collaborator?) alongside state checks — added to `brief-template.md`
   and referenced from §2.5. This is the rule that directly closed the C3
   hole: a state-only test can't tell a wired-in function from an orphaned
   one sitting next to it.
3. **G8 admission gate — `test_quality_gate.py`** (new script,
   `swarm-shared/scripts/`). Two checks, correctly scoped after a planning-
   stage correction (mutation testing alone does *not* catch C3 — a function
   with its own direct unit test survives mutation on that test regardless
   of whether anything else calls it):
   - **Reachability** (blocks admission): AST call-graph analysis over a
     leaf's own impl files. Finds the entry point (most outgoing local
     calls), flags any *other* top-level function nothing calls. Deterministic,
     no randomness.
   - **Lite mutation** (advisory by default, `--strict` blocks — used by
     `manager-mode-hardcore`): one mechanical mutation per function
     (numeric-literal offset, bool negate), rerun tests, flag if still green.
     Catches weak/tautological assertions — a different problem than
     reachability, not a replacement for it.
4. **Phase 3.4 — pre-spawn test-quality audit.** A fresh-context sub-agent
   (not the overlord — same self-enhancement-bias reasoning as Phase 8)
   reviews a shard's tests against the locked spec before any leaf spawns.
5. **`check_no_contradiction()`** in `check_invariants.py` — heuristic,
   flags the same identifier bound to two different literal values across
   *sibling briefs* in the same wave/shard, before any leaf spawns.

### Building `test_quality_gate.py` surfaced a real bug in itself

First implementation used `Compare.col_offset` to locate comparison operators
for mutation — wrong: that offset points at the comparison's *left operand*,
not the operator, so every comparison mutation silently failed its
column-sanity check and fell through to whichever numeric-literal site came
next, sometimes one no test exercised. Caught by smoke-testing the gate
against the real C3 artifacts before trusting it (below), not by review —
fixed by dropping comparison mutation entirely and keeping only
Constant-node mutations, whose column offsets are reliable.

### Smoke test against real C3/C4 artifacts (before the live run)

Ran the finished gate directly against the actual buggy C3 output and the
actual healthy C4 output from Phase C, independently re-verified:

- **C3 (buggy)**: `leaf-X1: FAIL: reachability: function 'stack_discounts'
  in discounts.py is never called by any other function in this leaf (entry
  point appears to be 'build_invoice')... exit 1` — catches the exact,
  known defect, precisely, no false positives on `calculate_tax` or
  `shipping_cost` (which genuinely are called, just from within the same
  file — an earlier, simpler text-matching version of the check flagged
  these incorrectly before being replaced with real AST call-graph analysis).
- **C4 (healthy)**: zero reachability findings, 3 mutation findings, all
  advisory, exit 0 — the gate doesn't block good code over an unlucky
  single-mutant miss.

### Live verification: 3 independent runs through the fixed process

Same defect shape as C3 (2-file leaf, deliberately unresolved discount-
stacking-order contradiction, no stated ground truth), same shared brief,
run independently 3 times by fresh `general-purpose` agents, each working
through parent → shard-test-writer → builder → admission gates for real,
using the actual updated skill files (not a paraphrase). Every claim below
independently re-verified by me — re-ran pytest myself, grepped each
`engine.py` for a real call to `stack_discounts`, re-ran both admission-gate
scripts myself — not taken on the agents' word:

| Run | Contradiction caught? | Where | Resolution | Tests (verified) | check_invariants.py | test_quality_gate.py |
|---|---|---|---|---|---|---|
| 1 | Yes | Writing the composition/interaction assertion, before any impl | Escalated via question ledger, picked `stack_discounts`'s stated order as ground truth | 15/15 pass | PASS | 1 advisory (`apply_coupon`) |
| 2 | Yes | Same — writing the interaction assertion forced a concrete numeric choice (confirmed the two orders diverge: 82.94 vs 82.93) | Escalated, same resolution | 13/13 pass | PASS | 1 advisory (`apply_coupon`) |
| 3 | Yes | Same, plus explicitly added a return-value-passthrough assertion (not just a call-assertion) to block a "calls it but ignores the result" loophole | Escalated, same resolution | 23/23 pass | PASS | 2 advisory (`apply_coupon`, `build_invoice`) |

**3/3: single coherent implementation, `build_invoice` genuinely calls
`discounts.stack_discounts` (confirmed by grep on the real file, not agent
claim), zero reachability findings, zero dead code.** This is the outcome
tier-2 ("Good") in the plan's rubric — the shard-test-writer's independent
authorship, forced through the mockist composition rule, caught the
contradiction at test-authoring time in every run, before the reachability
gate (tier 3) ever had to fire as a backstop.

**Two things did NOT work as hoped, both honestly reported by the agents
and independently confirmed:**

- **`check_no_contradiction()` never fired, in any run — expected, now
  documented.** It only compares literal values *across sibling briefs*.
  C3's actual defect was a contradiction *within one brief* (two sections of
  the same document), which this heuristic was never scoped to catch. I
  verified this directly against C3's real test files before the live run
  (grep for the pattern check_no_contradiction looks for — found none,
  since the contradiction was about call *order*, not a literal value
  mismatch). Tier-1 ("Best" — caught before any test/impl exists) did not
  happen in any run; tier-2 did, every time. Worth being honest that the
  Phase 3 mechanical check is not what's carrying this fix — the composition
  rule (a process change, not a script) is.
- **The `apply_coupon` mutation advisory fired in all 3 runs, independently.**
  Not noise — a consistent, real signal that `apply_coupon`'s error-path
  tests (unknown code / expired / below-min-spend) don't pin the exact
  discount multiplier tightly enough to catch a numeric mutation. Worth
  tightening in a follow-up, but correctly non-blocking here since it's
  unrelated to the contradiction defect class this phase targeted.

### Two real bugs found live, fixed, and re-verified

Both surfaced independently by 2-3 of the 3 agents (not one agent's fluke),
both in `check_invariants.py`, both pre-existing (not introduced by this
phase's edits), both fixed and re-synced to all 4 install locations, existing
test suite re-run clean (6/6) after each fix:

1. **Schema falsely required the singular `test_file`/`impl_file` field even
   when a brief legitimately used only the plural `*_files` form.** A
   genuinely 2-file leaf with no natural "primary" file has no reason to
   duplicate one path into the singular field. Fixed: `check_schema` now
   accepts a non-empty plural list as satisfying the requirement.
2. **`_leaf_paths()` didn't dedupe singular + plural, so a brief that (not
   unreasonably, given #1) listed the same path in both fields self-
   collided in `check_non_overlap`** — a brief could fail audit by
   "overlapping with itself." Fixed with `dict.fromkeys` dedup.

### Verdict

The fix works, for the reason it was designed to: separating who writes
tests from who resolves ambiguity, plus forcing an interaction assertion
whenever files compose, converts a silent two-implementations split into a
forced, visible, single decision made before any impl exists. The mechanical
gate (G8 reachability) is a real, precise, independently-validated backstop
— but in all 3 live runs it wasn't what saved the outcome; the process
change was. The Phase 3 contradiction heuristic is real but narrower than
its name suggests (cross-brief only) — this is now documented rather than
overclaimed. Recommend: keep the current scope (don't chase a general
within-brief contradiction detector — the composition rule already covers
the dangerous case, where the contradiction concerns something that's
supposed to compose), and consider tightening `apply_coupon`-style
error-path test rigor as a smaller, separate follow-up given the 3/3
corroborated signal.

## Phase E — leaf-size ceiling, on the fixed process

Phase C's ceiling test used `cavecrew-builder`/an unaudited process and only
reached 5 files before the C3 defect appeared. This phase asks the real
question: with the Phase D fix in place, how far does a single leaf actually
go before *correctness* — not an artifact of the old process — breaks down.
C3's shape (3 files, the coupon-order contradiction) is the floor. Five
rungs, `general-purpose` throughout, each running the full solo pipeline
(parent brief → shard-test-writer with composition assertions → builder →
both admission gates), on a cumulative 12-module order-pricing domain
(`phaseE-leaf-ceiling-v2/MODULES.md`) with the same contradiction seeded at
every rung. Every result below independently re-verified by me — reran
pytest, reran both gates, grepped for real calls — not taken on any agent's
word.

| Rung | Files | Impl LOC (of budget) | Tests | Contradiction caught? | Gate result |
|---|---|---|---|---|---|
| E1 | 3 | 119 / 750 | 19/19 | Yes, pre-impl, escalated via question ledger | PASS (post-fix) |
| E2 | 5 | 134 / 1300 | 35/35 | Yes, pre-impl, mechanical tiebreaker | PASS |
| E3 | 7 | 122 / 1900 | 45/45 + 2 umbrella | Yes, pre-impl, reused Phase D precedent | PASS (post-fix) |
| E4 | 9 | 180 / 2500 | 53/53 | Yes, pre-impl, reused Phase D precedent | PASS (post-fix) |
| E5 | 12 | 148 / 3200 | 66/66 | Yes, pre-impl, reused **E1's own** precedent | PASS (post-fix) |

**Headline: correctness held cleanly at every rung, all the way to 12 files
and 66 tests.** The contradiction was caught before any impl existed in
every single run, no exceptions — the composition rule from Phase D is
doing exactly what it was built to do, independent of leaf size. LOC stayed
far under budget throughout (5-8% utilization even at the top rung) —
consistent with every prior phase: bigger budgets don't induce bloat, agents
just do the work and stop.

**One genuine complexity-strain signal, and it wasn't where you'd expect.**
E5 (12 files) was the only rung where the *leaf/builder* itself was clean
first-try — zero correction passes on implementation. The strain showed up
one level up, in the *parent/test-author* role: composing the full pipeline
(validation → catalog → discounts → loyalty → tax → shipping → currency,
all in one `build_invoice`) required an explicit correction pass to pin down
underspecified composition order, and the agent caught its own arithmetic
mistake in hand-verifying the expected test values only because it ran the
numbers in Python instead of trusting mental math. Worth noting for scaling
guidance: at high leaf complexity, the bottleneck is the spec-writer holding
the full composition coherently, not the implementer.

### Three more real bugs found live, fixed, and re-verified — same discipline as Phase D

1. **Brief-discovery glob false-positive.** `check_invariants.py`'s
   `leaf-*.md` glob also matches the brief template's own documented sidecar
   convention — `leaf-E1.ASSUMPTIONS.md`, `.ESCALATION.md`, `.RESULT.md` —
   and tried to parse them as malformed briefs, producing a permanent false
   FAIL on every leaf that follows the assumption-log convention as written.
   Fixed: filter to `"." not in path.stem` (a real brief id never contains a
   dot; every sidecar file does). Verified against E1's actual collision.
2. **`INTERACTION_HINTS` false-negative via ordinary prose.** The original
   heuristic scanned test text for bare words like "call"/"mock" near a
   function name. E4's agent proved, empirically, that its own explanatory
   comment — *"not part of `build_invoice`'s call chain"* — contained the
   word "call" and silently satisfied the check for an unrelated reason,
   nothing to do with any real interaction assertion. Fixed two ways:
   `_strip_comments()` so comments never reach the regex at all, and the
   regex itself tightened to require actual mock/patch API syntax
   (`assert_called`, `Mock(`, `patch(`, `monkeypatch.setattr(`, `wraps=`)
   instead of loose English words. Re-verified against the exact case that
   exposed it.
3. **No escape hatch for legitimately standalone functions — a design gap,
   not a bug.** Fixing #2 correctly made the gate start flagging E3/E4/E5's
   deliberately-standalone utility functions (`low_stock_alert`,
   `summarize_orders`, `release_stock`) — three independent runs hit this,
   and every agent refused to game the check by injecting fake interaction
   syntax into an honest state-check test, which is the correct call. The
   gate genuinely cannot infer "intentional utility" vs. "orphaned bug" from
   code shape alone; only the brief author knows which. Added
   `standalone_symbols` as a new optional brief-frontmatter field (same
   declarative pattern as `escalation_triggers`/`codebase_preconditions`),
   read by `test_quality_gate.py` and exempted from the reachability check.
   Verified three ways: (a) retrofitting E3/E4/E5's real briefs with the
   field clears all three false positives, all the way down to a clean
   exit 0; (b) the mutation gate still runs mutation attempts against those
   now-exempted functions (advisory findings unaffected); (c) re-running
   against the actual C3 buggy artifacts, with no `standalone_symbols`
   declared, still correctly blocks — the fix doesn't weaken real detection,
   it just stops asking the impossible of a heuristic.

### Verdict

The single-leaf ceiling is higher than anything tested so far, not lower —
12 files and 66 tests produced zero correctness defects and the fixed
process caught the seeded contradiction every time regardless of size. The
actual limiting factor discovered this phase wasn't leaf size at all; it was
gate false-positive/false-negative precision on the *reachability* heuristic,
which is now fixed and given a proper declarative escape hatch rather than
patched over. Recommend: next round can reasonably push a 6th rung (15-16
files, near the wave-level leaf-count cap for comparison) purely to find
where correctness *actually* starts to degrade, since nothing in E1-E5
found that ceiling — but the more valuable next step per the E5 signal is
probably tooling for the parent/spec-author role at high composition
complexity (e.g. a checklist or a script that mechanically verifies a
hand-derived expected value before it gets locked into a test), since that's
where the one real strain signal in this whole phase actually showed up.

## Phase F — single-file scale axis (inverse of Phase E)

User-raised methodology gap: Phase E scaled file COUNT (3→12 files) while
LOC stayed nearly flat (119→148). `test_quality_gate.py`'s reachability/
composition check literally no-ops below 2 `impl_files` — a single large
file was never gate-checked or tested regardless of size, a real blind axis
Phase E never touched. Phase F holds `impl_files=1` and scales total
responsibility/LOC instead, using the identical domain, functions, and
seeded coupon-order contradiction as `MODULES.md`, scope-matched to
E1/E3/E5 (F1=E1 scope, F2=E3 scope, F3=E5 full 12-module scope) so results
are directly comparable to Phase E on the file-count axis alone. Same
`general-purpose` agent, same full solo pipeline (write tests → RED →
implement → GREEN → run both gates → report). Contradiction seeded
intra-file since there's no second file to disagree with: a comment block
near the discount functions states one order, `build_invoice`'s own
docstring states the other, both inside the same file. Every result
independently re-verified — reran pytest, reran both gates, grepped the
actual impl for the resolved order and for standalone-function call sites.

| Rung | Matches | Impl LOC (of budget) | Tests | Contradiction resolution | Gate 1 (`check_invariants`) | Gate 2 (`test_quality_gate`) |
|---|---|---|---|---|---|---|
| F1 | E1 scope | 162 / 750 | 19/19 | volume→membership→coupon-last | FAIL (brief-prose "Resolve", not a leaf defect) | SKIP (1 impl_file) |
| F2 | E3 scope | 194 / 1900 | 42/42 | coupon-first→volume→membership | FAIL (brief-prose "determine", not a leaf defect) | SKIP (1 impl_file) |
| F3 | E5 scope | 291 / 3200 | 66/66 | volume→membership→coupon-last | FAIL (brief-prose "Resolve", not a leaf defect) | SKIP (1 impl_file) |

**Headline: correctness held cleanly at every rung, same as Phase E — but
Phase F surfaced a finding Phase E's own results already contained and
nobody had cross-checked: the seeded contradiction does not resolve to one
stable answer across rungs, in either experiment.** Direct inspection of
all 5 Phase E rungs' actual `discounts.py`/`stack_discounts` code:

- E1, E5: `volume → membership → coupon-last`
- E2, E3, E4: `coupon-first → volume → membership`

3 of 5 Phase E rungs actually landed coupon-first; E1 and E5 (the two
bookend rungs, and the two REPORT.md happened to describe in most detail
above) are the minority, not the majority.

Phase F's rungs, each explicitly reusing its scope-matched Phase E rung as
precedent, faithfully reproduced the exact same split: F1 (=E1) and F3
(=E5) landed coupon-last, F2 (=E3) landed coupon-first — the opposite
order, numerically different for real orders, both internally
self-consistent (each rung's own tests pass, each rung's impl matches its
own tests). Nothing in the current process catches this, because no gate
or test in this pipeline ever compares one leaf's/rung's resolution against
another's — each is only checked against its own brief and its own tests.
**This is the same shape as the original C3 defect** (two
internally-consistent-but-disconnected implementations of one contested
decision, invisible to a green test suite) — except manifesting across
independently-run leaves instead of within a single leaf's own files. The
composition-assertion rule that fixed C3 only forces consistency *within* a
leaf's own impl/test pair; it has no mechanism to detect or prevent drift
*between* leaves that both claim to implement "the canonical order" from
the same ambiguous spec.

**On the file-count-vs-file-size question the phase was built to answer**:
inconclusive in isolation, because the cross-rung contradiction drift is a
bigger confound than file count at this scope. What Phase F does show
directly: `test_quality_gate.py`'s SKIP-below-2-files behavior worked
exactly as documented at every rung, and every agent correctly reported
SKIP as "gate did not evaluate anything" rather than misreading exit-0 as
"passed clean" — no process-blind-spot on that specific question, in three
independent runs. Complexity-strain signal was absent even at F3 (full
12-module scope, 291 LOC, first-try clean end to end) — no single-file
analogue of E5's parent/test-authoring strain signal appeared. The one
concrete single-file-specific note (from F2): keeping two
contradiction-bearing comment blocks consistent with each other required
re-reading both side by side while writing, since — unlike the multi-file
case — nothing enforces they stay in the same file's view together; it
didn't cause an error here, but it's a plausible drift vector at larger
scale that multi-file leaves structurally can't have (each half lives in
its own self-consistent file).

### Verdict

Single-file leaves are not obviously worse than multi-file leaves at
matched scope — 3200 LOC in one coherent file produced zero defects and no
strain signal Phase E's multi-file top rung didn't also show (or rather,
didn't show at all, cleanly, in both forms). The real finding this phase
produced wasn't about file size at all: it's that **an unresolved
cross-section spec ambiguity, when handed to multiple independent agents
across multiple independent runs with no shared ground truth, does not
converge to one answer even when every individual run is internally
correct and every individual run's tests pass.** Recommend: before treating
either Phase E's or Phase F's rungs as reference implementations of "the"
correct order, resolve the actual contradiction in `MODULES.md` itself (it
was deliberately left unresolved for probing purposes, which was the right
call for testing single-leaf behavior, but is now actively producing
contradictory "canonical" artifacts if anyone reuses these rungs as
precedent going forward). Process-level fix worth considering: a
cross-leaf/cross-rung consistency check — analogous to the existing
`check_no_contradiction()` cross-sibling-brief heuristic, but comparing
*resolutions*, not just brief prose — for any leaf that explicitly cites
another leaf's implementation as its tiebreaker precedent, the way every
Phase F rung did here.
