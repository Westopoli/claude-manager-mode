# Overlord-allocation pilot v2 — tests the real delegate-then-audit shape

v1's flaw: had the overlord itself do the whole decomposition read directly.
That's not what the skill actually does — Phase 2.6 delegates test-writing to
a sub-agent and Phase 3.4 has a fresh auditor check it; the overlord's real
job is holding the full plan/goal in its own context and auditing delegated
output against it, never producing all the detail itself. v1 tested "can an
agent read a plan well," not "does the delegate-then-audit discipline catch
what a single first-pass read misses" — which is the actual thing v1's own
results (real gaps, on both projects) showed matters.

This version tests the real shape, now that Phase 2.2 delegation and the
completeness sweep are actually authorized in SKILL.md (both added this
session, in response to v1's findings).

## Method

**2 spawns total**, one per project. Each spawn plays the overlord role in
full, for real — it is explicitly instructed to:

1. Read the full plan (CASH: whole doc; switchboard: TIER 0 §1 only, same
   scope as v1) and current SKILL.md Phase 2 (2.1-2.6) + the "Delegated
   drafting passes" section.
2. Per 2.2, spawn exactly one fresh sub-agent to draft the consolidation
   grouping — the sub-agent gets the plan text and the rubric, nothing else
   (no memory of this instruction, no visibility into what the overlord
   already knows about the exercise).
3. Receive the sub-agent's draft leaf list back.
4. Run 2.2's completeness sweep itself, by hand, against the full plan text
   it (the overlord) still holds in its own context — the sub-agent's draft
   doesn't share that context, so this step is where a missed requirement
   either gets caught or doesn't.
5. Produce a final leaf list (adopting, correcting, or overriding the
   sub-agent's draft) plus an explicit log of what the completeness sweep
   found: items the draft missed, items it got wrong, items confirmed
   covered.

Same repo-access restriction as v1 (plan file only, no `src/`, `.swarm/`,
git history) — for both the overlord and its spawned sub-agent.

## What this measures that v1 couldn't

v1 already gave us the failure catalog to check against — real, confirmed
misses:
- CASH: the "Overarching Goal" section, §0 assumptions table, §19 Items 5/6
  (both explicitly still-open) never traced to a leaf or an exclusion.
- Switchboard: one run missed Layer 7's second Calimatic endpoint and never
  addressed the Campaign-Examples/Cross-Sell section at all.

**Scoring**: for each project, does the overlord's completeness sweep catch
any of that project's known v1 misses in the sub-agent's draft? A catch
means the discipline (delegate, then independently audit against retained
context) does what it's supposed to. A miss repeated means either the sweep
instruction itself needs sharpening, or completeness-checking against a
long prose spec is a harder problem than one wording fix solves — a real,
useful negative result either way, not a wasted run.

Also log, same as v1: did the sub-agent's draft show any of the same
mis-reads v1's direct runs showed (wrong endpoint counts, silently skipped
sections)? That's the delegation-risk side — a sub-agent's first draft
should be expected to have gaps; the question is only whether the overlord
catches them.

## Output

`experiments/overlord-allocation-redesign/ALLOCATION-PILOT-v2.md` — per
project: the sub-agent's draft (or a summary if long), the overlord's
completeness-sweep log, the final leaf list, and an explicit
caught/missed tally against v1's known gaps for that project.
