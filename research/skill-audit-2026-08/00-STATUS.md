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
| A6 commits | | | 6-commit series per plan | |
| A7 E2E mini cascade | | | A-worktree/E2E-<date>.md | |
