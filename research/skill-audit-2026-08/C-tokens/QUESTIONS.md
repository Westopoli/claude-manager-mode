# Token questions — answered from `out/*.csv` only

Source: `out/agents.csv` (716 agents, deduped by `message.id`; naive sum would over-count ×1.95 — see `SUMMARY.md`). All figures below are token counts, not dollars, unless labeled `$`.

## Q1 — Per-role distributions (fresh = input + cache_write; billed cache_read ≈ 10% of fresh rate)

| role | n | fresh_med | fresh_p90 | cache_read_med | output_med |
|---|---|---|---|---|---|
| leaf | 112 | 39,779 | 140,297 | 395,106 | 7,059 |
| experiment-leaf | 27 | 55,190 | 123,124 | 716,976 | 17,675 |
| test-fixer | 16 | 57,375 | 119,936 | 784,726 | 12,531 |
| shard-test-writer | 36 | 68,415 | 145,486 | 828,160 | 20,626 |
| test-auditor | 55 | 74,799 | 150,829 | 827,835 | 15,143 |

Ordering by fresh tokens: **auditor > writer > fixer > leaf** — matches the payload analysis in the plan (auditor's `TEST-AUDIT-BRIEF.md` is contractually un-trimmable; writer holds the whole shard's brief set + `test-design.md`). Every role's cache-read median is **~10× its fresh median** — the dominant per-agent cost, even discounted to ~10% of face value, is *re-reading the same cached prefix*, not the fresh payload the skill authors control most directly.

## Q2 — First-turn payload by role (= what the skill actually fed, before any codebase reading)

| role | n | median chars | max chars |
|---|---|---|---|
| leaf | 112 | 2,567 | 9,522 |
| test-auditor | 55 | 3,547 | 7,749 |
| test-fixer | 16 | 4,951 | 7,139 |
| shard-test-writer | 36 | 5,481 | 12,776 |

Writer's median first-turn payload (5.5k chars) is 2.1× the leaf's — consistent with SKILL.md's own claim that the writer holds "the shard's entire brief set *and* every impl file its tests target" before writing a line. Auditor's *first-turn* payload is smaller than expected relative to its fresh-token lead in Q1 — its cost comes from what it reads via tool calls after the first turn (the audit-brief file), not from the initial prompt. Confirms: auditor cost lever is the audit-brief content, not the framing prompt.

## Q3 — Cache-read per turn for leaves (is the system prompt/skill doc the dominant cost?)

Leaf median cache-read (395k) over a leaf's typical turn count (see `by_role.csv`, leaf turns_med) is consistent with the skill's own SKILL.md (~19k tokens) plus brief-template boilerplate plus prior-turn history being re-sent as cached context on every turn. This is corpus evidence *for* the Phase-G diagnosis quoted in the plan ("each fresh context re-reads the same contract excerpts, brief, and domain spec from scratch") — cache-read, while cheap per-token, is 10× the fresh volume, so a 10% saving there is worth more in absolute terms than most fresh-side trims.

## Q4 — Turns/tool calls vs leaf outcome

Deferred to Track B join (`out/cascades.csv` × `agents.csv` by cascade+leaf) — not yet done; flagged as **needs-experiment-or-join** in `D-experiments/knob-map.md` rather than answered here from CSVs alone, since the join key (leaf id) isn't reliably present on every row (`cascade`/`wave` extraction succeeded for a subset — see `SUMMARY.md`'s "Cascade roles by project" table, which is visibly partial).

## Q5 — Fixer spawns per audit finding

16 test-fixer agents total vs several hundred findings across the audited cascades (`B-test-audit/out/findings.csv`) — fixers are batched (SKILL.md 3.4.3: "fresh, per finding" is the rule but real cascades clearly batch multiple findings per fixer spawn, based on volume alone). Exact per-cascade ratio needs the B×C join noted in Q4.

## Q6 — Retry loops (same session + same description spawned >1×)

**8 (session, description) pairs** spawned more than once in the same session:
`Research software effect on agency valuation` ×2, `S15 terminal review and DB load` ×2, `S10 notes rail calculators UI` ×2, `S16 Haiku pass driver` ×2, `Lane B batch tabs` ×2, `Build formula/O-group prep states` ×2, `Lane B batch formulas` ×2, `Write wave-2 listener tests` ×2.

None of these descriptions match the manager-mode role regex (they're from non-cascade projects — plugin-QA lanes, a valuation research session). **No manager-mode-role retry loop appears in this corpus** — i.e. no evidence here of a leaf, writer, or auditor being re-spawned with the identical description within one session. This is a *negative* result worth flagging: either retries genuinely don't happen in these cascades, or a retry gets a *different* description each time (e.g. "leaf-03 retry" vs "leaf-03") and so isn't caught by exact-match — a real limitation of this detection method, noted in `SUMMARY.md`.

## Q7 — Opus vs Sonnet, same role (real cross-model data, not a controlled experiment)

| role | Opus n | Opus fresh_med | Opus out_med | Sonnet n | Sonnet fresh_med | Sonnet out_med |
|---|---|---|---|---|---|---|
| shard-test-writer | 13 | 105,945 | 31,720 | 23 | 58,792 | 10,101 |
| test-auditor | 9 | 114,276 | 22,622 | 36 | 74,920 | 13,835 |
| test-fixer | 2 | 77,731 | 18,127 | 14 | 57,375 | 12,531 |
| leaf | 3 | 45,833 | 8,277 | 107 | 39,779 | 7,059 |

For the two roles with enough Opus samples to mean anything (writer, auditor): Opus runs **~1.5–1.8× the fresh tokens and ~1.6–3.1× the output tokens** of Sonnet on the same role. This is **confounded** — different projects/cascades chose the model, not a controlled A/B — but it is directional evidence against "Opus writes tighter/shorter" and toward "Opus writes more, not just better," which matters for the plan's open question (N× Sonnet vs 1× Opus). Leaf's 3 Opus samples are too few to read anything into.

## Decision rule applied (per `00-DECISIONS.md` / plan Track C3)

| Question | Status |
|---|---|
| Q1–Q3, Q6, Q7 | **Answered from corpus.** Recorded in `00-DECISIONS.md`. |
| Q4 (turns/tool-calls vs outcome), Q5 (fixer:finding ratio) | **Needs the B×C join** (leaf-level, not just role-level) — not a knob-variation gap, just an unfinished join. Listed as a TODO in `D-experiments/knob-map.md`, not as "needs-experiment": no new tokens need to be spent, only more script work against data already collected. |
| "N×Sonnet vs 1×Opus for writer/auditor" (the plan's headline open question) | **Confounded in the corpus** (Q7) — real signal exists but model choice correlates with project/cascade, not randomized. This is the one item that graduates to `D-experiments/design.md` as `needs-experiment`. |
