# DRAFT v3 — overlord task-allocation redesign + shard-necessity pilot

Not yet applied. v3 changes: replaced pre-impl LOC/complexity guessing
with a read-only spec-text rubric (research pass, sources in Part 1);
LOC now only appears where it's actually measurable (existing files, 2.4)
or as a post-decision ceiling (playbook.md budget), never as a
new-work estimate. Trimmed old-version references out of text destined
for SKILL.md itself.

Two standing pillars, unchanged: authorship separation (test-writer ≠
builder, always), fresh-adversarial-audit + overlord-side goal
reconciliation (never delegated).

---

## Part 1 — Phase 2 edits (SKILL.md)

Six sections total (was five): 2.1 unchanged, new 2.2 inserted, 2.2-2.5
shift to 2.3-2.6.

### 2.1 — unchanged

File-independence dependency map. The actual race-condition safety
mechanism. Consolidation (2.2) only merges slices 2.1 already proved
don't collide — can't reintroduce a collision by definition.

### 2.2 — Consolidation pass (NEW, rubric-based, no LOC guess)

**Why not LOC**: LOC/complexity can't be measured before code exists —
an estimate here is a guess wearing a number. Research pass found no
established method sizes LLM-agent work this way; the useful move
COSMIC Function Points make is counting discrete elements *readable in
the spec itself*, just on the wrong axis for this problem. Full research
report: `experiments/overlord-allocation-redesign/COMPLEXITY-RESEARCH.md`.

```
### 2.2 Consolidation pass

2.1 finds the max-safe leaf count. That's not the leaf count to use.
Before assigning slices 1:1 to leaves, score each candidate by four
things countable directly in the spec text — not a LOC guess:

- **Rule-clusters** — distinct decision rules/branches (validation
  gates, default-with-override tables; count table rows directly).
- **Exception branches** — numbered exception/edge-case sections.
- **External integrations** — distinct third-party systems touched
  (webhook, API, storage, email, print, etc).
- **Cross-cutting concerns** — things re-applied consistently across
  multiple rule-clusters (audit logging, tiered gates, redaction). The
  dangerous axis — a leaf can satisfy every individual rule and still
  violate the cross-cutting one.

One leaf, one coherent unit, when: ≤1 cross-cutting concern spans it,
≤2-3 external integrations, and its rule-clusters share one failure
domain (a wrong assumption in one can't silently corrupt another's
output).

Past that: split along the cross-cutting-concern or integration
boundary first, not by rule count — that's where compositional bugs
live. A spec section amended after a real incident counts as an added
cross-cutting concern on whatever it touches — that's evidence of
hidden coupling already found once.

c.f. `experiments/scaling-test/phaseH-ceiling-search/`: one leaf held 6
composed concerns across 585 LOC, zero degradation. Composition was the
limiter, never LOC — this rubric targets composition directly.
```

### 2.3 — Task-size guardrail (was 2.2)

```
### 2.3 Task-size guardrail

Count planned leaves, after 2.2:

- **≤ 16:** proceed.
- **> 16:** refuse. Re-scope, or split into sequential waves.

Hard backstop, not a nudge — 2.2 is what keeps leaf count low.
```

### 2.4 — Fat-file check (was 2.3) — LOC valid here, file already exists

```
### 2.4 Fat-file check (only if some impl files exist)

Unlike 2.2, this file already exists — its LOC is real, not a guess.
Estimate resulting LOC (current + new work this wave adds). Target
1000-1500. Past 2500 — provisional, pending validation beyond H2's
tested 585-LOC ceiling — flag the user for review, do not continue
silently. Same two options as before: sequential waves, or a prep-step
file split.

Multiple ACs in one file is not itself a reason to split — 2.2 may put
them in one leaf on purpose.
```

### 2.5 — Emit briefs (was 2.4) — unchanged, renumber only
### 2.6 — Write per-leaf failing tests (was 2.5) — unchanged, renumber only

### Cross-references to fix elsewhere in SKILL.md

- Line 229/237: `(2.5)` → `(2.6)`
- Line 573: `(2.4)` → `(2.5)`
- Line 593-597 "Task-size discipline": rewrite tight —
  ```
  ## Task-size discipline

  Phase 2.3 refuses past 16 leaves — drift between siblings, context
  fill, missed cross-leaf contradictions. Phase 2.2's consolidation pass
  is what should keep most waves well under this; a wave still near 16
  after honest consolidation judgment likely needs re-scoping, not a
  bigger cap.

  Past 16 even after consolidation: split into sequential waves
  (`wave:` field sequences cross-wave file edits). The >16 refusal is
  non-negotiable — push-past decisions belong upstream, at the spec.
  ```
- Line 608: `≤12/warn-13–16/refuse->16` → `refuse->16`

### playbook.md Sizing section — LOC as post-decision ceiling only

`impl_line_budget` stops being a sizing tool and becomes a ceiling set
*after* 2.2's rubric decides one leaf is coherent — same relationship
G9 already has to actual complexity (measured post-decision, never
predicted). Replace current default (200 — predates all evidence, and
conflicts with the new ceiling if left in place) with 1000, matching
2.4's target floor:

```
- **Impl line budget** (default 1000, configurable per-brief) — a
  ceiling on a leaf 2.2 already judged coherent, not a sizing input.
  Raise toward 1500 as needed; past 2500 (2.4) is a hard stop requiring
  explicit user confirmation. All three numbers provisional pending
  validation beyond H2's tested 585-LOC ceiling.
```

Also update `skills/swarm-shared/templates/.claude-swarm.toml.example`'s
`max_impl_lines = 200` → `1000` to match.

---

## Part 2 — Shard-necessity pilot, ≤4 spawns, existence-proof only

**Not a comparison.** E1 (Phase E's old multi-leaf baseline) isn't a
valid control: predates the Phase 8→3.4 audit redesign, almost certainly
wasn't genuinely isolated (same flaw Phase G was built to fix in Phase
F), and no matched multi-leaf run exists under the current pipeline to
compare against. A real A/B needs a matched-pipeline multi-leaf run —
separate, larger-budget work, not this pass.

This pilot answers one narrower question: does the new consolidated
model, allocated via 2.2's rubric instead of a LOC guess, produce
correct, audit-clean, G9-clean output at multi-AC scope, at all. A first
data point, not a verdict.

**Spec**: pick a spec section from the order-pricing domain family that
scores as one coherent leaf under 2.2's rubric (≤1 cross-cutting
concern, ≤2-3 integrations, one failure domain) — this pilot doubles as
the rubric's first real application, not just a LOC choice.

**Spawns (≤4)**:
1. Test-writer — full scope, one test file.
2. Fresh auditor — adversarial, pre-impl.
3. Builder — implements to GREEN.
4. Contingent — only if audit round 1 fails (H1/H2 both needed one revise).

**Verify independently, same discipline as H1/H2**: rerun tests directly,
grep resolved ambiguities in real impl, recompute at least one
discriminating number by hand.

**Measure**: LOC/utilization against the 1000-1500-2500 scale (recorded
after the fact, not predicted), G9 result, defect count caught pre-impl,
within-file consistency across the merged ACs. No token-cost comparison
claim — report the raw number, don't frame it against anything
historical.

**Output**: short note, `experiments/overlord-allocation-redesign/PILOT.md`
— numbers + a plain verdict on whether this is worth a real, larger,
matched comparison next.
