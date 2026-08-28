# manager-mode

> Disciplined parallel-agent TDD for Claude Code and Codex. One north-star test, many sub-tasks, zero drift.

![License](https://img.shields.io/badge/license-MIT-blue)
![Claude Code + Codex](https://img.shields.io/badge/Claude%20Code%20%2B%20Codex-skill-D97757)
![Status](https://img.shields.io/badge/status-v1.1-green)

[Why TDD + AI](#why-tdd-for-ai-agents) • [Before / After](#before--after) • [Benchmarks](#benchmarks) • [What you get](#what-you-get) • [How it works](#how-it-works) • [Install](#install) • [Config](#config)

A skill pack for Claude Code and Codex that lets you run many AI sub-agents in parallel without the usual failure modes: overlapping file edits, silent design decisions, oversized tasks, regressions slipping past admission.

One slash command. Eight phases. A dozen layered gates. One tree-shaped cascade.

| Command | What it does |
|---|---|
| `/manager-mode` | The whole cascade in one command. Drafts spec/contract/umbrella if missing, writes and audits per-leaf RED tests, spawns builders in parallel, sweeps assumptions, admits each leaf through G1–G7 + umbrella checks, then evidence-audits admitted leaves in parallel batches of at most three. Confirmed batch-footprint repairs must pass affected tests and the full suite. |
| `/manager-mode-hardcore` | For high-consequence work: keeps the normal admission flow, then uses two independent fresh-context auditors and a third adjudicating reviewer for every ≤3-leaf batch. |

---

## Why TDD for AI agents

AI agents fail in three predictable ways:

1. **Silent design.** Underspecified tasks let the agent "decide" how something should work. The choice never surfaces — it just becomes code.
2. **Vibes-pass "done".** Agents declare victory at the first plausible-looking output. You find out it wasn't done in integration. Or in prod.
3. **Parallel agents amplify both.** Five agents drifting in five directions, each "done", none of them composing.

A failing test fixes the root cause. The API is pinned before any code runs — no room to invent a different shape. "Done" becomes a binary, machine-checkable signal. Regressions get loud instead of staying silent. TDD has been the right discipline for 20 years; it's *especially* the right discipline for AI agents, because silent design drift is the failure mode autoregressive models are most prone to.

## The north-star test

Every wave starts with **one failing test** that defines what "done" looks like for the entire batch of work. We call it the **umbrella test** — it's the north star every sub-agent moves toward.

```
                                umbrella test (failing)
                                          │
                   ┌──────────────────────┼──────────────────────┐
                   ▼                      ▼                      ▼
               sub-task 1             sub-task 2             sub-task 3
          (one test + one impl)  (one test + one impl)  (one test + one impl)
                   │                      │                      │
                   └──────────────────────┼──────────────────────┘
                                          ▼
                                umbrella test (passing)
                                          │
                                      wave done
```

Each sub-task is one test file + one impl file. The sub-task is done when its own test passes. The wave is done when the umbrella test passes. No passing umbrella, no admission.

## Before / After

### Without Manager Mode

```
"spawn 5 agents on this"
        │
        ▼
   Agent A ──── edits auth.py
   Agent B ──── also edits auth.py    ← collision, last write wins
   Agent C ──── invents JWT           ← requirements said sessions, silent drift
   Agent D ──── task too big          ← ran out of context, half-stubbed
   Agent E ──── "done!"               ← integration test still failing, nobody noticed
```

### With Manager Mode

```
   /manager-mode  ──►  Phase 0    preflight (config + check which inputs exist)
                Phase 1    lite-discovery (drafts spec/contract/umbrella only if
                            missing, with Bible Compliance footer on the spec)
                Phase 1.5  plan-consistency: spec vs contract vs umbrella —
                            blocking, and runs even when nothing was drafted
                Phase 2    decompose: emit briefs + shard-test-writer authors
                            per-leaf failing tests (Spec Link Rule, ≤16 leaves)
                Phase 3    audit briefs (check_invariants.py + external
                            test-quality audit — block on FAIL)
                Phase 4    wave base commit; one git worktree per leaf; spawn N in parallel
                Phase 5    wait green; commit each leaf worktree; assumption-sweep
                Phase 6    admission loop: G1–G10 + umbrella pre/post per leaf
                            (admit or revert from file backup)
                Phase 7    final report: counts + follow-ups + apex test
```

## Benchmarks

Paired evals (one with Manager Mode, one without), each targeting a specific failure mode. Graded on **mistake prevention**, not pass-rate, tokens, or wall-clock. Methodology: [skills/swarm-shared/references/evaluation-rubric.md](skills/swarm-shared/references/evaluation-rubric.md).

**Core safety suite (A–E):**

| Eval | Failure mode tested | Without skill | With skill |
|---|---|---|---|
| **A** | Fault detection at 15-way fan-out | Both produced output | Caught 2 silent drifts |
| **B** | Skipping the failing-test gate | **Failed silently** | **Blocked correctly** |
| **C** | Requirements vs strategy contradiction | Both halted | Skill kept an audit trail |
| **D** | Silent regression across 5 admissions | Both correct | Skill kept a reviewable record |
| **E** | Two sub-tasks targeting same fat file | **Failed silently** | **Blocked correctly** |

**Coordination-pattern suite (F–H):**

| Eval | Failure mode tested | Without skill | With skill |
|---|---|---|---|
| **F** | Sibling-leaf assumption drift | Both adopted the same value (forced by brief) | Channel surfaced via sibling-ASSUMPTIONS read |
| **G** | Leaf resolved a blocked decision by self-inference | **Admission approved despite open question** | **G3 blocked admission** |
| **H** | Leaf workaround instead of proposing a contract change | Blocked via narrative escalation | Blocked via structured `.swarm/proposals/` (auditable) |

- **8/8 evals**: correct verdict with the skill.
- **3/8 evals (B, E, G)**: baseline silently failed a safety property; skill blocked.
- **0 false positives** on Phase 3 audit verdicts.
- Coord-pattern suite (F/G/H): old skill 78% ± 38%, new skill 100% ± 0%.

The load-bearing evals are B, E, and G: real time gets lost when those gates get skipped in production work. The skill blocked all three.

## What you get

| Component | What |
|---|---|
| `/manager-mode` | The single command. Drives all eight phases — preflight, lite-discovery, decompose, audit, spawn, sweep, admission loop, report. |
| `run_gates.py` | Runs every Phase 6.5 gate for one leaf in a single command — artifact preconditions, file-match, G1–G6, G8–G10 — and writes the leaf's `GATES.md` evidence file itself. Read-only: it verifies, it never admits. Exists because prose gates have no failure mode; across 64 surveyed cascades the boundary sweep was recorded 0 times and 13 of 15 admission logs held a header and no rows. |
| `check_invariants.py` | Deterministic audit script run at Phase 3. Standalone — runnable in CI without Claude Code. Checks file-overlap, no-design, sizing, and the Spec Link Rule (every test file headers `# spec: <path>::<section>::AC-<N>`). |
| `playbook.md` | Full theory: why each invariant exists, what failure mode it prevents, prep-step seam discipline, file-mediated coordination patterns. |
| `brief-template.md` | Canonical leaf-brief shape. `/manager-mode` Phase 2 emits briefs against this template; Phase 3 audits against it. |

## How it works

`/manager-mode` walks through eight phases without you having to invoke anything else:

1. **Preflight (Phase 0).** Find or bootstrap `.claude-swarm.toml`. List which of {spec, contract, umbrella} already exist on disk.
2. **Lite-discovery (Phase 1).** Fires only for missing inputs. One-question drafts per artifact — spec, type contract, failing umbrella test. The spec carries a Bible Compliance footer (cites your source-of-truth doc + lists deliberate divergences). No `.UNSTATED.md` ceremony.
3. **Decompose (Phase 2).** Reads spec + contract, emits one brief per sub-agent at `<briefs_dir>/leaf-NN.md`. A separate shard-test-writer — never the overlord — authors the failing test for each brief; leaves only write impl. Refuses to emit more than 16 leaves in one wave. Every test file begins with a `# spec: <path>::<section>::AC-<N>` header (Spec Link Rule).
4. **Audit (Phase 3).** Runs `check_invariants.py`. Any FAIL → fix the brief and re-run. No spawn until PASS.
5. **Spawn (Phase 4).** Commit the Phase 1–3 artifacts as the wave base (with your OK), then give each leaf its own git worktree on `swarm/<slug>/leaf-NN` and spawn one sub-agent per brief in parallel (Claude Code uses native `Task` delegation, Codex uses `spawn_agent`). Each leaf edits its impl files in place inside its worktree — never running git — and confirms RED→GREEN for real. Because your checkout is untouched for the whole wave, "green in isolation" means it: a leaf's green cannot be produced by a sibling's edits.
6. **Wait + sweep (Phase 5).** Wait for every sub-agent to report green, then commit each leaf's declared files from its worktree onto its branch (`worktree_ops.py commit` refuses on any undeclared write or any sign the leaf ran git). Run the aggregate assumption-sweep — read every `leaf-NN.ASSUMPTIONS.md`, classify drift (contradicts-spec, contradicts-bible, cross-leaf, fabricated, compounded), write `wave-N.SWEEP.md`. User picks patch-vs-redo per flagged entry.
7. **Admission loop (Phase 6).** Per leaf: G1–G10 gates → file-match → umbrella pre/post → admit-or-revert. G5 diffs the leaf's commit against the wave base, so any write outside its declared footprint blocks. Admission is a `--no-ff` merge into `swarm/<slug>/integration`; revert is a `reset --hard` there, with the leaf's commit kept on a `reverted/` branch for forensics. Your own branch is written only by the confirmed base commit and the confirmed final fast-forward. Append-only `post-review-log.md` (now with leaf/merge shas) plus a per-leaf `GATES.md` — the log records an admission, the evidence file records that the gates actually ran.
8. **Report + evidence audit (Phases 7–8).** Counts of admitted/reverted/escalated and apex status, followed by parallel evidence audits in deterministic ≤3-leaf batches. The overlord records accepted/denied findings and verifies any confirmed in-footprint repair with affected tests and the configured full suite.

## Coordination model

The cascade is a tree: parent at root, leaves at fringe, no edges between leaves. Direct leaf-to-leaf messaging would turn the cascade into a graph and destroy regression attribution. But leaves do sometimes need to coordinate. Three file-mediated patterns let them — without breaking the tree shape:

| Pattern | What | Where it fires |
|---|---|---|
| **Sibling-ASSUMPTIONS read** | Leaves read (never write) other leaves' `.ASSUMPTIONS.md` before logging their own. Catches drift at leaf-time instead of admission-time. | Leaf brief boilerplate |
| **Question ledger** | Leaf publishes `.swarm/<cascade>/questions/leaf-NN-Q<n>.md` instead of inferring silently. Parent answers asynchronously in `.swarm/<cascade>/answers/`. | `/manager-mode` Phase 6.5 **G3** gate enforces resolution |
| **Contract proposals** | Leaf publishes `.swarm/<cascade>/proposals/leaf-NN.md` instead of editing parent-owned files. Parent applies + accepts. | `/manager-mode` Phase 6.5 **G4** gate verifies application |

What's intentionally **not** built: direct leaf-to-leaf messaging, shared mutable state, synchronous waits, cross-leaf impl reads from another leaf's worktree or branch. Each would re-introduce a failure mode the cascade exists to prevent.

## Gate reference

Every safety net is a numbered gate. Each runs at a specific point in the workflow.

| Gate | What | Phase |
|---|---|---|
| `non-overlap` | No two briefs name the same impl file. | Phase 3 |
| `no-design` | No ambiguous verbs in task prose; no symbols outside the locked contract. | Phase 3 |
| `sizing` | Impl/test budgets within configured caps. | Phase 3 |
| `spec-link` | Every brief-declared test file begins with `# spec: <path>::<section>::AC-<N>`. | Phase 3 |
| `codebase-preconditions` | `verify:` commands on briefs that claim codebase state pass. | Phase 3.1 |
| `task-size` | Wave has ≤ 12 leaves (warn 13–16, refuse > 16). | Phase 2.2 |
| `bible-compliance` | Spec cites the source-of-truth doc + lists deliberate divergences. | Phase 1.A |
| `weak-umbrella` heuristic | Umbrella asserts on behavior, not source-grep. | Phase 1.C (drafting) |
| `G1` parent-owned | No staged file matches `parent_owned` globs. | Phase 6.4 |
| `G2` ASSUMPTIONS | Inferences are logged, not buried. | Phase 6.5 |
| `G3` open-question | Every published question has an answer or `unanswered: true` ack. | Phase 6.5 |
| `G4` contract-proposal | No `pending` proposals; `accepted` proposals are actually applied. | Phase 6.5 |
| `G5` footprint integrity | The leaf's commit changes only declared paths, and the leaf never ran git. | Phase 6.5 |
| `G6` escalation-trigger | Any brief-declared `detect:` command that matches requires a filed escalation. | Phase 6.5 |
| `G7` wave-sweep | Aggregate assumption-sweep ran before first admission of wave. | Phase 6.1 |
| `apex-test` | Behavioral integration test passes after all leaves are admitted. | Phase 7.1 |
| `bypass-detection` | Every prior leaf was gated through Phase 6; no leaf landed without audit. | Phase 6.0 |

## Install

One command detects Claude Code and Codex and installs the versioned `manager-mode`, `manager-mode-hardcore`, and `swarm-shared` skills into every detected client — machine-wide, including every Claude Code account under `~/claude-accounts/*/.claude`, not just whichever one `CLAUDE_CONFIG_DIR` currently points at.

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/Westopoli/claude-manager-mode/main/install.sh | bash
```

**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/Westopoli/claude-manager-mode/main/install.ps1 | iex
```

### Checking what is installed

```bash
./install.sh --list     # every target, with the version each one holds
./install.sh --check    # same, but exits 1 if any target drifts from source
```

Each installed skill directory carries a `VERSION` stamp (source commit + install date). Without it, a stale install is undetectable from inside a session: the skill loads and reads as authoritative while quietly running rules that were changed or removed from source, possibly months earlier.

Flags: `--no-accounts` restricts to the primary config dir, `--accounts-root DIR` looks for accounts somewhere other than `~/claude-accounts`, `--only claude|codex` restricts by client.

### Manual install

```bash
# macOS / Linux
git clone https://github.com/Westopoli/claude-manager-mode
cd claude-manager-mode
./install.sh
```

```powershell
# Windows
git clone https://github.com/Westopoli/claude-manager-mode
cd claude-manager-mode
.\install.ps1
```

### Installer options and behavior

```bash
./install.sh --list                 # show detected clients and their config homes
./install.sh --only claude          # install only for Claude Code
./install.sh --only codex           # install only for Codex
./install.sh --dry-run              # show targets without changing them
```

```powershell
.\install.ps1 -List
.\install.ps1 -Only claude
.\install.ps1 -Only codex -DryRun
```

Claude Code is detected when its `claude` executable is on `PATH` or its config home exists; Codex follows the same rule for `codex`. The target directories are `${CLAUDE_CONFIG_DIR:-~/.claude}/skills` and `${CODEX_HOME:-~/.codex}/skills` (PowerShell uses the same environment variables, falling back to the user's home directory). If neither client is present, the installer exits successfully without changing anything.

Before an update, existing installed and legacy skill directories are renamed with a timestamped `.bak.*` suffix. The installer validates and stages all required skills before it changes a target. Restart Claude Code after installing. For Codex, restart or refresh the Codex CLI or the local Codex surface in the ChatGPT desktop app, then invoke `/manager-mode` or `/manager-mode-hardcore`. A shell installer cannot add skills to ordinary hosted ChatGPT chats.

### Uninstall

```bash
# macOS / Linux
rm -rf ~/.claude/skills/{manager-mode,manager-mode-hardcore,swarm-shared}
rm -rf ~/.codex/skills/{manager-mode,manager-mode-hardcore,swarm-shared}
```

```powershell
# Windows
Remove-Item -Recurse -Force $env:USERPROFILE\.claude\skills\manager-mode, $env:USERPROFILE\.claude\skills\manager-mode-hardcore, $env:USERPROFILE\.claude\skills\swarm-shared
Remove-Item -Recurse -Force $env:USERPROFILE\.codex\skills\manager-mode, $env:USERPROFILE\.codex\skills\manager-mode-hardcore, $env:USERPROFILE\.codex\skills\swarm-shared
```

## Config

Optional. Drop a `.claude-swarm.toml` at your repo root to point Manager Mode at your test command and project layout:

```toml
spec_dir           = "specs/"
briefs_dir         = ".swarm/briefs/"
umbrella_test_cmd  = "pytest tests/umbrella -x"
type_contract_path = "src/contract.py"
```

Without a config file, Manager Mode uses sensible defaults — the only thing you'll *probably* need to set is `umbrella_test_cmd` so it knows how to run your test suite.

**What you can tune (via `.claude-swarm.toml`, never edit the script):**

| Knob | Default | What it controls |
|---|---|---|
| `spec_dir` | `specs/` | Where your requirements docs live |
| `briefs_dir` | `.swarm/briefs/` | Where sub-task descriptions land |
| `type_contract_path` | _(unset)_ | Shared types file all sub-agents import |
| `umbrella_test_cmd` | _(unset)_ | Command that runs the "done" test |
| `parent_owned` | types files, conftest, umbrella tests, integration tests | Files only the parent agent can edit |
| `max_impl_lines` | `200` | Cap on sub-task impl file size |
| `max_test_assertions` | `20` | Cap on sub-task test file size |
| `ambiguous_verbs` | `decide`, `choose`, `design`, `figure out`, … | Banned words in task descriptions |

Full schema at [skills/swarm-shared/references/config.md](skills/swarm-shared/references/config.md).

## License

MIT. Use it, fork it, ship it.
