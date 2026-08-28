# Decisions — append-only

| date | decision | evidence |
|---|---|---|
| 2026-08-27 | No worktree version of the skill ever existed; pre-8aeba56 was branch-based with no skill-created isolation. Worktree design is new, not a revert. | `git log --all -S 'git worktree'` empty; `8aeba56^:skills/swarm-merge/SKILL.md` |
| 2026-08-27 | Isolation = git worktrees only; file-based sandbox dropped; non-git repos refused at preflight. | user decision (plan) |
| 2026-08-27 | Leaves never run git. Overlord commits via `worktree_ops.py`; merge into `swarm/<slug>/integration`; user branch touched only by confirmed 4.0 commit + confirmed final ff. | user decision (plan) |
| 2026-08-27 | `manager-mode-lite` removed; its purpose (efficiency) is what Tracks C/D test directly. | user decision (plan) |
| 2026-08-27 | Track B is script-first; Sonnet 4.6 agents only for judgment on pre-extracted ledgers. | user decision (plan) |
| 2026-08-27 | Token mining must dedupe assistant `usage` by `message.id`; all earlier aggregates are inflated (~2.4×) and are not reused. | Plan agent sample of a leaf transcript |
| 2026-08-27 | A3 dry run signed off. GIT-SEQUENCE.md amended M1–M10 (symlink-untracked, `remove --force` only post-commit, `branch -d` from INT, set-based overlap, common-dir normalisation). Proceed to A4 script. | A-worktree/DRYRUN.md §Findings |
| 2026-08-27 | `footprint_ignore` effective set = config ∪ `worktree_link` ∪ `worktree_copy`; link names also written to per-worktree `info/exclude`. | DRYRUN.md finding 3 |
| 2026-08-27 | `max_impl_lines` default is **1000** (code DEFAULTS, .toml.example, playbook agree); `config.md`'s 200 is the stale outlier and gets fixed. | check_invariants.py DEFAULTS |
