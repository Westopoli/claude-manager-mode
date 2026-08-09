# Historical (pre-redesign) manager-mode cascades vs. v2 pilot — real evidence check

## What real historical material exists

Checked `leandrc49/.swarm/` (30+ named cascades) and `switchboard/.swarm/` (40+). Found the two
cascades memory pointed at:

- **`review_gate_removal`** (2 leaves) — `.swarm/review_gate_removal/briefs/leaf-01.md`,
  `leaf-02.md`. `spec_lines: 8-8` / `9-9`, `impl_line_budget: 5` / `3`. Each leaf is a single-line
  ternary/condition change against a narrow purpose-written `specs/cash_flow_review_gate_removal.md`,
  not the 611-line `CASH_Project_Plan.md`.
- **TODO fragility patch (Units A-D + step7_harden)** — waves 1-3, `post-review-log.md` shows
  5 leaves total, each `+3` to `+8` line deltas, each scoped to one function/one file. The
  decomposition source is `TODO.md`'s own "Priority plan" section — hand-written by a human/overlord
  directly (explicit ordering rationale, batching-by-shared-mutable-state rules, a numbered sequence),
  not produced by any Phase 2.1/2.2 mechanism, because neither existed yet.

**No historical cascade decomposed the full plan doc the way the v1/v2 pilots did.** Every real
cascade found works from a small, pre-distilled, human-curated spec slice (matches what v1 already
found via `.swarm/` grep: nobody cascades the master doc directly). This is the same dead end v1 hit,
confirmed again here.

## Direct contrast

Because no historical decomposition ever ran the "read a large spec cold, produce a leaf list"
exercise, there's no old artifact with a leaf list + completeness table to check the same failure
pattern (framing sections dropped, open items unassigned, cross-cutting misassignment) against
line-by-line. The comparison the prompt asks for cannot be made on decomposition artifacts — they
aren't the same kind of object.

What **can** be compared honestly: whether gaps of that general class occurred in real production
history, pre-redesign, and how they were caught. Answer: yes, repeatedly, and every one was caught
**after** admission via live execution, not before it — because no upfront completeness-sweep step
existed pre-redesign:

- MONEY INC incident (generic `REVIEW_REQUIRED` email gap) — found live, not upfront.
- 3 separate "Direct Download URL" crash instances — found one at a time, over multiple waves, not
  caught together upfront (`review_gate_removal` leaf-01 is literally patching the 3rd instance).
- `issues_log` contract-loss bug (`cash.contract` wiped by DataTable insert) — found live via execution
  1454, not in any decomposition step.
- PVC build-row null bug (fast-path skipped header-read) — found live via executions 1466/1467.

`TODO.md`'s own "Known gaps found during live verification (2026-08-06)" section is itself an
admission of this pattern: real, still-open, explicitly-flagged gaps (`DROPBOX_FOLDER_SPLIT` token-loss
blind spot) discovered *after* code shipped, sitting in exactly the kind of prose/framing location
(a paragraph, not a table row) that v1's CASH misses (Overarching Goal, §19 Items 5/6) and v2's residual
gaps (CASH testing-methodology invariant) also targeted.

## Verdict

Pre-redesign overlords never had a comparable completeness-sweep artifact to fail at — the real
gap-catching mechanism in practice was "ship it, find out live." The v1/v2 pilots' contribution is
moving that discovery earlier (pre-impl, from spec text) rather than later (post-admission, from
production incidents). That's a categorically different failure mode than "same gap pattern, caught
later" — it's "no upfront check existed at all, so nothing failed at it; now one exists and it works."

## Evidence quality caveat

This is not a controlled before/after on the same task. Historical cascades are real production
work at a different (much narrower) scope than the pilots' whole-plan-doc decomposition test, so the
comparison is necessarily qualitative (mechanism existed vs. didn't; caught pre-impl vs. caught live),
not a matched leaf-count or gap-count comparison. Don't cite this as "v2 fixed N historical gaps" —
it didn't fix any of the four listed bugs after the fact; it demonstrates the class of gap those bugs
represent is now checked for before code exists, where before it wasn't checked for at all.
