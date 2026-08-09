# Manager-mode improvement — August 2026

## 1. Overview

`/manager-mode` is a single-command parallel-agent TDD cascade: an overlord
chat reads a spec/contract/umbrella test, decomposes the work into leaf
briefs, spawns isolated sub-agents to implement against pre-written failing
tests, and admits or reverts each leaf's diff based on independent
verification — never on any agent's self-report.

This doc formalizes an evidence-driven improvement arc that ran across
roughly a dozen sessions in August 2026: eight lettered/numbered experiment
phases (A–H) probing where the skill's process actually breaks, plus a
separate allocation-redesign thread that changed how the overlord
decomposes work in the first place. It exists because that arc is
currently scattered across ~10 memory files and several
`experiments/scaling-test/` report artifacts, with no single document
tying dates, findings, and the skill's current mental model together.

This is a synthesis document, not a replacement for its sources. For raw
data: `experiments/scaling-test/REPORT.md` (Phases A–E), the per-phase
`REPORT.md` files under `phaseF/G/H-*`, and `experiments/overlord-allocation-redesign/`
for the allocation-redesign pilots. For current behavior, ground truth is
always `skills/manager-mode/SKILL.md` itself — this doc describes it as of
August 2026, but the file may have moved on.

**A note on dates.** The underlying `REPORT.md` covering Phases A–E has no
date fields anywhere in it — none of those phases can be dated more
precisely than "earlier in this arc, predating the sessions below."
Phases F onward, the skill redesign, Phase G, G9+briefs+Phase H, the
allocation redesign, and Phase H3 are all dated **2026-08-07**, run across
several sessions on the same day.

---

## 2. Current mental model — what the skill does today

### The core loop

```
Phase 0  Preflight        — locate/bootstrap .claude-swarm.toml, resolve briefs_dir
Phase 1  Lite-discovery    — fires only for missing spec/contract/umbrella
Phase 2  Decompose         — 2.1 dependency map
                              2.2 consolidation pass + completeness sweep
                              2.2a post-plan checklist (6 questions)
                              2.3 task-size guardrail (16-leaf hard cap)
                              2.4 fat-file check
                              2.5 emit briefs
                              2.6 shard-test-writer authors per-leaf failing tests
Phase 3  Audit briefs      — check_invariants.py + codebase-preconditions
                              + 3.4 pre-spawn test-quality audit (fresh auditor per shard)
Phase 4  Spawn leaves      — N sub-agents in parallel
Phase 5  Wait + sweep      — aggregate ASSUMPTIONS sweep, wave snapshot
Phase 6  Admission loop    — per leaf: G1–G9 + file-match + umbrella pre/post + admit-or-revert
Phase 7  Final report      — counts + follow-up direction
```

Leaves only ever write implementation against tests they did not author.
The overlord's own authorship narrows to spec/contract/umbrella; a
dedicated **shard-test-writer** sub-agent writes every per-leaf test,
independent of whichever leaf implements against it.

### The two load-bearing pillars

1. **Authorship separation is absolute.** Whoever writes a test is never
   the same agent instance as whoever implements against it — true
   regardless of shard/no-shard, regardless of how allocation changes.
   This exists because of a real, concrete failure: **Phase C's C3
   defect** (§3) — when leaves wrote their own tests, an unresolved
   cross-file contradiction produced a silent, self-consistent-but-
   disconnected split implementation, and every test still passed green.
   Phase D's fix (separating test authorship from implementation, plus a
   mockist composition rule) converted that silent failure into a forced,
   visible, pre-impl decision — verified 3-for-3 in live re-runs.

2. **Adversarial fresh-context auditing + overlord-side goal
   reconciliation is the real safety mechanism** — not leaf-count caps,
   not LOC budgets. A fresh auditor tries to break an artifact before any
   builder touches it; the overlord — never a sub-agent — holds the
   overarching goal/plan in its own context and reconciles delegated
   output against it, every time, never delegating the reconciliation
   itself. Concrete evidence: Phase G's G1 rung (a fresh auditor caught a
   real `.xx5` floating-point rounding-tie defect, pre-impl); the
   allocation-redesign v2 pilots (§3), where the overlord's own
   completeness sweep caught real gaps in a delegated sub-agent's draft,
   on both test projects, zero repeat-misses against v1's known gaps.

### The 3 authorized delegation points — and nowhere else

1. **Phase 2.1 (dependency map)** — on a codebase with no `graphify_cmd`
   and a large/unfamiliar import graph, the overlord may spawn a
   read-only investigator to draft a dependency map; the overlord must
   independently confirm non-overlap before slicing briefs from it.
2. **Phase 2.2 (consolidation pass)** — on a large/unfamiliar spec, the
   overlord may spawn a fresh sub-agent to draft the consolidation
   grouping; the overlord must independently run 2.2's completeness sweep
   against the draft before adopting it.
3. **Phase 1 lite-discovery, structural ambiguity resolution** — for a
   genuine structural underspecification, the overlord may spawn a fresh
   sub-agent to propose a resolution with rationale, then present BOTH
   the proposal and its own assessment at the normal approval gate.

Explicitly **not** available anywhere else: brief emission (2.5), the
invariant audit (Phase 3), admission (Phase 6), the test-audit gate
itself (3.4). The rule is not "delegation is dangerous" — it's that
delegating the **check** itself, rather than upstream drafting labor
feeding a check the overlord still performs, is the specific failure mode
this boundary exists to prevent.

### Admission gates (Phase 6, per leaf)

| Gate | What it checks | Blocks? |
|---|---|---|
| G1 | Staged path doesn't match `parent_owned` globs | Yes |
| G2 | ASSUMPTIONS.md present when inference was implied | Advisory-shaped |
| G3 | Every open question answered or explicitly `unanswered: true` | Yes, on disagreement |
| G4 | No `pending` contract proposals; `accepted` ones actually landed | Yes |
| G5 | Wave-snapshot SHA-256 integrity outside this leaf's footprint | Yes |
| G6 | Escalation-trigger `detect:` command, if it fires, has a matching `.swarm/escalations/` file | Yes |
| G7 | Wave-sweep file exists and postdates every leaf's ASSUMPTIONS | Yes (first admission of wave) |
| G8 | Test-quality gate (2+ impl_files only): reachability blocks, mutation findings advisory | Reachability yes, mutation advisory |
| G9 | Complexity gate (cyclomatic > 10 or nesting > 3), all leaves | Advisory (uncalibrated, flagged in-code) |

G8/G9 are both advisory by default; `manager-mode-hardcore` runs G8 with
`--strict` (blocking). G9's thresholds are explicitly flagged in the code
itself as uncalibrated — Phase H (§3) was designed partly to calibrate
them, but never ended up running G9 against its own output, so this is
still an open item (§4).

### What this skill deliberately does not do

Doesn't write implementation itself. Doesn't use git — `.swarm/` files
replace branches/revert/log/regression-attribution (only cryptographic
commit signing is lost). Doesn't auto-spawn leaves before Phase 3's audit
passes. Doesn't make architecture decisions silently — every phase has an
explicit user-facing surface point.

---

## 3. The progression, phase by phase

### Phase A — single-leaf capability probe

Synthetic "warehouse toy system," `cavecrew-builder` sub-agent, seeded
faults (a brief contradicting the spec) across 3 leaves of increasing
scope: A1 (1 file, 200-line budget, control), A2 (2 files, 400-line
budget, 2x stretch), A3 (3 files + an embedded ambiguous-verb design
leak). A1/A2 both caught and escalated their seeded contradiction
correctly (7/7 and 11/11 tests). A3 refused outright before writing any
code, catching both seeded faults, and recommended splitting into 3
single-file leaves.

**Finding:** no leaf-capability ceiling found at this scale. Real
unplanned finding: `cavecrew-builder` has no Bash tool — every builder had
to manually trace test-vs-impl instead of actually running pytest, a
self-report risk the report's own author had to independently verify
against.

### Phase B — shard mechanism probe

1 overlord context, 2 shards × 2 leaves (4 total), fully concurrent.
Shard-A: `reporting.py`, `notifications.py`. Shard-B: `shipping.py`,
`shipping_rates.py`. All 4 passed (34/34 tests), zero cross-shard file
overlap. A cross-shard duplication probe (two leaves independently needing
to round a float) had both leaves make the same call with no visibility
into each other's work — but the report itself flags this as inconclusive,
since the shared need was trivial, not a real design decision.

**Feeds into Phase C:** test leaves at real 300-400 LOC scope (A2 only
used 10% of its budget); don't raise the 12/16 leaf cap yet; clarify who
executes tests, given A's Bash gap.

**Skill change between B and C:** `general-purpose` (Bash-enabled)
promoted to the default impl-leaf sub-agent type; `cavecrew-builder`
demoted to opt-in for genuinely trivial single-file leaves. This decision
still holds today (§2).

### Phase C — leaf-size ceiling sweep, and the arc's most important defect

New order-pricing domain, `general-purpose` agent (now Bash-enabled), 4
rungs of increasing scope:

| Rung | Files | Budget | Real LOC | Tests |
|---|---|---|---|---|
| C1 | 1 | 150 | 14 | 8/8 |
| C2 | 1 | 450 | 146 | 26/26 |
| C3 | 3 | 750 | 244 | 36/36 |
| C4 | 5 | 1300 | 345 | 60/60 |

All rungs' tests independently re-run by the report's author (not trusted
from self-report). Real LOC stayed well under budget even at C4 (26%
utilization).

**Two diverging ceilings.** Correctness never broke, even at C4 — it
self-caught and fixed a rounding mismatch itself via real pytest
execution, directly attributed to having Bash access. **Judgment quality
broke at C3**: given two contradictory canonical orderings with no stated
ground truth, the leaf did not escalate. Instead it kept each file
locally self-consistent — `discounts.stack_discounts()` implemented one
order, `engine.build_invoice()` implemented the other, and
`build_invoice` **never called `stack_discounts` at all** (confirmed by
grep — genuine dead code). All 36 tests still passed, because the tests
matched this same split resolution. The report calls this a worse outcome
than an outright bug, because it is silent and passes every check that
existed at the time.

This is the defect that motivated pillar 1 in §2 and the entire Phase D
skill change.

### Phase D — root cause, fix, and live re-verification

Root cause: C3's leaf wrote its own tests, which is not the skill's real
default (`test_owned_by: parent`). Five changes landed, synced to all
install locations:

1. **Shard test-writer role** — tests authored by a sub-agent independent
   of the implementing leaf.
2. **Mockist composition rule** — any leaf with 2+ impl_files now requires
   at least one interaction assertion (does the orchestrator actually call
   the collaborator?) alongside state checks. This is the specific rule
   that closes the C3 hole.
3. **G8 test-quality gate** (new `test_quality_gate.py`) — AST-based
   reachability check (blocks: flags unreachable top-level functions) plus
   a lite mutation check (advisory by default). Note: mutation testing
   alone would **not** have caught C3 — a function with its own direct
   unit test survives mutation regardless of whether anything else calls
   it. This was caught as a planning-stage correction before landing.
4. **Phase 3.4** — pre-spawn test-quality audit by a fresh-context
   sub-agent, before any leaf sees the tests.
5. **`check_no_contradiction()`** — a `check_invariants.py` heuristic
   flagging the same identifier bound to two different literal values
   across sibling briefs in the same wave.

A bug in the gate-building process itself: the first mutation-check
implementation used `Compare.col_offset` to locate operators, but that
offset points at the left operand, not the operator — every comparison
mutation silently no-op'd. Fixed by dropping comparison mutation, keeping
only reliable Constant-node mutations.

**Live re-verification, 3 independent runs of the same C3 shape,** through
the real updated pipeline end-to-end: 3/3 caught the contradiction
pre-impl this time, all forced to a single coherent, grep-confirmed
implementation. Honestly reported: `check_no_contradiction()` **never
actually fired** in any of the 3 runs — it only compares literals across
sibling briefs, and C3's defect was *within* one brief, outside its scope.
The **process change** (the composition rule forcing an interaction
assertion), not the mechanical check, is what carried the fix. Two more
real pre-existing `check_invariants.py` bugs were found and fixed along
the way (a schema bug rejecting legitimate plural-only file lists, and a
path-dedup bug in `_leaf_paths()`).

### Phase E — leaf-size ceiling, on the fixed process

Scaling file *count* (3→12 files) on the now-fixed Phase D process:
119→148 impl LOC, 19→66 tests, all pass across all 5 rungs (E1-E5).
Correctness held cleanly; real complexity strain, when it appeared, showed
up at the parent/test-authoring stage at the top rung, not the leaf/builder
stage. 3 live bugs found and fixed along the way (a brief-glob
false-positive, an `INTERACTION_HINTS` false-negative, a
`standalone_symbols` design gap).

One methodological lesson surfaced here, not a skill finding: this
phase's own memory record went stale mid-session (it kept describing
itself as an unstarted "resume point" after the work had actually
finished) — a general reminder to verify current state directly rather
than trust a memory file's own claim about where things stand.

### Phase F — the single-file scale axis, and cross-rung drift

Phase E only ever scaled file *count*; LOC stayed nearly flat, and
`test_quality_gate.py` literally no-ops below 2 impl_files — meaning a
single huge file was never gate-tested at all, regardless of size. Phase F
held `impl_files=1` and scaled total responsibility instead, scope-matched
to E1/E3/E5 as F1/F2/F3, same domain and seeded coupon-order
contradiction (restated intra-file).

| Rung | Scope | LOC/budget | Tests | Resolution |
|---|---|---|---|---|
| F1 | =E1 | 162/750 | 19/19 | coupon-last |
| F2 | =E3 | 194/1900 | 42/42 | coupon-**first** |
| F3 | =E5 | 291/3200 | 66/66 | coupon-last |

Correctness held cleanly again, no complexity-strain signal even at F3's
full 12-module scope.

**Headline finding: cross-rung contradiction drift.** F2's resolution is
the opposite order from F1/F3. Each rung explicitly cited its
scope-matched Phase E rung as precedent — and a direct grep of all 5 Phase
E rungs' actual code confirmed Phase E was never internally consistent
either: E1/E5 resolved coupon-last, E2/E3/E4 resolved coupon-first (3-of-5
majority is actually coupon-first). Every individual rung is
self-consistent — its own tests match its own impl — so nothing in the
pipeline caught this, because no gate or test compares one leaf's
resolution against another leaf's. **Same shape as C3**, but manifesting
*across* independently-run leaves instead of *within* one file. The
composition rule that fixed C3 only enforces intra-leaf consistency, never
inter-leaf.

### Skill redesign (Part 1) + Phase G — real 3-agent isolation

Phase 8 (a post-admission batch auditor) was removed entirely, replaced by
a strengthened Phase 3.4 (pre-impl, explicit context package,
goal-fidelity + umbrella-alignment + test-quality checks).
`manager-mode-hardcore` was rewritten to double the *pre-impl* audit
instead of running a post-admission review that no longer exists.

Phase G validated this under genuine 3-agent isolation — test-writer →
fresh auditor → builder, as three separate spawns with zero shared
context (unlike Phase F, where one agent played every role sequentially).
G1-G4, 220-1400 LOC budgets, 24-75% utilization (mean 46%), largest actual
file 339 LOC, zero unresolved defects.

Four findings:

1. **Pre-impl audit works as designed** — G1's fresh auditor caught a
   real defect: a coupon-order discriminating test landed on an exact
   floating-point `.xx5` rounding tie, meaning a wrong-order
   implementation could have passed it. Caught entirely before any
   builder existed; fixed via a new fresh test-writer spawn, re-confirmed
   by a new fresh auditor.
2. **Cross-rung drift is orthogonal to isolation quality** — the same
   3-of-4 G1/G3/G4-vs-G2 split showed up again. Real isolation didn't fix
   it, because it was never what isolation controls — each rung
   independently cited a different (already-inconsistent) Phase E
   precedent.
3. **A real, accepted gap in the pre-impl audit** — G3's builder caught an
   ordinary test-authoring bug (`threshold=1` should have included
   `stock=0` since `0 < 1`, but the test asserted it shouldn't) that
   **neither the test-writer nor G3's fresh auditor caught** — only the
   builder did, as a side effect of TDD's own RED/GREEN discipline, not a
   designed safety net. This is the concrete first instance of the gap
   flagged in advance when Phase 8 was removed; accepted as a tradeoff.
4. **Token cost** — isolation adds a real per-rung tax: 187k-262k
   tokens/rung (3-5 spawns), independent of scope. G1 (smallest scope, with
   one revision cycle) cost more than any single Phase E rung despite
   covering less — the isolation/coordination tax, not a scope effect.

### G9 complexity gate + cascade-scoped briefs + Phase H design

Recovered a dead-chat plan and implemented four pieces: **G9** (new
`complexity_gate.py`, AST-based cyclomatic-complexity and max-nesting
checks, runs on every leaf, advisory by default; caught and fixed its own
elif-nesting bug — Python represents `elif` as a nested `ast.If`, and the
naive walker mis-tracked it as false depth — before landing);
**cascade-scoped `briefs_dir`** (was a flat `.swarm/briefs/`, now
`.swarm/<cascade-slug>/briefs/`, slug auto-derived from the spec's name);
a wordiness-verdict on SKILL.md itself (no segmentation recommended — it's
a linear single-read procedure, splitting buys nothing token-wise since
leaves never read it directly); and **Phase H's design** (below).

### Phase H — the ceiling search, H1/H2/H3, done

Explicitly designed to push far past G4's scale and find where a single
large file actually breaks, in 3 deliberately wide-spread rungs (not G's
incremental steps): H1 (2200 LOC budget, 1.6x G4, a multi-tier
approval/authorization workflow), H2 (5000, 3.6x, promotional-campaign
stacking with its own seeded ambiguity), H3 (9000, 6.4x, regional
tax-jurisdiction cascading + refund/partial-cancellation reversal —
explicitly the rung designed to find where bookkeeping breaks). Same
isolation mechanics as Phase G throughout.

| Rung | Budget | Actual LOC | Utilization | Tests | Correction cycles |
|---|---|---|---|---|---|
| H1 | 2200 | 471 | 21.4% | 68/68 | 1 (audit FAIL→REVISE→PASS) |
| H2 | 5000 | 585 | 11.7% | 82/82 | 1 (audit FAIL→REVISE→PASS) |
| H3 | 9000 | 527 | 5.9% | 103/103 | 1 (builder-side, fixed same pass) |

All independently rerun via pytest directly against each rung's own
`src/`, all GREEN.

**Headline: the ceiling was never found.** LOC utilization actively
*fell* as budget grew (21% → 12% → 6%) while actual file size stayed
roughly flat (471/585/527 lines) — confirming G4's own hypothesis that
this domain's real complexity ceiling sits well below where these
experiments have been probing, even 6.4x further out than G4.

**H3's within-file consistency check** (its own addition to the
methodology — does a seeded ambiguity resolve identically at every call
site *inside the same file*, as opposed to cross-rung drift, which is
expected) found zero drift across all three carried-forward ambiguities
(coupon-order, currency-timing, campaign-order). `partial_refund` (H3's
own new logic) genuinely reverses composed effects — proportional share
via `total_qty`, tax reversed via `compute_tax`'s own logic, loyalty
credited back via `points_available` — rather than naively re-running
forward logic on a smaller quantity.

**Why the LOC stayed flat, traced by direct code inspection as a
follow-up investigation:** H3's brief anticipated genuine
state-bookkeeping complexity for the reversal logic — an
`order["applied_effects"]` ledger tracking what was applied and in what
order, so it could be replayed in reverse. The builder never built that,
because it didn't need to: every effect in this domain (coupon, campaign,
tax, loyalty) is a **linear, single-pass transformation** with no
path-dependence, so `partial_refund` correctly reduces to scaling the
already-computed final-state fields proportionally — arithmetic, not a
state-machine replay. H1→H2→H3 each added roughly the same real
structural surface (one registry + one-or-two functions), even though the
*task prose* and the *LOC budget* both grew much faster than that. The
task got harder-sounding faster than the domain got structurally harder.

**Practical implication, flagged, not yet acted on:** `playbook.md`'s
`impl_line_budget` (1000-1500 target, 2500 hard cap) looks generous, not
tight, relative to what a real single-concern domain needs — this domain
topped out around 530 real lines with 4 stacked layers of genuine business
logic.

### Allocation redesign — Phase 2 restructure + v1/v2 pilots

A separate thread, same period, aimed at a different question: not "how
big can a leaf get" but "is the overlord's own decomposition decision any
good." An early draft of the Phase 2.2 rubric leaned on estimating LOC
pre-impl as a sizing signal — rejected, because **LOC/complexity cannot be
measured before code exists; that's a guess wearing a number**. Replaced
with the 4-axis spec-text rubric that ships today (§2): rule-clusters,
exception branches, external integrations, cross-cutting concerns — all
countable directly from spec prose, no execution needed. A completeness
sweep was added to 2.2 (enumerate every requirement/invariant/open item,
confirm each owned or excluded), and delegation was extended from 2 legal
points to 3 (adding 2.2 itself).

**Pilot v1** (4 spawns — 2 on the CASH onboarding plan, 2 on switchboard's
TIER 0 — each overlord reading the plan directly and decomposing itself,
no delegation tested) found real coverage gaps: both CASH overlords
silently dropped the plan's own "Overarching Goal" section (marked
Critical twice, opens the document) and two explicitly-still-open P0
items — neither in the leaf list nor the exclusion list, unlike how
rigorously both overlords listed exclusion reasons elsewhere. One
switchboard overlord (of two) claimed a factually false "0 integrations"
for a layer that actually needed a second API endpoint, and never
addressed a 55-line campaign-examples section at all.

**Pilot v2** ran the actual delegate-then-audit shape the skill specifies
(v1 had the overlord do the whole read-and-decompose itself, which isn't
what the skill's Phase 2.6/3.4 pattern actually does): 2 spawns, one per
project, each playing a real overlord — read the plan, spawn its own
sub-agent to draft consolidation per 2.2, then run the completeness sweep
itself against the draft using its own retained context. **Zero
repeat-misses on either project** — every one of v1's known gaps was
either fixed outright or caught live by the sweep this time, not silently
dropped. New, smaller residual gaps were found instead (an item never
assigned to a leaf, a dangling unused endpoint, a cross-cutting rule
misfiled under a leaf with no surface to enforce it).

**Phase 2.2a**, the thread's final concrete addition, generalizes directly
from v2's own residual gaps into 6 fixed, project-agnostic questions run
after the completeness sweep (§2): consumption check, enforcement-surface
check, input/output coverage check (added at the user's own explicit
request, stricter than the enforcement-surface check — catches a leaf
that owns a general rule but drops one named exception value), sweep-table
completeness, open-item sweep, implied-duty restatement.

**Historical comparison** (checking whether real production cascades ever
hit this same gap class): no real cascade in either project ever
cold-decomposed a full plan doc — every real cascade (the review-gate
removal migration, the TODO fragility patch waves) worked from a small,
human-pre-distilled spec slice, sourced before Phase 2.1/2.2 existed. No
comparable leaf-list-vs-completeness-table artifact exists to
line-compare. What is real: the same gap *class* (framing-prose
invariants, buried open items) shows up repeatedly in actual production
incident history — the MONEY INC incident, three separate Direct Download
URL crash instances, an issues_log contract-loss bug, a PVC null bug — and
every one of those was caught **after admission**, via live execution,
never upfront, because no upfront check existed before this redesign. The
correct framing is "no check existed → ship-and-discover" becoming "a
pre-impl check now exists and catches that gap class" — not a claim that
2.2a would have retroactively prevented any specific historical incident.

**Effort-level exploration**, researched but not applied: subagents
inherit the parent session's `effortLevel` by default; a per-agent-
definition `effort:` frontmatter field can override it; there is no
per-spawn override on the Agent tool itself (unlike `model`). The default
impl-leaf agent, `general-purpose`, is harness-built-in with no local
definition file, so it has no frontmatter surface to pin effort on — it
will always inherit the overlord's session effort. The user's own
resolution: skip the split, run the whole overlord session at `high`, let
every subagent inherit it.

---

## 4. Threads still open

- **No breaking point ever found for single-large-file TDD leaves.**
  Phase H's own recommendation: a real ceiling search would need either a
  genuinely different (not just bigger) domain, or accepting that this
  class of layered-business-logic domain may not break at any LOC count
  it can realistically reach.
- **G9's thresholds (cyclomatic 10, nesting 3) remain uncalibrated.**
  Phase H running did not end up validating them — `complexity_gate.py`
  was never actually run against H1/H2/H3's own output in this pass.
- **`impl_line_budget` calibration** — H3's finding (§3) suggests
  `playbook.md`'s current 1000-1500/2500 numbers may be generous relative
  to real single-concern domains, but this is flagged from one domain, not
  acted on as a general change.
- **No Phase I scoped.** Nothing currently planned past H3.

---

## 5. Sources

| Artifact | Covers |
|---|---|
| `experiments/scaling-test/REPORT.md` | Phases A–E, full raw data |
| `experiments/scaling-test/phaseF-single-file-scale/` | Phase F rungs + SPEC.md |
| `experiments/scaling-test/phaseG-isolated-single-file/REPORT.md` | Phase G rungs + findings |
| `experiments/scaling-test/phaseH-ceiling-search/REPORT.md` | Phase H rungs + findings (this session) |
| `experiments/overlord-allocation-redesign/COMPLEXITY-RESEARCH.md` | Why no pre-code LOC/complexity metric exists |
| `experiments/overlord-allocation-redesign/TEST-DESIGN.md`, `ALLOCATION-PILOT.md` | Pilot v1 design + results |
| `experiments/overlord-allocation-redesign/TEST-DESIGN-v2.md`, `ALLOCATION-PILOT-v2-CASH.md`, `ALLOCATION-PILOT-v2-SWITCHBOARD.md` | Pilot v2 design + results |
| `experiments/overlord-allocation-redesign/HISTORICAL-VS-V2-COMPARISON.md` | Real-cascade comparison |
| `skills/manager-mode/SKILL.md` | Current skill behavior, source of truth |
| `skills/swarm-shared/references/playbook.md` | Sizing section, `impl_line_budget` |
| `skills/swarm-shared/scripts/check_invariants.py`, `test_quality_gate.py`, `complexity_gate.py` | G-gate implementations |
