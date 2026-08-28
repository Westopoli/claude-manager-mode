# Track A — exact git sequence per phase

All commands run by `skills/swarm-shared/scripts/worktree_ops.py`. `S` = cascade slug, `N` = wave, `MAIN` = user's checkout root, `INT` = `.swarm/S/worktrees/integration`, `WT(leaf)` = `.swarm/S/worktrees/leaf-NN`. Every command is logged to `.swarm/S/git-ops.log`.

## 0.0 `preflight --slug S`   (cwd MAIN)

```
git rev-parse --git-dir                       # fail → "not a git repo; manager-mode requires git"
git rev-parse --abbrev-ref HEAD               # "HEAD" → refuse: detached
git status --porcelain --untracked-files=normal
   # any line not starting with "??" → refuse: tracked changes, commit or stash
   # "??" lines → WARN list: absent from worktrees; add to worktree_copy if needed
git worktree list --porcelain                 # any path under .swarm/S/worktrees → leftover
git branch --list 'swarm/S/*' 'swarm/S/**'    # any → leftover
   # leftovers → refuse; print `worktree_ops.py cleanup --slug S --purge`
```

## 4.0 `base --slug S --wave N`   (cwd MAIN)

```
git status --porcelain            # non-empty → refuse, print paths (Phase 1–3 artifacts uncommitted)
base=$(git rev-parse HEAD)
if ! git show-ref --verify --quiet refs/heads/swarm/S/integration; then
    git branch swarm/S/integration "$base"
    git worktree add .swarm/S/worktrees/integration swarm/S/integration
else
    git merge-base --is-ancestor "$base" swarm/S/integration || refuse "base not on integration line"
    base=$(git -C INT rev-parse HEAD)
fi
# apply worktree_link (symlink MAIN/<p> → INT/<p>) and worktree_copy (cp) to INT
write .swarm/S/wave-N.base.json {wave, base_sha, integration_sha, user_branch, created_at, leaves:{}}
```

## 4.1 `add --slug S --wave N [--leaf leaf-NN ...]`   (cwd MAIN)

```
for each brief with wave == N:
    git worktree add -b swarm/S/leaf-NN .swarm/S/worktrees/leaf-NN "$base"
       # branch or path exists → refuse for that leaf, continue others, exit 1 at end
    apply worktree_link symlinks + worktree_copy into WT(leaf)
    base.json.leaves[leaf-NN] = {branch, worktree, commit: null}
```

## 4.2 leaf prompt (no git)

"Your working directory is `.swarm/S/worktrees/leaf-NN/`, a git checkout the parent manages. Never run git. Edit your `impl_files` in place there; confirm RED then GREEN."

## 5.1 `commit --slug S --leaf leaf-NN`   (cwd WT(leaf))

```
[ "$(git rev-parse HEAD)" = "$base" ] || refuse "HEAD moved: leaf ran git"          → keep worktree
changed=$(git status --porcelain --untracked-files=all | awk '{print $2}') minus footprint_ignore
[ -z "$changed" ] && refuse "no changes: leaf reported green without producing files"
undeclared = changed − declared;  [ -n "$undeclared" ] && refuse "undeclared writes: …"  → keep worktree
missing_impl = impl_files − existing;  [ -n "$missing_impl" ] && refuse
git add -- <declared ∩ changed>
git commit -q -m "swarm(S): leaf-NN — <brief title>"
sha=$(git rev-parse HEAD)
base.json.leaves[leaf-NN].commit = sha ; write .swarm/S/audits/wave-N/leaf-NN.COMMIT = sha
```

## 6.5 `run_gates.py --leaf leaf-NN`   (read-only; cwd MAIN)

```
file-match: git diff --name-only base..swarm/S/leaf-NN  == declared (set equality; impl_files ⊆ exists)
G5:         same set ⊆ declared; HEAD-of-branch parent == base (exactly one commit)
            git -C MAIN status --porcelain → non-empty → WARN (advisory)
G1, G2–G4, G6–G10 unchanged; G8/G9/G10 read files at WT(leaf) (or `git show branch:path`)
writes audits/wave-N/leaf-NN.GATES.md
```

## 6.6–6.9 `admit --slug S --leaf leaf-NN`   (cwd INT)

```
GATES.md exists and has no "| FAIL |" row            || refuse
git status --porcelain  → empty                       || refuse "integration dirty"
pre_sha=$(git rev-parse HEAD)
pre = named passes of `umbrella_test_cmd -v --tb=no -q`   (cwd INT)
git merge --no-ff --no-edit swarm/S/leaf-NN
   # conflict → git merge --abort ; append GATES row "G1/overlap breach | FAIL" ; log row BLOCKED ; exit 1
post = named passes (cwd INT); acceptance = brief `## Acceptance` cmd (cwd INT)
regressed = pre − post
if regressed or acceptance failed:                                   # 6.9b
    git reset --hard "$pre_sha"
    git worktree remove .swarm/S/worktrees/leaf-NN
    git branch -m swarm/S/leaf-NN swarm/S/reverted/leaf-NN
    log row: | N | shard | leaf-NN | files | REVERTED | ts | regression: … | leaf_sha | — |
    append "## Post-review regression" to briefs/leaf-NN.md
else:                                                                # 6.9a
    merge_sha=$(git rev-parse HEAD)
    git worktree remove .swarm/S/worktrees/leaf-NN
    git branch -d swarm/S/leaf-NN
    log row: | N | shard | leaf-NN | files | +Δ | ts | clean | leaf_sha | merge_sha |
git worktree prune
```

Note: "same count" outcome (6.8 yellow flag) is returned as exit 2 with the merge left in place; the overlord asks the user and then calls `admit --confirm-same` or `revert`.

## End of wave: `sync --slug S`   (cwd MAIN)

```
git merge --ff-only swarm/S/integration      # user branch catches up so wave N+1 Phase 2/3 writes land on top
   # ff impossible → stop; print instructions
```

## 7 `finish --slug S`   (cwd MAIN)

```
git log --oneline HEAD..swarm/S/integration   → show; ask
git merge --ff-only swarm/S/integration       # impossible → print the two commands, stop, never rebase
cleanup --slug S                              # below
```

## `status --slug S` / `cleanup --slug S [--purge]`

```
status:  git worktree list --porcelain | filter .swarm/S ; git branch --list 'swarm/S/**'
         prints a table: kind | name | path | state (admitted-leftover / reverted / refused / integration)
cleanup: remove worktrees of admitted leaves (should be none); git branch -d swarm/S/integration after ff (confirm)
         keep swarm/S/reverted/* and refused worktrees unless --purge (confirm, list first)
         git worktree prune
```

## Expected git refusals to verify in the dry run

1. `git worktree add` when the branch already exists (leftover from aborted run).
2. `git branch -d` on a leaf merged with `--no-ff` — should succeed (merged); confirm.
3. `git worktree remove` with untracked files present — needs `--force`? confirm behaviour for refused-at-commit leaves.
4. `git merge --ff-only` when the user committed on their branch mid-cascade.
5. Merge conflict when two leaves touch the same file (deliberate overlap).
6. `git status` inside a worktree whose `.swarm/` symlinks point back into MAIN — confirm ignored.
7. `git rev-parse --git-common-dir` from inside a worktree → MAIN/.git.

## Amendments after the dry run (DRYRUN.md, 2026-08-27)

| # | finding | change to the sequence |
|---|---|---|
| M1 | Directory-only ignore patterns (`.venv/`) do **not** match a *symlink* named `.venv`; every `worktree_link` symlink shows as `?? .venv` forever. | `footprint_ignore` effective set = configured `footprint_ignore` ∪ `worktree_link` names ∪ `worktree_copy` paths. Additionally `add` writes each `worktree_link` name (no trailing slash) into the per-worktree exclude file (`git rev-parse --git-path info/exclude` run *inside* the worktree) so `git status` itself stays clean; the filter remains as belt-and-braces. Verified in E2E, not yet in the dry run. |
| M2 | `git worktree remove` refuses on any untracked/modified path (exit 128) — which M1 guarantees. `--force` is safe for committed work, destructive for uncommitted. | `remove --force` is used **only** when the leaf's commit sha is recorded in base.json (admit and revert-after-commit). Refused-at-commit leaves are never auto-removed (D9 already said so; now it is the only safe option too). |
| M3 | `git branch -d` after a `--no-ff` merge succeeds only when cwd's HEAD contains the merge. | `admit` runs `branch -d` with `cwd=INT`, never MAIN. Test pins this. |
| M4 | Two leaves editing one file need not conflict (non-adjacent hunks auto-merge). | Overlap is a *set* check: `git diff --name-only base..branch` of the leaf ∩ union of every other leaf's declared/changed set must be ∅ (Phase 3 already forbids declared overlap; admit re-checks the *actual* changed sets). A git conflict is a secondary signal, not the gate. |
| M5 | `git rev-parse --git-common-dir` prints relative `.git` from MAIN, absolute from a worktree. | `main_root()` resolves the path (`Path(out).resolve().parent`) before comparing. |
| M6 | `git merge --ff-only` failure text suggests `--no-ff`/rebase, both forbidden. | `finish` prints its own message with the two allowed commands; raw stderr goes to `git-ops.log` only. |
| M7 | `worktree add -b` with an existing branch → exit 255; invalid ref → exit 128. | Any non-zero exit is a refusal; both messages are captured verbatim into the log. |
| M8 | `git commit -am` inside a leaf leaves untracked files uncommitted; "leaf ran git" ≠ "worktree fully committed". | `commit` step checks HEAD drift **and** untracked/modified sets independently; both are reported. |
| M9 | `git worktree add` creates parent dirs itself. | No `mkdir -p`. |
| M10 | This environment's Bash tool blocks `git reset --hard` typed as a command. | Irrelevant for `worktree_ops.py` (subprocess inside python), but E2E driving must call the script, never raw `git reset --hard`. |
