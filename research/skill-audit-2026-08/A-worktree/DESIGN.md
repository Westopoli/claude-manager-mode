# Track A — git-worktree isolation: design decisions

Status: DRAFT until `DRYRUN.md` is signed off in `../00-DECISIONS.md`.

## Why this exists

The current skill isolates each leaf in a full project copy (`.swarm/<slug>/sandbox/leaf-NN/`), hashes every file before the wave, harvests declared files into `pending/`, copies into the live tree with `backups/` for revert. In five real Agora cascades this produced:

- G5 false positives on live-tree drift (`runs/`, `docs/`, `.venv/`) — the overlord hand-wrote four `admit*.py` waiver scripts to get past its own gate.
- No surviving `pending/` staging anywhere; harvested output went straight to backups + live tree.
- One project copy per leaf (disk), and an isolation tax measured at ~2× tokens in `experiments/scaling-test/phaseG`.

A worktree gives the same property the sandbox was built for — the leaf's test imports impl at its *real* path and observes RED→GREEN in a tree no sibling can touch (`playbook.md:186-190`, keep verbatim) — with git doing the bookkeeping: what changed (`git status`), what was declared vs. produced (`git diff --name-only`), what was admitted (merge commit), and how to revert (`reset --hard`).

History note: no worktree version ever existed. The pre-2026-05-22 design was branch-based with no skill-created isolation and was dropped because git commands needed permission grants and leaked side effects when agents ran non-interactively. Both are addressed below (one script runs all git; leaves never run git).

## Decisions

| # | Decision | Rejected alternative |
|---|---|---|
| D1 | **Location.** Leaf worktrees at `.swarm/<slug>/worktrees/leaf-NN/`; integration worktree at `.swarm/<slug>/worktrees/integration/`. Both under the already-gitignored `.swarm/`. Relative paths work in prompts; forensics discoverable by `resolve_*` helpers. Documented costs: `git clean -fdx` in the main checkout destroys them; repo-wide linters/test discovery may descend into `.swarm/` (already true for sandboxes). | `$TMPDIR`: not relative-path addressable, lost on reboot, invisible to resolvers. |
| D2 | **Base.** Overlord works in the user's checkout for Phases 0–3 (drafts reviewed where the user expects). At 4.0 it lists the artifact paths (spec, contract, umbrella, briefs, shard tests, audits), asks, commits on the user's branch → `base_sha`. `swarm/<slug>/integration` is created from base at cascade start. After each wave's admission loop, integration is ff'd into the user's branch (confirmed) so wave N+1's Phase 2/3 writes land in the checkout and `base_{N+1}` = new HEAD. Undo instruction for the 4.0 commit: `git reset --soft HEAD~1`. | Integration worktree as overlord root from Phase 0: cleaner isolation, but every Phase 1–3 cwd/path changes and drafts live in a hidden dir. Fallback if per-wave ff proves annoying. |
| D3 | **Dirty tree at preflight → refuse.** `git status --porcelain` shows tracked changes, or detached HEAD → stop; tell the user to commit or stash. Untracked non-ignored files → list with a warning (they will not exist in any worktree; use `worktree_copy` if needed). | Auto-stash: hides user work; a pop after a failed cascade is exactly the side effect that killed the old design. |
| D4 | **Deps.** `sandbox_link` → `worktree_link` (symlink from main root into each worktree; old key accepted as alias with a deprecation note). New `worktree_copy` for untracked-but-needed files (`.env.test`, generated fixtures). Both applied to leaf *and* integration worktrees. `snapshot_ignore` → `footprint_ignore` (same semantics: paths excluded from the footprint check). | Committing deps: no. |
| D5 | **Snapshot gone.** `wave-N.base.json` = `{wave, base_sha, integration_sha, user_branch, created_at, leaves: {leaf-NN: {branch, worktree, commit: null\|sha}}}` written by `worktree_ops.py base`. | SHA snapshots alongside git: redundant; the live-tree half is what produced the false positives. |
| D6 | **G5 footprint.** Pre-commit, in the leaf worktree: `HEAD == base_sha` (else the leaf ran git → block) and `git status --porcelain --untracked-files=all`, minus `footprint_ignore`, ⊆ declared. Post-commit: `git diff --name-only base..branch` ⊆ declared ∧ every `impl_file` exists on the branch. Live-tree drift in the user's checkout → **advisory WARN** (admission never writes there). Integration worktree dirty → **block**. | Keep live-tree drift blocking: it is the false-positive source and no longer protects anything. |
| D7 | **Staging and backups gone.** The leaf commit on `swarm/<slug>/leaf-NN` *is* the staged artifact. Revert = `git reset --hard <pre-merge-sha>` in the integration worktree. | — |
| D8 | **Conflict on merge.** Impossible under the Phase 3 file-disjoint invariant; if it happens it *is* an undeclared overlap: `git merge --abort`, GATES row `G1/overlap breach — FAIL`, not admitted, loop continues. | Auto-resolve: never. |
| D9 | **Cleanup / data-leak policy.** Admitted leaf: `git worktree remove` + `git branch -d` (safe delete; merged). Reverted-after-commit: remove worktree, rename branch → `swarm/<slug>/reverted/leaf-NN` (forensics live in the commit, not on disk). Refused-at-commit (undeclared writes / HEAD moved): **keep worktree and branch** until the user inspects — the only case where on-disk state is the evidence. Integration branch deleted after the final ff (confirmed). `git worktree prune` always last. `worktree_ops.py status` lists every residual `swarm/<slug>/*` branch and worktree; the Phase 7 report prints that list verbatim under "Residual git state" so nothing leaks silently. `cleanup --purge` removes `reverted/*` and refused leftovers after confirmation. | Delete everything unconditionally: loses the only forensic record for reverts. |
| D10 | **Who runs git.** Only `worktree_ops.py`, invoked by the overlord. Leaf prompt: "your working directory is `.swarm/<slug>/worktrees/leaf-NN/`, a git checkout the parent manages; never run git." Permission surface for the target project: one allow entry `Bash(python3 *worktree_ops.py*)`. Every git call goes through `_git(args, cwd)` which appends `timestamp \| cwd \| argv \| exit` to `.swarm/<slug>/git-ops.log` — the audit trail that replaces the "identical timestamps" bypass tell. | Raw git in prose: "prose is not a gate"; each raw command is its own permission prompt. |
| D11 | **Finish.** `worktree_ops.py finish` shows `git log --oneline <user-branch>..swarm/<slug>/integration`, asks, then `git merge --ff-only swarm/<slug>/integration` in the main checkout. If ff is impossible (user committed meanwhile) → stop and print the two commands; never rebase or merge non-ff on the user's behalf. | — |
| D12 | **Waves / shards.** Shard = label only (audit dir + test-writer scope); no git object per shard. Each wave: base = integration HEAD at wave start, own `wave-N.base.json`. One global sequential admission loop (ascending wave, then NN) into the single integration branch. Concurrent waves (SKILL.md "Going past one wave") share only the integration branch, which admission serializes anyway. | Integration branch per wave: more state, no benefit. |
| D13 | **Non-git repos → refuse** at preflight (`git rev-parse --git-dir`). `check_invariants.py` gains `main_root()` via `git rev-parse --git-common-dir` so any script invoked from inside a worktree resolves `.swarm/` at the main checkout. | — |
| D14 | **run_gates.py stays read-only.** It computes file-match and G5 from git and writes `GATES.md`; `worktree_ops.py admit` is the mutating half and refuses unless `GATES.md` exists with no `\| FAIL \|` row (same guard Agora's `tools.py admit` implemented). | Merge admit into run_gates: breaks the "runner does not admit anything" contract pinned by tests. |

## Config changes (`.claude-swarm.toml`)

| old | new | notes |
|---|---|---|
| `sandbox_link` | `worktree_link` | alias accepted, warning printed |
| `snapshot_ignore` | `footprint_ignore` | alias accepted |
| — | `worktree_copy` | list of untracked paths copied into each worktree |
| `max_impl_lines` | unchanged | fix inconsistency: `config.md` says 200, `.toml.example` says 1000 → 200 |

## Per-cascade layout after this change

```
.swarm/
  post-review-log.md               # + leaf_commit | merge_commit columns
  <slug>/
    PLAN-CHECK.md  briefs/  audits/  questions/  answers/  proposals/
    worktrees/leaf-NN/             # git worktree on swarm/<slug>/leaf-NN
    worktrees/integration/         # git worktree on swarm/<slug>/integration
    wave-N.base.json               # replaces wave-N.snapshot.json
    wave-N.SWEEP.md
    audits/wave-N/leaf-NN.COMMIT   # sha written at 5.1
    git-ops.log                    # append-only, every git call
```
Removed: `sandbox/`, `pending/`, `backups/`, `wave-N.snapshot.json`.
