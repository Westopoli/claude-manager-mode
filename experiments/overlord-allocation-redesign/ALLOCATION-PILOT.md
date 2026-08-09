# Overlord-allocation pilot — results

4 spawns run (2 CASH, 2 switchboard TIER 0), read-only, allocation-only.
Full outputs: `cash-overlord-{1,2}.md`, `switchboard-overlord-{1,2}.md`.

## Ground-truth comparison: hit a real structural dead end, reporting honestly

Checked three candidate ground-truth sources before writing this up:

1. **CASH `n8n_flow`** (7 leaves, one-line-per-leaf granularity) — wrong
   spec entirely (`specs/cash_flow_n8n_workflow.md`, a pre-v3 document)
   and pre-dates this redesign's whole philosophy (old one-function-per-leaf
   default). Not usable.
2. **Switchboard `sprint-1-10`** (4 leaves, real briefs A-D) — wrong spec
   too (`docs/specs/active/sprint-1.8-phase3-pg-cron-scheduler.md`, the
   pg_cron scheduling infrastructure, not TIER 0's tag-derivation logic).
   Not usable.
3. **CASH `review_gate_removal`** (2 leaves) — its spec_file is yet
   another derived doc (`specs/cash_flow_review_gate_removal.md`);
   `CASH_Project_Plan.md` only appears in `do_not_edit` (parent-owned
   reference), never as the actual thing cascaded.

**Finding, not a pilot failure**: grepped both projects' entire `.swarm/`
history for any cascade whose `spec_file` was the top-level plan document
itself. Zero hits, either project. Every real cascade in both projects'
history worked from a narrower, already-decomposed spec — never the
original high-level plan. That's real information about how this skill
actually gets used in practice (someone always writes a narrower spec
first), but it means this pilot's original premise — "compare against
what got built from this document" — has no clean target for either
project as originally scoped. Finding a valid comparison would mean
reconstructing which derived-spec sections trace back to which plan
sections across dozens of waves, which is bigger than a 4-spawn pilot.

## What the pilot actually measured instead

Two things that don't need repo ground truth: cross-spawn agreement (same
shape as the coupon-order measurement in G/H), and whether each spawn's
rubric application is internally sound against the plan text alone.

### CASH — 9 leaves (overlord-1) vs 7 leaves (overlord-2)

Both independently converged on the same 5 core groupings: an
ingest/gate cluster (envelope + idempotency + normalize, citing the
plan's own §20 Stage-A table), Dropbox chain, Sheets write, Printing, and
Apps Script plugin as its own leaf (correctly identified as a separate
runtime/repo surface with zero shared footprint — neither spawn missed
this). Both independently cited the plan's own §20 text ("no clean
parallel-safe seams") as justification for keeping orchestration a single
large leaf rather than splitting it — a real instance of the rubric
picking up an explicit textual admission in the spec and using it
correctly as a cross-cutting-concern signal, not something either spawn
had to be told to look for.

Where they diverge: overlord-1 keeps severity-collapse and Day-1-init as
separate leaves (9 total); overlord-2 folds severity-collapse into
orchestration and Day-1-init into routing (7 total). Both directions are
defensible — the disagreement is exactly how tightly "one failure domain"
gets drawn at the margins, not a rubric miss on either side.

### Switchboard TIER 0 — 8 leaves (overlord-1) vs 7 leaves (overlord-2)

Both converged on treating the tag-diff/stale-removal reconciler as its
own leaf, independently naming it the rubric's "dangerous axis" (the one
true cross-cutting concern spanning every tag layer) — same pattern as
CASH's orchestration convergence, different project, same rubric
behavior.

Real divergence worth flagging: overlord-2 caught that Layer 7 (status
tags) needs a *second* Calimatic endpoint (`GetAllStudentUnenrollments`)
beyond the four listed at the top of the section, and gave it its own
leaf on that basis. Overlord-1 folded Layer 7 into the same leaf as
Layers 1/2/3/4/6 without flagging the extra endpoint. This isn't a
defensible-either-way split — it's one spawn correctly applying the
external-integration axis to something the other missed. First concrete
evidence the rubric's quality depends on how carefully a given spawn
reads the full spec, not just on the rubric's own design.

## Verdict

The rubric behaves sanely on real prose it wasn't designed around — both
projects, both spawns each, leaf counts stayed reasonable (7-9), and the
two most interesting outputs (CASH's orchestration leaf, switchboard's
diff-reconciler leaf) both came from the rubric correctly reading the
spec's own explicit structure rather than imposing an external one.

Two real, useful findings, neither of them "the rubric is broken":

1. **Real ground truth for this kind of test doesn't exist yet in either
   project** — every real cascade works from a derived spec, not the
   top-level plan. A follow-up wanting genuine plan-vs-built scoring needs
   either a project where someone cascaded the top-level doc directly, or
   a live-forward test (run a real cascade from a plan now, compare after
   the fact — expensive, but clean).
2. **Missed-integration risk is real and spawn-dependent, not rubric-
   dependent** — switchboard's Layer 7 divergence shows the failure mode
   isn't the four-axis rubric itself, it's whether a given read caught
   every integration mentioned in the text. Worth a note in 2.2's actual
   wording: explicitly re-scan for integration mentions before finalizing
   the external-integration count, don't rely on catching them in a first
   pass.
