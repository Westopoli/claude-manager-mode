# Overlord token accounting — Step A of `read-fidnings-of-manager-mode-bubbly-crown.md`

Extends `mine_transcripts.py` to walk main-session `.jsonl` files (not just
`subagents/agent-*.jsonl`), classify a session as an **overlord** when it
contains a `Skill` call for `manager-mode`/`manager-mode-hardcore` (strong
signal) or ≥2 `Task` spawns whose description matches a cascade role
(`task_count` fallback), and join each overlord to its own subagents by
`(project, session)` — the same key `mine_agent` already writes per
subagent row. Outputs: `out/sessions.csv` (15 rows), `out/by_cascade_total.csv`
(15 rows, one per cascade run). 8/8 unit tests green (3 new: skill-trigger,
task-count-trigger, false-positive-guard on a single unrelated Task call).

## Headline

| | overlord | subagents | total |
|---|---|---|---|
| $ across 15 real cascades | **$406.75** | $112.59 | $519.34 |
| share of $ | **78.3%** | 21.7% | |

Median per-cascade overlord share: **85.1%**. Range 47.5%–98.3%; the two
low outliers (47.5%, 56.6%) are the two costliest cascades in absolute
subagent $ (Fable-5/Opus-5 writer+auditor runs with 16 and 10 subagents),
not cases where the overlord was cheap.

F1 confirmed directly, not just inferred from the corpus-wide 4.56B/209
figure: **on a per-cascade basis the overlord is 3-4x the subagent cost**,
consistently, across projects (iCodeETL, switchboard, the-best-salesmen)
and overlord models (Sonnet 5, Sonnet 4.6, Opus 5, Fable 5).

## Is overlord cache-read dominated by SKILL.md or by accumulated tool output?

This decides whether K37 (context diet: script-summarized gate/audit output)
or raw SKILL.md prose size is the right lever.

Traced `cache_read_input_tokens` per assistant turn across the largest
overlord session (1f04066d…, Sonnet 5, 568 turns, 267.9M total cache-read):

| turn percentile | cache-read tokens at that turn |
|---|---|
| 0% (first) | 0 |
| 10% | 131,580 |
| 25% | 232,671 |
| 50% | 519,396 |
| 75% | 728,014 |
| 90% | 829,890 |
| 99% | 873,455 |

SKILL.md is ~20k tokens. By turn 10%, the prefix is already 6-7x that and
it keeps climbing near-monotonically through 99% of the session. **The
prefix is dominated by accumulated tool output (gate results, rendered
verbatim test/spec text, audit briefs written back into context), not by
the fixed SKILL.md text** — confirms F1/F6 and settles the question the
plan raised: **K37 (script-summarized output, brief-by-script not
Write-tool) is the right target, not SKILL.md prose compression.** The
memory note "only cut dead text in SKILL.md" stands; this doesn't change
it, since the growing prefix is tool-output, not skill prose.

## Reproduce

```
cd research/skill-audit-2026-08/C-tokens
python3 -m unittest        # 8 tests green
python3 mine_transcripts.py  # writes out/sessions.csv, out/by_cascade_total.csv, out/agents.csv
```
