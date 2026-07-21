# claude-manager-mode

> Disciplined parallel-agent TDD for Claude Code. One north-star test, many sub-tasks, zero drift.

![License](https://img.shields.io/badge/license-MIT-blue)
![Claude Code](https://img.shields.io/badge/Claude%20Code-skill-D97757)
![Status](https://img.shields.io/badge/status-v1.1-green)

[Why TDD + AI](#why-tdd-for-ai-agents) • [Before / After](#before--after) • [Benchmarks](#benchmarks) • [What you get](#what-you-get) • [How it works](#how-it-works) • [Install](#install) • [Config](#config)

A skill pack for Claude Code and Codex that lets you run many AI sub-agents in parallel without the usual failure modes: overlapping file edits, silent design decisions, oversized tasks, regressions slipping past admission.

One slash command. Eight phases. A dozen layered gates. One tree-shaped cascade.

| Command | What it does |
|---|---|
| `/manager-mode` | The whole cascade in one command. Drafts spec/contract/umbrella if missing (lite-discovery), decomposes the spec into per-sub-agent briefs, writes a failing test per sub-agent, audits the briefs, spawns sub-agents in parallel, waits for green, runs an aggregate assumption-sweep, then admits each sub-agent through G1–G7 + the umbrella regression check. Reverts via file-backup on regression. No git, no chained commands, no `.UNSTATED.md` ceremony. |

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

### Without claude-manager-mode

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

### With claude-manager-mode

```
   /manager-mode  ──►  Phase 0  preflight (config + check which inputs exist)
                Phase 1  lite-discovery (drafts spec/contract/umbrella only if missing,
                          with Bible Compliance footer on the spec)
                Phase 2  decompose: emit briefs + write per-leaf failing tests
                          (Spec Link Rule headers, task-size guardrail >12/>16)
                Phase 3  audit briefs (check_invariants.py — block on FAIL)
                Phase 4  spawn N sub-agents in parallel
                Phase 5  wait green; aggregate assumption-sweep → wave-N.SWEEP.md
                Phase 6  admission loop: G1–G7 + umbrella pre/post per leaf
                          (admit or revert from file backup)
                Phase 7  final report: counts + follow-ups + apex test
                Phase 8  batched evidence audit: ≤3 admitted leaves per batch;
                          auditor evidence → overlord confirmation → verified repair
```

## Benchmarks

Paired evals (one with `claude-manager-mode`, one without), each targeting a specific failure mode. Graded on **mistake prevention**, not pass-rate, tokens, or wall-clock. Methodology: [skills/swarm-shared/references/evaluation-rubric.md](skills/swarm-shared/references/evaluation-rubric.md).

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
| `check_invariants.py` | Deterministic audit script run at Phase 3. Standalone — runnable in CI without Claude Code. Checks file-overlap, no-design, sizing, and the Spec Link Rule (every test file headers `# spec: <path>::<section>::AC-<N>`). |
| `playbook.md` | Full theory: why each invariant exists, what failure mode it prevents, prep-step seam discipline, file-mediated coordination patterns. |
| `brief-template.md` | Canonical leaf-brief shape. `/manager-mode` Phase 2 emits briefs against this template; Phase 3 audits against it. |

## How it works

`/manager-mode` walks through eight phases without you having to invoke anything else:

1. **Preflight (Phase 0).** Find or bootstrap `.claude-swarm.toml`. List which of {spec, contract, umbrella} already exist on disk.
2. **Lite-discovery (Phase 1).** Fires only for missing inputs. One-question drafts per artifact — spec, type contract, failing umbrella test. The spec carries a Bible Compliance footer (cites your source-of-truth doc + lists deliberate divergences). No `.UNSTATED.md` ceremony.
3. **Decompose (Phase 2).** Reads spec + contract, emits one brief per sub-agent at `<briefs_dir>/leaf-NN.md`, AND writes a failing test for each brief (overlord-owned tests; leaves only write impl). Refuses to emit more than 16 leaves in one wave; warns past 12. Every test file begins with a `# spec: <path>::<section>::AC-<N>` header (Spec Link Rule).
4. **Audit (Phase 3).** Runs `check_invariants.py`. Any FAIL → fix the brief and re-run. No spawn until PASS.
5. **Spawn (Phase 4).** One sub-agent per brief, in parallel — single message with N `Task()` calls. Each sub-agent's prompt says: "tests at X are failing; write impl at Y to make them pass; do not modify tests; stage at `.swarm/pending/leaf-NN/`."
6. **Wait + sweep (Phase 5).** Wait for every sub-agent to report green. Then run the aggregate assumption-sweep — read every `leaf-NN.ASSUMPTIONS.md`, classify drift (contradicts-spec, contradicts-bible, cross-leaf, fabricated, compounded), write `.swarm/wave-N.SWEEP.md`. User picks patch-vs-redo per flagged entry.
7. **Admission loop (Phase 6).** Per leaf: G1–G7 gates → file-match → umbrella pre/post → admit-or-revert. Backup-based revert (no git). Append-only `post-review-log.md` for audit trail.
8. **Report + evidence audit (Phases 7–8).** Counts of admitted/reverted/escalated and apex status, followed by parallel evidence audits in deterministic ≤3-leaf batches. The overlord records accepted/denied findings and verifies any confirmed in-footprint repair with affected tests and the configured full suite.

## Coordination model

The cascade is a tree: parent at root, leaves at fringe, no edges between leaves. Direct leaf-to-leaf messaging would turn the cascade into a graph and destroy regression attribution. But leaves do sometimes need to coordinate. Three file-mediated patterns let them — without breaking the tree shape:

| Pattern | What | Where it fires |
|---|---|---|
| **Sibling-ASSUMPTIONS read** | Leaves read (never write) other leaves' `.ASSUMPTIONS.md` before logging their own. Catches drift at leaf-time instead of admission-time. | Leaf brief boilerplate |
| **Question ledger** | Leaf publishes `.swarm/questions/leaf-NN-Q<n>.md` instead of inferring silently. Parent answers asynchronously in `.swarm/answers/`. | `/manager-mode` Phase 6.5 **G3** gate enforces resolution |
| **Contract proposals** | Leaf publishes `.swarm/proposals/leaf-NN.md` instead of editing parent-owned files. Parent applies + accepts. | `/manager-mode` Phase 6.5 **G4** gate verifies application |

What's intentionally **not** built: direct leaf-to-leaf messaging, shared mutable state, synchronous waits, cross-leaf impl reads from `.swarm/pending/`. Each would re-introduce a failure mode the cascade exists to prevent.

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
| `G5` wave-snapshot integrity | No file outside the leaf's footprint changed since wave start. | Phase 6.5 |
| `G6` escalation-trigger | Any brief-declared `detect:` command that matches requires a filed escalation. | Phase 6.5 |
| `G7` wave-sweep | Aggregate assumption-sweep ran before first admission of wave. | Phase 6.1 |
| `apex-test` | Behavioral integration test passes after all leaves are admitted. | Phase 7.1 |
| `bypass-detection` | Every prior leaf was gated through Phase 6; no leaf landed without audit. | Phase 6.0 |

## Install

Copies the skills into `~/.claude/skills/`. Restart Claude Code, then invoke `/manager-mode`.

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/Westopoli/claude-manager-mode/main/install.sh | bash
```

**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/Westopoli/claude-manager-mode/main/install.ps1 | iex
```

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

### Uninstall

```bash
# macOS / Linux
rm -rf ~/.claude/skills/{swarm,swarm-shared}
```

```powershell
# Windows
Remove-Item -Recurse -Force $env:USERPROFILE\.claude\skills\swarm, $env:USERPROFILE\.claude\skills\swarm-shared
```

## Config

Optional. Drop a `.claude-swarm.toml` at your repo root to point claude-manager-mode at your test command and project layout:

```toml
spec_dir           = "specs/"
briefs_dir         = ".swarm/briefs/"
umbrella_test_cmd  = "pytest tests/umbrella -x"
type_contract_path = "src/contract.py"
```

Without a config file, claude-manager-mode uses sensible defaults — the only thing you'll *probably* need to set is `umbrella_test_cmd` so it knows how to run your test suite.

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
