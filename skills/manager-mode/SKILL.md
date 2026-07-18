---
name: manager-mode
description: Single-command parallel-agent TDD cascade. Use when the user wants to build a feature with parallel sub-agents — phrases like "swarm this", "decompose and spawn", "run the cascade", "spawn N agents on this", "build feature X with parallel agents", "set up the wave", "let's parallelize this". Walks through all phases internally (preflight → lite-discovery → decompose → audit → spawn → wait + sweep → admission loop → final report → adversarial audit) — no sibling slash commands to chain. Overlord chat writes spec/contract/umbrella (lite drafts if missing) AND per-leaf failing tests; leaves only write impl. Leaf sub-agents default to cavecrew (builder/reviewer) when their tool needs fit; a closing adversarial `cavecrew-reviewer` pass assumes the umbrella test and admitted code are both wrong and must prove otherwise. File-based, no git. Hard-refuses when decomposition exceeds ~16 leaves; warns >12. Always invoke this when the user wants parallel sub-agent work — not separate commands for spawn / review / post-review (they no longer exist).
---

# /manager-mode — single-command parallel-agent cascade

One slash command. The overlord (this chat) drives every phase. Sub-agents only write impl against pre-written failing tests.

The cascade prevents three structural failures in parallel-agent TDD: (1) leaves stepping on each other's files, (2) leaves silently making design decisions, (3) leaves receiving slices too big to finish coherently. Phases 0–7 are the procedure for keeping those guarantees while collapsing the prior 4-command UX into one.

Theory: `~/.claude/skills/swarm-shared/references/playbook.md`. Brief template: `~/.claude/skills/swarm-shared/references/brief-template.md`. Config schema: `~/.claude/skills/swarm-shared/references/config.md`.

---

## Phases at a glance

```
Phase 0  Preflight              — find/bootstrap .claude-swarm.toml; list which of {spec, contract, umbrella} exist
Phase 1  Lite-discovery         — fire only for missing inputs; one-question drafts, Bible Compliance footer on spec
Phase 2  Decompose              — emit briefs + write per-leaf failing tests (Spec Link Rule + task-size guardrail)
Phase 3  Audit briefs           — run check_invariants.py + codebase-preconditions; fix & re-run on FAIL
Phase 4  Spawn leaves           — N sub-agents in parallel via Task() in one message
Phase 5  Wait + sweep           — wait all green; aggregate assumption-sweep; write .swarm/wave-N.SWEEP.md
Phase 6  Admission loop         — per leaf: G1–G7 + file-match + umbrella pre/post + admit-or-revert + log
Phase 7  Final report           — counts + follow-up direction
Phase 8  Adversarial audit      — cavecrew-reviewer assumes test+code are wrong; goal-trace → test-coverage → code-slop
```

If all three inputs (spec, contract, umbrella RED) already exist on disk, Phase 1 is skipped entirely. That is the common path for a returning project.

---

## Phase 0 — Preflight

**0.1 Locate config.** Walk up from cwd until a `.claude-swarm.toml` is found. If none: copy `~/.claude/skills/swarm-shared/templates/.claude-swarm.toml.example` to `<project_root>/.claude-swarm.toml`, then ask the user to fill each required field — do not guess values, wrong values here propagate everywhere:

- `spec_dir` — directory for the spec file (often `specs/`).
- `briefs_dir` — leaf briefs go here (default `.swarm/briefs/`).
- `type_contract_path` — contract file (often `src/<pkg>/types.py`).
- `umbrella_test_cmd` — command that runs the umbrella (e.g., `pytest tests/umbrella.py`).
- `parent_owned` — globs leaves cannot touch.

**0.2 Read inputs.** List which of these three exist on disk:

- Spec at `<spec_dir>/<name>.md` (ask the user for `<name>` if ambiguous; do not silently pick).
- Type contract at `<type_contract_path>`.
- Umbrella test at the path `umbrella_test_cmd` would discover.

**0.3 Existing-wave guard.** If `<briefs_dir>` already contains `leaf-*.md` from a prior cascade, stop and ask the user how to scope this run:

- Different `briefs_dir` per cascade (recommended) — set `briefs_dir = ".swarm/<name>/briefs/"` for this run.
- Same `briefs_dir`, additive — only safe if the new wave does not touch files prior leaves owned. Confirm before continuing.

Do not silently overwrite prior briefs.

**0.4 Existing-cascade summary.** Print one line: which of {spec, contract, umbrella} exist, briefs_dir state, project root path. Lock the scope.

---

## Phase 1 — Lite-discovery (conditional, per missing input)

Fires only for inputs missing from Phase 0. **No 11-step ceremony, no `.UNSTATED.md`, no `[source: user-stmt-N]` citation discipline.** Each missing input gets one short turn.

### 1.A Spec missing

Ask in one block:

1. **What do you want to build?** (one or two paragraphs, user's own words)
2. **What's the source-of-truth design doc (bible) for this project, if any?** Path or "none" is acceptable.

Draft `<spec_dir>/<name>.md`:

```markdown
# <name>

## Summary
<one-paragraph paraphrase>

## Acceptance criteria
1. <criterion>
2. <criterion>
...

## Inputs / Outputs / Constraints / Out of scope
<bullets>

## Bible Compliance
- **Bible path:** `<path>` (or "none — this project has no source-of-truth doc")
- **Sections referenced:** <section names / line refs the spec implements>
- **Deliberate divergences:** <list any spec line that intentionally diverges from the bible, with the reason. If none: "none.">
```

Render the draft to the user. They approve, edit, or restart. Bible Compliance is the one piece of discovery rigor kept from the legacy `/swarm` — the source-of-truth strategy doc cites a real cost from omitting it (a wave shipped four Python stages when the bible specified Postgres; cost an afternoon + 15 leaf agents to re-do). Skipping the footer is acceptable when the project genuinely has no bible; lying that there is none is the failure mode.

If `extra_spec_gate_cmds` is set in `.claude-swarm.toml`, run each command with `$SPEC_FILE` exported. Any non-zero exit blocks Phase 1 — fix and re-run.

### 1.B Type contract missing

Derive the minimum symbols needed to encode the spec's inputs, outputs, and main behaviors. Write `<type_contract_path>` with sentinel bodies (`raise NotImplementedError`, `return None`). Each symbol comment-cites the spec line it encodes.

Render to user → approve/edit/restart. Spec is locked at this point — a restart returns to drafting the contract, not the spec.

### 1.C Umbrella test missing

Draft a single behavioral test at the path `umbrella_test_cmd` discovers. The test imports from the contract, asserts on return values or observable side effects (never `open(path).read()` — that is source-grep, not behavior), and is expected to fail because the contract bodies are sentinels.

Run `umbrella_test_cmd`. Confirm exit code is non-zero (RED). If GREEN: the test does not exercise the contract — revise.

Render to user → approve/edit/restart.

### Lite-discovery is one approval-turn per artifact, not three

If the user is engaged and answers quickly, all three drafts can land in one conversation. The point of "lite" is no `.UNSTATED.md`, no architecture intake, no restate-and-confirm loop, no self-scan production. The user is sitting right there — speak with them.

---

## Phase 2 — Decompose

Read the locked spec + contract. Produce one leaf brief per slice at `<briefs_dir>/leaf-NN.md`. **Overlord responsibility:** also write each leaf's failing test file at the path declared in the brief's `test_files`. Leaves only write impl against pre-written failing tests.

### 2.1 Dependency map

If `graphify_cmd` is set, run it. Otherwise do a manual import-graph scan of the impl files you intend to assign. Identify slices such that no two slices touch the same impl file (within the same wave).

### 2.2 Task-size guardrail

Count planned leaves:

- **≤ 12:** proceed.
- **13–16:** print warning, ask the user to confirm. Past ~12, observed failure rate climbs — siblings drift, parent context fills, post-review log gets noisy. Confirm or re-scope.
- **> 16:** **refuse**. Do not write the briefs. Tell the user either to re-scope the spec into a smaller wave, or to break into multiple sequential waves (wave 1 owns files A–F, wave 2 picks up files G–L after wave 1 admits cleanly).

### 2.3 Fat-file check (only if some impl files exist)

For each impl file the spec implies will be touched: if the file already exists and spans multiple ACs the spec decomposes into separate leaves, render the fat-file warning and ask the user to choose:

- **(a) Sequential waves** — assign AC-X to wave 1, AC-Y to wave 2. Same file, one owner at a time.
- **(b) Prep-step split** — overlord commits a refactor that splits the file into sub-files before decomposition. See `swarm-shared/references/playbook.md` "Prep steps".

Do not pick silently. The seam-axis decision belongs to the user.

### 2.4 Emit briefs

For each slice, write `<briefs_dir>/leaf-NN.md` following `~/.claude/skills/swarm-shared/references/brief-template.md`. Set `test_owned_by: parent` in every brief frontmatter (the overlord owns the test files now).

Key brief rules:
- `spec_lines`: concrete `int-int` range.
- `contract_imports`: only symbols present in the locked contract.
- `do_not_edit`: every other same-wave brief's `impl_files` + parent-owned globs.
- Task prose: imperative, no ambiguous verbs (decide / choose / design / determine / figure out / resolve / pick).
- Task fenced code: total non-blank lines across all fenced blocks ≤ `max_brief_code_lines` (default 10). Stub signatures + mirror-pointer snippets only. **Do not embed ready-to-paste impl bodies — the leaf authors the body.** Use shape-carriers instead: `spec_lines` refs, `contract_imports`, mirror-pointers ("match the structure of `path/to/sibling.py`"), invariant statements. Embedding the body collapses parallelism — parent absorbs leaf work, leaf becomes a copy-paste courier. Audit blocks briefs that exceed the ceiling.
- `impl_line_budget`, `test_assertion_budget`: from `.claude-swarm.toml`; tighten if you can.

The brief's `## Task` section must instruct the leaf:

> Test files at `<test_files paths>` are already written and failing. Your job: write impl at `<impl_files paths>` that makes them pass. Stage outputs at `.swarm/pending/leaf-NN/` mirroring destination paths from the project root. Do not modify the test files. Do not create any files outside `impl_files`.

### 2.5 Write per-leaf failing tests

For each brief, write its `test_files` path(s) with a failing test that exercises only that leaf's contract symbols.

**Spec Link Rule** — every test file MUST begin with a header comment of this exact shape:

```
# spec: <spec_path>::<section>::AC-<N>
```

SQL test files (pgTAP, etc.) may use `--` instead of `#`: `-- spec: <spec_path>::<section>::AC-<N>`.

Example: `# spec: specs/cache.md::Acceptance criteria::AC-3`.

This header is the leaf's traceability anchor. Phase 3's invariant check greps for it; missing or malformed header → audit FAIL.

After writing each test, run it once to confirm RED. If GREEN: the test does not actually exercise the slice — revise. Do not advance to Phase 3 with a green test in a brief footprint.

---

## Phase 3 — Audit briefs

Run the deterministic invariant check:

```bash
python ~/.claude/skills/swarm-shared/scripts/check_invariants.py
```

Optional flags: `--briefs-dir <path>`, `--root <path>`.

The script reads `.claude-swarm.toml`, parses every `leaf-*.md` in `briefs_dir`, and validates:

- **non-overlap** — no two same-wave briefs name the same file; no brief touches parent-owned globs.
- **no-design** — `spec_lines` concrete; `contract_imports` resolve in the locked contract; no ambiguous verbs in task prose.
- **sizing** — `impl_line_budget` ≤ `max_impl_lines`; `test_assertion_budget` ≤ `max_test_assertions`.
- **spec-link** — every brief-declared test file path starts with `# spec: ...::AC-N` header (or `-- spec: ...::AC-N` for SQL).

Exit 0 = all pass, exit 1 = findings, exit 2 = config error.

### 3.1 Codebase-preconditions verification

For every brief with `codebase_preconditions:` frontmatter entries, run each `verify:` shell command from project root. Any non-zero exit → **FAIL: codebase-preconditions** for that brief.

For briefs without `codebase_preconditions:` whose task prose contains claim-words ("already", "in place", "exists as of", "previously added", "we have", "was admitted in wave"): emit an **Advisory** (non-blocking) recommending the parent add a `verify:` command.

### 3.2 Render verbatim

Show the script output to yourself (the overlord) and to the user. Do not paraphrase. The leaf_id + invariant + reason all matter for fixing the brief.

### 3.3 On FAIL

For each failing brief: read it, identify the offending line, fix the brief inline (or re-run Phase 2 if the failure is structural — wrong slicing, fat-file collision the dependency map missed). Then re-run the audit. Do not advance to Phase 4 with any FAIL outstanding.

If FAIL is on **non-overlap**, surface both resolution paths (sequential waves vs prep-step split) — these are seam-axis decisions, present them to the user.

---

## Phase 4 — Spawn leaves

After Phase 3 reports `all PASS`, spawn one sub-agent per brief **in parallel** — a single message with N `Task()` tool calls, not N sequential turns.

### 4.1 Per-leaf prompt shape

Each `Task()` call gets a self-contained prompt:

```
You are leaf-NN of a TDD cascade. Read your brief at <briefs_dir>/leaf-NN.md
in full before doing anything.

Your test file(s) are already written at <test_files paths> and are failing.
Your job: write impl at <impl_files paths> that makes them pass.

Stage your output at .swarm/pending/leaf-NN/ mirroring the destination paths
from the project root (e.g. src/cache.py → .swarm/pending/leaf-NN/src/cache.py).

Do NOT modify test files. Do NOT create files outside impl_files. Do NOT
edit any file in do_not_edit. Do NOT make design decisions — if anything
is ambiguous, write a question to .swarm/questions/leaf-NN-Q<n>.md and
proceed under best-guess (record the guess in leaf-NN.ASSUMPTIONS.md with
unanswered: true).

When your test(s) go green in isolation, report back: "leaf-NN green" plus
a summary of what you staged.
```

### 4.2 Subagent type selection

Default to cavecrew for every leaf when it's available — its agents are caveman-compressed (cheaper reports back to the overlord) and each has a narrower blast radius than a general-purpose agent, which matches the brief's footprint discipline. Pick by capability fit, not by habit:

- **`caveman:cavecrew-builder`** — default choice for a normal impl leaf. Needs only `Read, Edit, Write, Grep, Glob` and ≤ 2 impl files (it hard-refuses at 3+). Use it whenever the brief's `impl_files` count and required tools fit inside that.
- **Brief needs something cavecrew-builder can't do** — `WebSearch`/`WebFetch` (external API shape lookup, doc lookup), `NotebookEdit`, 3+ impl files, or any tool outside `Read, Edit, Write, Grep, Glob` — fall back to `general-purpose`. Check the brief's tool footprint before spawning, don't discover the refusal mid-wave.
- **`caveman:cavecrew-investigator`** — not used for impl leaves (it's read-only), but reach for it inline during Phase 2/3 if you need a quick file-locator pass without burning overlord context.

This is a hint, not a hard rule. The brief's footprint discipline is the actual safety net; the choice of sub-agent type is performance optimization. If a cavecrew-builder leaf hard-refuses mid-spawn, re-spawn that one leaf as `general-purpose` — don't downgrade the whole wave.

### 4.3 Wait for all leaves to report

Do not advance to Phase 5 until every spawned leaf has reported green-in-isolation. A leaf that reports red after multiple attempts → escalate to user (the leaf may need a re-spawn with corrected brief, or the brief itself was wrong).

---

## Phase 5 — Wait + aggregate sweep

All leaves reported green. Before any admission:

### 5.1 Wave-snapshot init

Compute SHA-256 of every file in the repo that is NOT declared in any wave-N brief's `test_files` + `impl_files`. Write to `.swarm/wave-<wave>.snapshot.json`:

```json
{
  "wave": <wave>,
  "created_at": "<ISO timestamp>",
  "leaf_owned_paths": ["src/cache.py", "tests/test_cache.py", ...],
  "hashes": {"<path>": "<sha256>", ...}
}
```

Skip files matching `.git/**`, `.swarm/**`, `__pycache__/**`, `node_modules/**`, `.venv/**` (plus any `snapshot_ignore` entries in `.claude-swarm.toml`).

### 5.2 Aggregate assumption-sweep

Read every `<briefs_dir>/leaf-NN.ASSUMPTIONS.md`. Categorize entries:

1. **Contradicts the spec.** Assumption picks a value the spec explicitly contradicts.
2. **Contradicts the bible.** Assumption picks a value the source-of-truth doc forbids.
3. **Cross-leaf contradiction.** Two leaves made incompatible assumptions about the same shared interface.
4. **Fabricated symbol or path.** References a type/function/file that does not exist in the contract or repo.
5. **Compounded inference.** A leaf assumption is justified by another assumption rather than by a spec line or contract symbol.

Write `.swarm/wave-<wave>.SWEEP.md`:

```markdown
# Wave <wave> assumption-sweep

## Summary
- Total assumptions logged: N
- Flagged: M (by category)

## Flagged entries

### [leaf-NN / category K]
- Assumption: "<quote>"
- Conflicts with: <other entry / spec line / bible section>
- Damage assessment: <blast radius>
- Patch suggestion: <minimal fix, no redo>
```

Present flagged entries to the user. Default bias: patch, do not redo — redo costs an afternoon, patch usually costs minutes. User decides per entry.

If zero entries flag, write the file anyway with a single line: `Assumption-sweep clean. N assumptions reviewed, none drift.` G7 in Phase 6 requires the file to exist and to be newer than every leaf ASSUMPTIONS.

### 5.3 Open-question + proposal triage

- List `.swarm/questions/leaf-NN-Q*.md`. For each, ensure either an answer at `.swarm/answers/leaf-NN-Q<n>.md` exists OR the leaf's ASSUMPTIONS file tags it `unanswered: true`. If neither, the leaf made a silent decision — escalate to user for an answer before Phase 6.
- List `.swarm/proposals/leaf-NN.md`. Resolve every `status: pending` proposal (parent applies + marks `accepted`, OR `rejected` / `superseded`). G4 in Phase 6 blocks on `pending`.

---

## Phase 6 — Admission loop

For every leaf with staged output at `.swarm/pending/leaf-NN/`, in ascending NN order:

### 6.0 Bypass detection

Read `.swarm/post-review-log.md`. List all `leaf-NN.md` files in `briefs_dir` whose NN predates the current leaf. Any prior leaf_id absent from the log is a bypass — it was never gated. If bypass found:

> ⚠ BYPASS: `leaf-NN` has a brief but no post-review-log entry. The file-match rule, parent-owned check, and umbrella were never verified for it. Confirm whether to audit now or accept the risk before continuing.

Do not silently continue past a detected bypass.

If `post-review-log.md` exists but lacks the required header (see 6.7), warn — the audit trail may have been tampered with.

### 6.1 G7 wave-sweep check (first admission of wave only)

If this is the first admission for this wave: require `.swarm/wave-<wave>.SWEEP.md` to exist and to have an mtime newer than every `leaf-NN.ASSUMPTIONS.md` for this wave. If missing → block. If older than any leaf ASSUMPTIONS → block (re-run Phase 5.2).

For subsequent admissions of the same wave, skip this gate (it passed at first admission).

### 6.2 Verify staging non-empty

`.swarm/pending/leaf-NN/` must exist and contain ≥ 1 file. If empty: reject — the leaf reported green but staged nothing. Re-spawn or escalate.

### 6.3 File-match rule

Read the brief. Take the union of `test_files` + `impl_files`; call it `declared`. The staging directory must contain exactly `declared` — same count, same paths (relative to project root). No extras, no missing, no renames.

- Count mismatch → reject.
- Path mismatch → reject.

When `test_owned_by: parent` (default in this skill — overlord wrote the tests), the test files in `declared` are still in scope for file-match (the leaf may not modify them, but they live at the same paths the brief declares).

### 6.4 G1 parent-owned check

For every staged file path, check it does NOT match any glob in `parent_owned`. Any match → reject. A leaf that needed to touch parent territory made a design decision the cascade forbids; the right fix is a contract proposal (Phase 5.3), not a direct edit.

### 6.5 Gate sweep (G2–G6)

- **G2 ASSUMPTIONS file** — note presence/absence. Do not block on absence (means brief was concrete). Do block if brief's prose implies inference happened but no log exists.
- **G3 open-question** — every published question must have a matching answer OR an ASSUMPTIONS entry tagged `unanswered: true`. If a parent answer disagrees with the leaf's recorded inference → block (the leaf wrote against the wrong assumption).
- **G4 contract-proposal** — `.swarm/proposals/leaf-NN.md` must not be `status: pending`. If `accepted`, verify the target parent-owned file actually contains the change (grep for an identifying line).
- **G5 wave-snapshot integrity** — for every path in `.swarm/wave-<wave>.snapshot.json` that is NOT in this leaf's footprint, recompute SHA-256. Any drift → block (some leaf wrote outside its staging dir).
- **G6 escalation-trigger** — for every `escalation_triggers:` entry with a `detect:` command in this brief, run the command with `$STAGING_DIR=.swarm/pending/leaf-NN/`. If a trigger fires and no `.swarm/escalations/leaf-NN.md` exists → block.

### 6.6 Umbrella pre-admission

Run `umbrella_test_cmd`. Capture per-test named results — for pytest, add `-v --tb=no -q` if not already present. Record `pre_passing_tests` (set of named passes) and `pre_count`.

If the runner emits count-only output, note: per-test regression detection will be count-only (weaker gate).

### 6.7 Copy + post-admission umbrella

For every path in the brief's `test_files + impl_files`: if a file exists at that destination, snapshot it to `.swarm/backups/leaf-NN/<path>` (mirroring the dest layout). If no file exists yet (new file), record the absence — revert will delete instead of restore.

Copy every staged file from `.swarm/pending/leaf-NN/` to its destination path. All declared files copied; no partial admissions.

Run `umbrella_test_cmd` again. Capture `post_passing_tests` + `post_count`.

If the brief has an `## Acceptance` block with a test command, run it as a second independent gate. Both umbrella and brief acceptance must pass.

### 6.8 Decide

**Per-test regression check first** (regardless of net count):

- `regressed = pre_passing_tests − post_passing_tests`
- Non-empty → **revert** (skip to 6.9b).
- Count-only mode → skip set-diff, note: count-based gate only, weaker.

**Net count + expected delta:**

- More tests pass → admit (6.9a).
- Same → yellow flag, possible integration-boundary slice; ask user before admitting.
- Fewer → revert (6.9b).

### 6.9a Admit

- Staged files are already in place (copied in 6.7).
- Delete `.swarm/pending/leaf-NN/`.
- If `post-review-log.md` does not yet exist, create with this header:

```
# Post-Review Log — append-only, do not edit manually
# Editing this file invalidates bypass-detection.

| leaf_id | files | delta | timestamp | status |
|---------|-------|-------|-----------|--------|
```

- Append one row:

```
| leaf-NN | <impl_files>, <test_files> | +N | <ISO timestamp> | clean |
```

The log is append-only. Never edit, reorder, or delete entries.

- If `graphify_cmd` is set, run it and inspect for unexpected couplings (new import edge between leaf-owned modules that wasn't in the design). Flag for user; do not block.

### 6.9b Revert

- For every backup under `.swarm/backups/leaf-NN/`: overwrite the destination with backup contents.
- For every declared file that had no backup (new file): delete from destination.
- Delete `.swarm/pending/leaf-NN/`.
- Append to `post-review-log.md`:

```
| leaf-NN | <impl_files>, <test_files> | REVERTED | <ISO timestamp> | regression: <test-name> |
```

- Append a `## Post-review regression` block to `<briefs_dir>/leaf-NN.md` noting the regressed test + staged diff summary.
- Continue the admission loop with the next leaf — one revert does not stop the rest of the wave.

---

## Phase 7 — Final report

After every leaf in the wave has been processed:

### 7.1 Apex test (if configured)

If `apex_test_cmd` is set in `.claude-swarm.toml`, run it. Apex is the behavioral integration test — distinct from `umbrella_test_cmd` (per-leaf isolation). Apex catches the failure mode where every leaf's umbrella passed but the integration composes incorrectly.

Apex failure does NOT auto-revert (multiple leaves admitted; attributing the failure to one is a separate forensic step). Report the failure + suggest investigation paths (likely candidate: any leaf whose test was source-grep heavy rather than behavioral).

### 7.2 Report

Print to the user:

```
Wave <wave> complete.

| leaf    | delta | status   |
|---------|-------|----------|
| leaf-01 | +2    | clean    |
| leaf-02 | REVERTED | regression: tests/test_cache.py::test_miss |
| ...     |       |          |

Totals: N admitted, M reverted, K escalated.
Apex: <PASS | skipped | FAILED>.
```

### 7.3 Direction for follow-ups

- For each reverted leaf: name the regressed test, point at the appended `## Post-review regression` block, suggest re-spawn with corrected brief.
- For each escalation (G3/G4/G6 blocks resolved during the loop): list what got resolved and how.
- For wave-sweep flags accepted as patches: confirm the patches landed.

Do not end the turn here — Phase 8 runs automatically right after the report, no separate user trigger needed. Every gate through Phase 7 checks "did the leaf's test pass" — none of them check "was the test worth passing" or "is this code any good." Phase 8 is the one pass that assumes both are wrong and makes someone prove otherwise.

---

## Phase 8 — Adversarial audit

Runs once per wave, after Phase 7's report, against everything admitted this wave (skip leaves that reverted — nothing to audit). The posture is adversarial by design: every gate up to now was a leaf proving its own test green. Nothing so far has asked whether the test encodes the real requirement, or whether the code behind it is something a senior engineer would sign off on. This phase hires a skeptic for that job.

### 8.1 Overlord compiles the goal-trace

Only the overlord chat has the conversation — a fresh sub-agent starts blank, so this step has to happen here, not in the sub-agent. Pull together, in one file `.swarm/wave-<wave>.AUDIT-BRIEF.md`:

- **User's ask, verbatim.** Quote the actual request(s) that led to this wave — the original feature ask, plus any mid-wave corrections or scope changes the user gave in chat. Paraphrase only where the user's message was very long; otherwise quote.
- **Locked spec** — path + the Summary and Acceptance Criteria sections in full.
- **Umbrella test file path(s)** and **every admitted leaf's** `impl_files` + `test_files` (from `post-review-log.md`, `status: clean` rows only).
- **Anything already flagged and dismissed** — wave-sweep entries the user decided not to act on, yellow-flags admitted anyway. The auditor should know what's already been litigated so it doesn't re-relitigate a decision the user already made, but it can still disagree if the dismissal looks wrong in hindsight.

This is a compilation step, not a judgment step — don't pre-filter what looks fine. The auditor forms its own opinion in 8.3.

### 8.2 Spawn the auditor

Spawn one `caveman:cavecrew-reviewer` agent (fall back to `general-purpose` with an explicit "assume it's wrong" instruction if cavecrew isn't available) with `.swarm/wave-<wave>.AUDIT-BRIEF.md` plus this framing:

```
You are auditing wave <wave> of a TDD cascade. Default posture: assume the
umbrella test and the admitted code are BOTH wrong until you've checked hard
enough to be confident otherwise. Passing tests only prove the code matches
the test — they prove nothing about whether the test matches what the user
actually asked for. That's your job to check.

Your mandate is to actively TRY TO REFUTE the admission, not to confirm it
looks fine. For each stage below, go in looking for the strongest reason
this wave should NOT have been admitted — don't settle for "seems okay" as
a default verdict. This matters because agreement-seeking review is a real,
documented failure mode: in one published case, 80+ independent review
agents — including dedicated adversarial reviewers — unanimously endorsed a
vulnerability that didn't exist, because each one was implicitly checking
"does this look plausible" rather than "can I prove this wrong." A single
agent that actually tried to disprove the finding (ran the code, checked
the real behavior) caught what the other 80 missed. You are that agent.
Confirmation is not your default; it's a conclusion you have to earn by
failing to find a problem after genuinely trying.

Every finding you report — at any severity, 🔴/🟡/🔵/❓ — must cite the
concrete evidence behind it: a quote from the code, the test assertion
text, the spec line, or (if you can run one) an actual command/test output.
"This looks wrong" is not a finding; "line N does X, which contradicts
AC-3's requirement that Y" is. If you can't point to the specific evidence,
you haven't finished checking — keep looking or downgrade to a ❓ question
you flag as unverified, don't report it as a settled finding.

Read .swarm/wave-<wave>.AUDIT-BRIEF.md first. Then work in three stages, in
order:

STAGE A — Goal fidelity.
Compare the user's verbatim ask against the locked spec's Summary + Acceptance
Criteria. Does the spec actually capture what the user asked for, or did it
drift, narrow, or silently drop a requirement during lite-discovery? Flag any
AC that doesn't trace back to something the user said, and any user requirement
with no corresponding AC.

STAGE B — Umbrella test coverage.
Read the umbrella test file(s) in full. For each Acceptance Criterion, find the
assertion(s) that would fail if that AC's behavior broke. If you can't find one,
that AC is UNTESTED regardless of what the test suite reports. Call out:
  - assertions that check the test ran (mocks, source-grep, "no exception raised")
    rather than the actual observable behavior the AC describes
  - ACs with no assertion at all
  - assertions weaker than the AC requires (e.g. AC says "returns sorted list",
    test only checks the list is non-empty)
Do not accept "the test passed" as evidence the AC is covered. Read what it
actually asserts.

STAGE C — Code quality.
Read every admitted impl file **as a diff arriving with no explanation** —
judge it on what it actually does, not on what its comments, docstrings, or
variable names claim it does. A comment saying "this is safe because X" or
"handles the edge case" is not evidence of anything; only the code's real
behavior is. You are looking for what a senior engineer would flag in
review, not just what breaks the test — the code passed its narrow test
already, so a bug that survived is one the test doesn't exercise. Look for:
  - actual bugs / wrong behavior the umbrella test doesn't cover
  - inefficiency (needless O(n^2), repeated work, allocations in hot paths)
  - code slop: dead code, copy-pasted near-duplicates, overbroad
    try/except, magic values that should be named, functions doing two jobs
  - missing error handling at real boundaries (not defensive checks on
    internal invariants that can't happen)
  - anything that technically satisfies the brief but wouldn't survive a
    real code review

Report each stage separately, findings only, severity-tagged as usual
(🔴 bug, 🟡 risk, 🔵 nit, ❓ question), each finding paired with the evidence
that grounds it (see above). If a stage is genuinely clean, say so in one
line — don't manufacture findings to fill space, but don't let "it's
probably fine" pass without having actually checked and tried to refute.
```

### 8.3 Present findings, don't auto-revert

Render the auditor's report to the user verbatim, organized under its three stage headers. This phase never reverts or re-spawns leaves on its own — it surfaces what a skeptical second pass found and lets the user decide what's worth acting on, same as the wave-sweep in Phase 5.2. For each 🔴/🟡 finding, suggest the fix path: goal-fidelity gaps go back to spec (re-open Phase 1.A for that AC), test-coverage gaps mean writing a stronger umbrella assertion and re-running the affected leaf's admission, code-quality findings can usually be patched directly without a full re-spawn.

Append the report to `.swarm/wave-<wave>.AUDIT.md` for the record. Do not fold it into `post-review-log.md` — that log is admission history, not review commentary, and stays append-only in its existing shape.

End the turn after presenting.

---

## What this skill does NOT do

- **Write impl code itself.** The overlord writes spec, contract, umbrella, and per-leaf tests. Impl is the leaf's job.
- **Delegate planning to a sub-agent.** Spec drafting, brief emission, gate enforcement all stay in the overlord chat. Delegating planning re-introduces the failure mode the cascade exists to prevent: a non-overlord making design decisions invisible to the audit trail.
- **Use git.** All state lives in `.swarm/`. Staging dir replaces branches; backup dir replaces revert; post-review-log replaces git log; per-test set-diff replaces commit metadata for regression attribution. The cascade's guarantees are equivalent; the one thing lost is cryptographic commit signing (acceptable in single-project trust models).
- **Auto-spawn leaves before Phase 3 passes.** Phase 4 only fires after Phase 3 reports `all PASS`. Pre-audit spawn re-introduces every failure mode the audit prevents.
- **Make architecture decisions silently.** Phase 1 surfaces Bible Compliance + each draft as an explicit approval gate. Phase 2 surfaces fat-file collisions + leaf-count guardrails. Phase 3 surfaces invariant violations. Phase 5 surfaces aggregated assumption drift. Phase 6 surfaces per-leaf gate failures. Silence at any of these is the failure mode; explicit user choice is the success path.

---

## File-mediated coordination (recap)

Leaves never message each other directly — the cascade is a tree, leaf-to-leaf edges would destroy regression attribution. Three file-mediated patterns let them coordinate, all parent-arbitrated:

| Pattern | What | Gate |
|---|---|---|
| Sibling-ASSUMPTIONS read | Leaf reads (never writes) sibling `.ASSUMPTIONS.md` before logging its own inferences. Catches drift at leaf-time. | Brief boilerplate; no skill enforcement |
| Question ledger | Leaf publishes `.swarm/questions/leaf-NN-Q<n>.md`; parent answers in `.swarm/answers/`. Leaf proceeds under best-guess, tags ASSUMPTIONS `unanswered: true`. | G3 (Phase 6.5) |
| Contract proposals | Leaf publishes `.swarm/proposals/leaf-NN.md` instead of editing parent-owned files. Parent applies + marks accepted. | G4 (Phase 6.5) |

Full theory at `~/.claude/skills/swarm-shared/references/playbook.md`.

---

## Task-size discipline

The leaf-count guardrail in Phase 2.2 (warn > 12, refuse > 16) reflects empirical observation: past ~12 simultaneous sub-agents in a single wave, drift between siblings climbs, the overlord's context fills with leaf reports, and the assumption-sweep starts missing cross-leaf contradictions because it gets long.

When the spec genuinely needs more than 12 slices, break into sequential waves. Wave 1 admits, wave 2 picks up; cross-wave file edits are explicitly allowed (`wave:` field on the brief sequences them). One large feature, two clean waves of 8–10 leaves each, is materially safer than one wave of 18.

The refusal at >16 is non-negotiable in this skill. If the user wants to push past it, that decision belongs upstream — re-scope the spec, not the gate.

## Shard-based parallelism, for specs that outgrow one wave

The 12/16 cap above is a ceiling on *one wave's* leaf count, not on how much work the cascade can do in parallel overall. A large, genuinely-decomposable spec (dozens of independent slices, no shared-file dependencies between groups of them) doesn't have to run those groups one sequential wave at a time — it can run several waves **concurrently**, each in its own isolated staging tree, the same way a large real-world multi-agent rewrite (64 concurrent Claude instances porting a 500K-line codebase, organized as 4 isolated worktrees of 16 agents each rather than one flat pool of 64) actually scaled: the ceiling on parallelism there wasn't the agents' reasoning quality, it was **write-collision on shared state** — agents running conflicting git commands against the same checkout. The fix was architectural isolation (separate worktrees, no cross-shard git operations), not a bigger flat pool.

Manager-mode's equivalent shared state is `.swarm/pending/`, `post-review-log.md`, and the wave snapshot/sweep files — those are exactly what breaks if two waves try to run concurrently against the same paths. A **shard** is an isolated copy of that state:

- Instead of one `.swarm/pending/leaf-NN/` staging tree, run N parallel staging trees: `.swarm/pending/shard-A/leaf-NN/`, `.swarm/pending/shard-B/leaf-NN/`, and so on — one per concurrent wave.
- Each shard gets its own wave number, its own `post-review-log.md` entries (still one shared log file is fine since admission is still one-at-a-time per shard; the append-only format already tolerates interleaved waves), and its own `.swarm/wave-<wave>.snapshot.json` / `.SWEEP.md` / `.AUDIT.md`.
- **No file overlap across shards, ever** — this is the same non-overlap invariant Phase 3 already enforces within one wave's briefs, just extended to hold across every shard running at the same time. Two shards racing to write the same file is exactly the collision this whole pattern exists to prevent; if the dependency map from Phase 2.1 can't guarantee that separation up front, don't shard — run sequential waves instead.
- Each shard still obeys the normal ≤12/warn-13–16/refuse->16 leaf-count cap on its own. Sharding is how you go past that ceiling *in aggregate* without raising it for any single wave — mirrors 4 isolated groups of 16 rather than one ungoverned pool of 64.

This is additive, not a replacement for the default path. Most specs fit in one wave and don't need this section at all — reach for shards only when the dependency map already shows multiple large, file-disjoint groups of slices, and running them sequentially would just be waiting with no coordination benefit.
