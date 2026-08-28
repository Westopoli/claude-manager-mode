# Skill audit 2026-08 — status

| step | started | done | output | verified-by |
|---|---|---|---|---|
| A1 design decisions | 2026-08-27 | 2026-08-27 | A-worktree/DESIGN.md | overlord (draft until A3 signoff) |
| A2 git sequence | 2026-08-27 | 2026-08-27 | A-worktree/GIT-SEQUENCE.md | overlord (draft until A3 signoff) |
| A3 dry run | 2026-08-27 | 2026-08-27 | A-worktree/DRYRUN.md (Sonnet agent, 13 cases) | overlord: findings folded into GIT-SEQUENCE.md M1–M10 |
| B1 extractor | 2026-08-27 | 2026-08-27 | B-test-audit/extract_ledgers.py → ledgers/{agora,leandrc49,switchboard,the-best-salesmen} (56 ledgers) | overlord: declared vs parsed finding counts spot-checked on Agora |
| C1 miner | 2026-08-27 | 2026-08-27 | C-tokens/mine_transcripts.py → out/agents.csv (716 agents), SUMMARY.md | overlord: dedupe ×1.95 verified on one transcript |
| B2 coverage matrix | 2026-08-27 | 2026-08-27 | B-test-audit/coverage.py → out/{cascades,ac_coverage,findings,audits}.csv, COVERAGE.md | pending spot-check |
| A4 worktree_ops.py | 2026-08-27 | 2026-08-27 | skills/swarm-shared/scripts/worktree_ops.py + tests/test_worktree_ops.py (18 tests) | unittest green |
| A4b run_gates.py git-based | 2026-08-27 | 2026-08-27 | run_gates.py + tests/test_run_gates.py fixture rewrite (22 tests) | unittest green |
| A5 prose + docs + lite removal | 2026-08-27 | 2026-08-27 | SKILL.md, hardcore, config.md, playbook.md, brief-template.md, toml example, README, test_skill_contract.py, .claude/settings.json | full suite 100 OK; install_test PASS |
| A6 commits | 2026-08-28 | 2026-08-28 | 6-commit series (bf7a406..92c6b61) | full suite green after each |
| A7 E2E mini cascade | 2026-08-28 | 2026-08-28 | A-worktree/E2E-2026-08-28.md | overlord: ran directly, verified user checkout untouched then correct at each stage |
| B3 judgment pass | 2026-08-28 | 2026-08-28 | B-test-audit/judgments/{pre-auditor-narrative,post-auditor-narrative,extracted-corpus}.json | 3 Sonnet agents, all cited |
| C1b miner unit tests | 2026-08-28 | 2026-08-28 | C-tokens/test_mine_transcripts.py (5 tests) | unittest green |
| C2 questions | 2026-08-28 | 2026-08-28 | C-tokens/QUESTIONS.md | overlord, from CSVs only |
| D1 knob map | 2026-08-28 | 2026-08-28 | D-experiments/knob-map.md | overlord |
| B4 synthesis | 2026-08-28 | 2026-08-28 | B-test-audit/SYNTHESIS.md | overlord, cross-referenced all 3 judgment files |
| B5 misconceptions | 2026-08-28 | 2026-08-28 | B-test-audit/MISCONCEPTIONS.md (incl. extractor under-linking finding) | overlord |
| D2 experiment design | 2026-08-28 | 2026-08-28 | D-experiments/design.md (4 rows, gated on approval) | overlord |
| C4 main-session miner | 2026-08-27 | 2026-08-27 | C-tokens/mine_transcripts.py extended → out/sessions.csv (15 overlord sessions), out/by_cascade_total.csv | unittest 8/8 green (3 new) |
| C5 overlord cost | 2026-08-27 | 2026-08-27 | C-tokens/OVERLORD.md — overlord is 78.3% of $ across 15 real cascades (median 85.1%); cache-read growth traced per-turn, dominated by accumulated tool output not SKILL.md | overlord, from CSVs only |
| E0 path-guard fix | 2026-08-27 | 2026-08-27 | skills/manager-mode/SKILL.md 4.2 leaf prompt now carries absolute worktree root + briefs_dir (was relative, risked cross-checkout edits) | 100 tests + install_test PASS |
| E0b no-auto-pass rule | 2026-08-27 | 2026-08-27 | test-design.md new section + SKILL.md 2.6 bullet, generalized from a real bug found in the Prosper probe (vacuous typo/reorder oracle) | 100 tests + install_test PASS |
| E1 Prosper Stage 0-1 | 2026-08-27 | 2026-08-27 | the-best-salesmen `search-quality` branch: search_probe.py (provenance-graded, closed verdict enum, self-validated against stub_empty/stub_all/stub_reference), search-failure-map.{md,json} (10220 queries, 4439 FAIL), specs/search-quality.md (partial stub) | commit ae3091f; stub-validation passed, no vacuous class |
| E1b map annotation | 2026-08-27 | 2026-08-27 | Stand-in checkpoint review (no human available overnight, user-authorized) — findings accepted, typo/reorder recall explicitly scoped out of this cascade | the-best-salesmen commit 1297e9c |
| E2 lock inputs | 2026-08-28 | 2026-08-28 | specs/search-quality.md (36 ACs), src/backend/types.py contract, tests/umbrella_search.py (RED). Plan-consistency pass caught 3 real AC contradictions, fixed before commit | the-best-salesmen commit 9725415; umbrella confirmed RED |
| E3 decompose | 2026-08-28 | 2026-08-28 | 4 leaf briefs (wave 1, one shard) + DEPENDENCY-MAP.md | the-best-salesmen commit 5384c24; check_invariants 4/4 PASS (spec-link findings are expected pre-2.6) |
| E4 writer/auditor pre-screen | 2026-08-28 | 2026-08-28 | 4 reps (shard-test-writer + test-auditor) in throwaway worktrees, all RED-confirmed; blind 4-pairing comparator run | comparator preferred Opus 4/4; Sonnet 5 does not qualify for writer/auditor — see 00-DECISIONS.md |
| E5 full cascades C0/C2 | 2026-08-28 | **blocked** | C0: real work through Phase 3 (PLAN-CHECK.md, DECOMPOSITION.md, 5 leaf briefs, 3 audit rounds, all in `/tmp/cascades/c0/.swarm/search-quality/`) then hit an architecture mismatch at Phase 4 — see 00-DECISIONS.md. C2: stuck 3h on an unreported "environment issue before Phase 0", zero output, stopped. | not verified — Step D paused pending redesign |
| E6 C2 skill variant | 2026-08-28 | 2026-08-28 | manager-mode-workspace/iteration-1/skill-snapshot-c2 + C2-CHANGES.md — options 1 (sweep/admission runners), 2 (return caps), 3 (script audit brief, summary rendering), 5 (inline excerpts, grep-range reads) | 100 tests green against snapshot; build_audit_brief.py smoke only |
| E7 cascade recorder | 2026-08-28 | 2026-08-28 | skills/swarm-shared/scripts/cascade_metrics.py + rates.json; SKILL.md 7.2 records every cascade (overlord + per-role $/tokens, artifacts) to .swarm/<slug>/METRICS.{md,json} and ~/.claude/swarm-metrics/ ledger; landed in repo skills/ and both snapshots | tests/test_cascade_metrics.py 9/9; full suite 109 OK; install_test PASS; smoke-run on overnight window found the cross-cwd executor session + 23 sub-agents |
