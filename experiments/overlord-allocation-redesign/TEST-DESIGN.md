# Overlord-allocation test — does the rubric size real specs well?

Tests Phase 2.1-2.4 (dependency map, consolidation pass, task-size
guardrail, fat-file check) in isolation: read a real project plan, produce
an allocation (leaf count + consolidation rationale), stop. No Phase 4+ —
no leaf/test-writer/builder/auditor spawns, no code written. Scored against
what was actually built.

## Why these two projects

Both are real specs this session has direct grounding in, not synthetic
domains — the whole point is testing the rubric on prose it wasn't
designed around (business-rule specs, not clean function signatures).

- **CASH** (`leandrc49/Kowski-Ventures/docs/CASH_Project_Plan.md`) — one
  self-contained pipeline (webhook → routing → 4 parallel actions), single
  cascade. Ground truth: `leandrc49/src/cash_flow/` (~20 real modules),
  `leandrc49/.swarm/` (real wave briefs/sweeps/snapshots).
- **Switchboard, TIER 0 only** (`switchboard/docs/reference/_source-strategy-doc.md`,
  lines 67-295, "Class Roster Sync → Niche Email Campaigns"). The full doc
  (21 strategies, 6 tiers) is confirmed too large for one cascade — its own
  `.swarm/` history shows dozens of separate named waves built over months
  (sprint-1 through sprint-10, family-student-objects, belt-tags,
  pickup-sheets, etc.), not one cascade. TIER 0 alone is comparable in
  scope to CASH's whole plan and has real matching ground truth: `.swarm/sprint-1-10/briefs/leaf-{A,B,C,D}.md`
  (4 real leaves, `sprint-1-10.SWEEP.md`).

## Method

**4 spawns total** (2 fresh overlord runs × 2 projects). Each spawn:
read-only. Receives the plan file (or TIER 0 excerpt), the target repo
path, and current SKILL.md Phase 2 (2.1-2.4) verbatim. Executes 2.1
(dependency map, textual — no `graphify_cmd` run, just reasoning about
which pieces would touch which files), 2.2 (consolidation pass, the
rubric), 2.3 (leaf-count guardrail), 2.4 (fat-file check, skipped — no
impl files exist yet for either target). Explicitly told: do not read
`src/`, `.swarm/`, or git history of the target repo — an overlord sizing
a brand-new spec wouldn't have that. Output: a leaf list, each with what's
consolidated into it and the one-sentence rubric justification (2.2's own
required format). Stops there. Two independent spawns per project, no
shared context between them (same isolation discipline as every prior
phase) — cross-spawn agreement is itself a signal, same as the
coupon-order measurement in G/H.

**Ground-truth comparison** (done by me, not a spawn): after both
allocations exist for a project, read the real `src/`/`.swarm/` history
and compare each proposed leaf's boundary against what actually shipped.

## Scoring

Per proposed leaf, one of:
- **Match** — real code has a corresponding coherent unit (one file/module,
  or one real leaf brief) at roughly that boundary.
- **Divergent** — real code split what the overlord consolidated, or
  merged what it split.
- **Excluded** — real code's boundary doesn't trace to anything in the
  plan document itself (a later undocumented change, a refactor, scope
  added after the plan was written). Per your instruction: this does not
  count against the overlord. Flag it and move on — the overlord is
  scored on fidelity to the plan, not on predicting unwritten changes.

For each Divergent, note whether the overlord's rubric reasoning was
still sound given only the plan text (a defensible read that reality
happened to depart from) or actually missed something visible in the
plan itself (a real miss). Only the latter counts as a rubric failure.

**Cross-spawn agreement** (per project, both overlords): did they reach
the same leaf count / same consolidation boundaries independently? Same
measurement shape as the coupon-order contradiction in G/H — agreement
under real isolation is itself evidence, disagreement isn't automatically
a failure (Phase G's Finding 2: cross-run drift is a separate, expected
phenomenon, not proof either run is wrong).

## Output

`experiments/overlord-allocation-redesign/ALLOCATION-PILOT.md` — one
table per project (proposed leaves × match/divergent/excluded), the two
spawns' leaf-count agreement, and a plain verdict: does the rubric produce
sane allocations on real prose, where does it diverge from reality and
why, is a real miss visible anywhere.
