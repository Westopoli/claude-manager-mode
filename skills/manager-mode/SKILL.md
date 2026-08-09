---
name: manager-mode
description: Single-command parallel-agent TDD cascade. Use when the user wants to build a feature with parallel sub-agents — phrases like "swarm this", "decompose and spawn", "run the cascade", "spawn N agents on this", "build feature X with parallel agents", "set up the wave", "let's parallelize this". Walks through all phases internally (preflight → lite-discovery → decompose → audit → spawn → wait + sweep → admission loop → final report) — no sibling slash commands to chain. Overlord chat writes spec/contract/umbrella (lite drafts if missing); a separate shard-test-writer writes per-leaf failing tests; leaves only write impl — no agent ever grades its own tests. A fresh test-auditor per shard reviews goal-fidelity and umbrella-alignment before any leaf spawns — no post-admission adversarial pass exists. Decomposition consolidates file-disjoint slices into one leaf when they're one coherent responsibility, scored by a spec-text rubric (rule-clusters, exception branches, integrations, cross-cutting concerns), not a leaf-per-file default. File-based, no git. Hard-refuses when decomposition exceeds 16 leaves. Always invoke this when the user wants parallel sub-agent work — not separate commands for spawn / review / post-review (they no longer exist).
---

# /manager-mode — single-command parallel-agent cascade

One slash command. The overlord (this chat) drives every phase. Sub-agents only write impl against pre-written failing tests.

The cascade prevents three structural failures in parallel-agent TDD: (1) leaves stepping on each other's files, (2) leaves silently making design decisions, (3) leaves receiving slices too big to finish coherently. Phases 0–7 are the procedure for keeping those guarantees while collapsing the prior 4-command UX into one.

## Shared asset resolver

Resolve `SWARM_SHARED_DIR` once before using a shared asset. In Claude Code, use
`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/swarm-shared`; in Codex, use
`${CODEX_HOME:-$HOME/.codex}/skills/swarm-shared`. Choose the directory belonging to
the client running this skill, and verify it exists before continuing. Every
shared-asset path below is relative to `SWARM_SHARED_DIR`.

Theory: `$SWARM_SHARED_DIR/references/playbook.md`. Brief template:
`$SWARM_SHARED_DIR/references/brief-template.md`. Config schema:
`$SWARM_SHARED_DIR/references/config.md`.

---

## Phases at a glance

```
Phase 0  Preflight              — find/bootstrap .claude-swarm.toml; list which of {spec, contract, umbrella} exist
Phase 1  Lite-discovery         — fire only for missing inputs; one-question drafts, Bible Compliance footer on spec
Phase 2  Decompose              — dependency map + consolidation pass + emit briefs + shard-test-writer authors per-leaf failing tests (Spec Link Rule + composition assertion + task-size guardrail)
Phase 3  Audit briefs           — run check_invariants.py (incl. contradiction check) + codebase-preconditions + external test-quality audit (goal-fidelity + umbrella-alignment + composition); fix & re-run on FAIL
Phase 4  Spawn leaves           — N sub-agents in parallel through the client delegation adapter
Phase 5  Wait + sweep           — wait all green; aggregate assumption-sweep; write .swarm/wave-N.SWEEP.md
Phase 6  Admission loop         — per leaf: G1–G9 + file-match + umbrella pre/post + admit-or-revert + log
Phase 7  Final report           — counts + follow-up direction
```

If all three inputs (spec, contract, umbrella RED) already exist on disk, Phase 1 is skipped entirely. That is the common path for a returning project.

---

## Phase 0 — Preflight

**0.1 Locate config.** Walk up from cwd until a `.claude-swarm.toml` is found. If none: copy `$SWARM_SHARED_DIR/templates/.claude-swarm.toml.example` to `<project_root>/.claude-swarm.toml`, then ask the user to fill each required field — do not guess values, wrong values here propagate everywhere:

- `spec_dir` — directory for the spec file (often `specs/`).
- `briefs_dir` — leaf briefs go here. Default derives per-cascade: `.swarm/<cascade-slug>/briefs/`, where `<cascade-slug>` comes from the spec's `<name>` (0.2), normalized — see config.md's "Cascade-slug derivation" note. Set explicitly here to override (e.g. to force a flat shared dir across cascades).
- `type_contract_path` — contract file (often `src/<pkg>/types.py`).
- `umbrella_test_cmd` — command that runs the umbrella (e.g., `pytest tests/umbrella.py`).
- `parent_owned` — globs leaves cannot touch.

**0.2 Read inputs.** List which of these three exist on disk:

- Spec at `<spec_dir>/<name>.md` (ask the user for `<name>` if ambiguous; do not silently pick).
- Type contract at `<type_contract_path>`.
- Umbrella test at the path `umbrella_test_cmd` would discover.
- Once `<name>` is known (from the spec filename, or the user's answer if ambiguous), resolve `briefs_dir` per the default derivation in 0.1 if not explicitly set in config. Lock this before 0.3's guard check.

**0.3 Existing-wave guard.** Auto-derived `briefs_dir` (0.1/0.2) already scopes each distinct spec `<name>` to its own directory, so this guard now only fires on the narrower remaining case: the *same* cascade slug being run again (re-run, or intentionally continuing the same cascade) and `<briefs_dir>` already contains `leaf-*.md`. If so, stop and ask the user how to scope this run:

- New slug for this run (e.g. append `-v2` / a date suffix to `<name>`) — sets a fresh `briefs_dir`, same as any two different-named cascades already get by default.
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

Read the locked spec + contract. Produce one leaf brief per slice at `<briefs_dir>/leaf-NN.md`. Per-leaf failing tests are written in 2.6 by a spawned shard-test-writer, never by the overlord directly. Leaves only write impl against pre-written failing tests.

### 2.1 Dependency map

If `graphify_cmd` is set, run it. Otherwise do a manual import-graph scan of the impl files you intend to assign. Identify slices such that no two slices touch the same impl file (within the same wave).

### 2.2 Consolidation pass

2.1 finds the max-safe leaf count. That's not the leaf count to use. Before assigning slices 1:1 to leaves, score each candidate by four things countable directly in the spec text — not a LOC guess:

- **Rule-clusters** — distinct decision rules/branches (validation gates, default-with-override tables; count table rows directly).
- **Exception branches** — numbered exception/edge-case sections.
- **External integrations** — distinct third-party systems touched (webhook, API, storage, email, print, etc).
- **Cross-cutting concerns** — things re-applied consistently across multiple rule-clusters (audit logging, tiered gates, redaction). The dangerous axis — a leaf can satisfy every individual rule and still violate the cross-cutting one.

One leaf, one coherent unit, when: ≤1 cross-cutting concern spans it, ≤2-3 external integrations, and its rule-clusters share one failure domain (a wrong assumption in one can't silently corrupt another's output).

Past that: split along the cross-cutting-concern or integration boundary first, not by rule count — that's where compositional bugs live. A spec section amended after a real incident counts as an added cross-cutting concern on whatever it touches — that's evidence of hidden coupling already found once.

**Completeness sweep, before finalizing the leaf list.** List every distinct requirement, invariant, and still-open/unresolved item stated anywhere in the spec — including framing sections stated once near the top (not just numbered/tabular ones), and anything an amendment or incident log flags as not yet done — and confirm each is owned by exactly one leaf or explicitly excluded with a one-sentence reason. An item with neither is a gap. Numbered/tabular sections are easy to catch this way by construction; prose stated once, and open items buried in a changelog, are exactly what this sweep exists to catch, because nothing else forces a second look at them.

### 2.2a Post-plan checklist

Run once the leaf list exists and the completeness sweep above is done — this is a second, differently-shaped pass, not a repeat of it. The sweep asks "is every item owned or excluded"; this checklist asks a fixed set of broader questions about the plan as a whole, the kind of miss that survives an item-by-item sweep because each individual item looks fine in isolation. Answer all six against the current leaf list, in order:

1. **Consumption check.** For every named entity the spec introduces (an endpoint, field, config value, external system, table) — is it actually invoked by some leaf's described behavior? An entity that's *listed* in a leaf's ownership but never *used* by anything is a silent pass-through, not coverage. Either point to what consumes it, or exclude it explicitly.
2. **Enforcement-surface check.** For every rule that coordinates across leaves or layers (not a single-leaf rule), does the leaf claiming it actually have the reach — the integration access, the composition responsibility — to make the rule true? A rule filed under a leaf just because it's topically nearby, with no leaf actually positioned to enforce it, is a misassignment even though the sweep would call it "owned."
3. **Input/output coverage check.** For every input variant the spec defines (enum values, status/severity codes, branch conditions, distinct data shapes) — is each one traced to a leaf that handles that specific case and produces the spec's stated output/behavior for it? This is stricter than the enforcement-surface check: a rule can be owned by a leaf with the right reach and still leave one named input value unrouted — the leaf handles the general case but not a spec-named exception, or a value is defined but no leaf's behavior description ever mentions transforming it. List the input space explicitly (don't rely on remembering it), then check each value against the leaf list, not just the rule that governs the value's category.
4. **Sweep-table completeness.** Does every item from the completeness sweep have its own row/entry, independent of whether it's also mentioned in a leaf's prose description? Ownership stated only in prose, with no corresponding sweep entry, leaves no audit trail that it was actually checked.
5. **Open-item sweep.** For every item the spec itself flags as not-yet-done, unresolved, or still-open (amendment logs, issue trackers, "known gap" notes) — is each one individually assigned or excluded, not just the subset that happened to already get mentioned in a leaf's description for other reasons?
6. **Implied-duty restatement.** Where a general rule implies an ongoing behavior for a specific leaf (maintain/update over time, not just create-once), does that leaf's own scope text say so explicitly, rather than relying on the general rule being satisfied by reference elsewhere?

Log the answer to each question, even when the answer is "no gap found" — a checklist with no record of having been run is indistinguishable from one that was skipped. Treat any "no" as a gap: assign, exclude with a reason, or correct the leaf list before moving to 2.3.

### 2.3 Task-size guardrail

Count planned leaves, after 2.2:

- **≤ 16:** proceed.
- **> 16:** **refuse**. Do not write the briefs. Tell the user either to re-scope the spec into a smaller wave, or to break into multiple sequential waves (wave 1 owns files A–F, wave 2 picks up files G–L after wave 1 admits cleanly).

Hard backstop, not a nudge — 2.2 is what keeps leaf count low.

### 2.4 Fat-file check (only if some impl files exist)

Unlike 2.2, this file already exists — its LOC is real, not a guess. Estimate resulting LOC (current + new work this wave adds). Target 1000-1500. Past 2500 — flag the user for review, do not continue silently:

- **(a) Sequential waves** — assign AC-X to wave 1, AC-Y to wave 2. Same file, one owner at a time.
- **(b) Prep-step split** — overlord commits a refactor that splits the file into sub-files before decomposition. See `swarm-shared/references/playbook.md` "Prep steps".

Do not pick silently. The seam-axis decision belongs to the user. Multiple ACs in one file is not itself a reason to split — 2.2 may put them in one leaf on purpose.

### 2.5 Emit briefs

For each slice, write `<briefs_dir>/leaf-NN.md` following `$SWARM_SHARED_DIR/references/brief-template.md`. Set `test_owned_by: parent` in every brief frontmatter (the leaf does not author or modify these files — ownership sits on the parent side of the cascade; see 2.6 for who actually writes them).

Key brief rules:
- `spec_lines`: concrete `int-int` range.
- `contract_imports`: only symbols present in the locked contract.
- `do_not_edit`: every other same-wave brief's `impl_files` + parent-owned globs.
- Task prose: imperative, no ambiguous verbs (decide / choose / design / determine / figure out / resolve / pick).
- Task fenced code: total non-blank lines across all fenced blocks ≤ `max_brief_code_lines` (default 10). Stub signatures + mirror-pointer snippets only. **Do not embed ready-to-paste impl bodies — the leaf authors the body.** Use shape-carriers instead: `spec_lines` refs, `contract_imports`, mirror-pointers ("match the structure of `path/to/sibling.py`"), invariant statements. Embedding the body collapses parallelism — parent absorbs leaf work, leaf becomes a copy-paste courier. Audit blocks briefs that exceed the ceiling.
- `impl_line_budget`, `test_assertion_budget`: from `.claude-swarm.toml`; tighten if you can.

The brief's `## Task` section must instruct the leaf:

> Test files at `<test_files paths>` are already written and failing. Your job: write impl at `<impl_files paths>` that makes them pass. Stage outputs at `.swarm/pending/leaf-NN/` mirroring destination paths from the project root. Do not modify the test files. Do not create any files outside `impl_files`.

### 2.6 Write per-leaf failing tests

Per-leaf tests are **not** written by the overlord directly, with no exception for small or single-wave runs. Spawn one **shard-test-writer** sub-agent per shard with the locked spec/contract and that shard's brief set only. It writes every `test_files` path in that shard, exercising only each leaf's contract symbols, and never touches impl. See `swarm-shared/references/playbook.md` "Roles" for the role's full boundary. This keeps test authorship independent of whichever agent later resolves an ambiguity in impl — the failure mode where a leaf writes a test that only certifies its own guess.

**Composition rule (mockist)** — if a leaf's `impl_files` has more than one entry, its test must include at least one interaction assertion (e.g. monkeypatch/spy proving the orchestrator actually calls the collaborator), not just output-state checks. State-only tests can't tell an unused, orphaned function from a wired-in one. See `brief-template.md`'s test-writing guidance.

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
python "$SWARM_SHARED_DIR/scripts/check_invariants.py"
```

Optional flags: `--briefs-dir <path>`, `--root <path>`.

The script reads `.claude-swarm.toml`, parses every `leaf-*.md` in `briefs_dir`, and validates:

- **non-overlap** — no two same-wave briefs name the same file; no brief touches parent-owned globs.
- **no-design** — `spec_lines` concrete; `contract_imports` resolve in the locked contract; no ambiguous verbs in task prose.
- **no-contradiction** — no rule/value cited with two different literal values across sibling briefs in the same wave/shard (heuristic, not exhaustive — catches a rule stated two ways before any leaf has to guess which one is real).
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

### 3.4 Test-quality audit (external, before any leaf spawns)

Once a shard's tests exist (2.6) and pass the invariant audit (3.0–3.3), spawn one fresh-context auditor per shard — same `caveman:cavecrew-reviewer`/`general-purpose`-fallback pattern used elsewhere in this skill, scoped to tests only — to audit that shard's test output before any leaf ever sees it. This is where test quality is judged: the overlord never grades its own (or the shard-test-writer's) tests directly, and no agent-based review of the implementation runs after admission. G8 (`test_quality_gate.py`, Phase 6.5) remains the mechanical backstop against orphaned/unreachable impl and weak assertions — this step is upstream and agent-judgment-based, G8 is downstream and scripted; they check different things and neither replaces the other.

#### 3.4.1 Overlord compiles the test-audit context package

Before spawning, write `.swarm/audits/wave-<wave>/<shard-or-default>/TEST-AUDIT-BRIEF.md` containing everything the auditor needs and nothing it must infer:

- **Umbrella test.** Full text of `umbrella_test_cmd`'s test file(s) — the auditor needs the top-level behavioral contract to judge whether a shard's tests are a coherent decomposition of it, not just traced to a spec line in isolation.
- **The shard's own stated goal.** The relevant spec Summary + Acceptance Criteria this shard's briefs cover, quoted, plus the shard's brief set (paths + `spec_lines` + `contract_imports` per brief).
- **The tests under audit.** Full text of every `test_files` path written in 2.6 for this shard.
- **Composition-relevant contract excerpts.** Only the locked `type_contract_path` symbols the shard's `contract_imports` reference — not the whole contract file, to keep the package bounded.
- **Sibling-shard awareness, if relevant.** If a sibling shard's brief set shares a contract symbol or an adjacent AC, name the sibling shard and quote only the overlapping symbol/AC — not its full brief set. Lets the auditor catch a test that only makes sense assuming a cross-shard interface shape nothing else confirms.
- **Anything already litigated.** Wave-sweep dismissals or yellow-flags touching this shard's territory, so the auditor doesn't re-open a decision the user already made (it may still disagree if it looks wrong).

Compilation step, not a judgment step — don't pre-filter what looks fine.

#### 3.4.2 Spawn and audit

Give the auditor `TEST-AUDIT-BRIEF.md` and this framing:

```
You are auditing shard <shard-id>'s tests before any leaf sees them. You
are a fresh-context, evidence-only reviewer with no visibility into how
these tests will later be implemented. Default posture: assume each test
is not proving what it claims to prove until you've checked hard enough to
be confident otherwise.

Check three things, in order:

1. GOAL FIDELITY — does each test actually verify this shard's stated
   goal (the spec Summary/AC excerpt in your brief), or something
   narrower/different that happens to touch the same lines?
2. UMBRELLA ALIGNMENT — read the umbrella test. For any behavior it also
   exercises that overlaps this shard, does this shard's test agree with
   the umbrella's expectation, or contradict it? A shard test that would
   pass while contradicting the umbrella's own assertion is a defect to
   catch now, not at admission.
3. TEST QUALITY — traces to spec_lines, isn't tautological, carries the
   composition assertion from brief-template.md's mockist rule when
   impl_files has 2+ entries.

Every finding needs a quote from the test, the umbrella, or the spec —
"looks thin" is not a finding. Write your report to
.swarm/audits/wave-<wave>/<shard-or-default>/TEST-AUDIT.md.
```

Dispatch one auditor per shard in parallel (shards already don't share footprint, per Phase 3's non-overlap check).

#### 3.4.3 On findings

Any 🔴/🟡 finding blocks that shard's leaves from Phase 4 spawn. The shard-test-writer (a **new** fresh spawn, not the flagged auditor and not the same context that wrote the original test) revises the offending test, confirms RED again, and 3.4.2 re-runs. For a purely mechanical fix the auditor pointed at a specific line for (e.g. a missing composition assertion), the overlord may apply it directly and record why in `TEST-AUDIT.md`'s follow-up section — do not silently wave through an unresolved 🔴.

---

## Phase 4 — Spawn leaves

After Phase 3 reports `all PASS`, spawn one sub-agent per brief **in parallel**. Use the client delegation adapter: Claude Code issues its native `Task` delegation calls; Codex calls `spawn_agent`. Dispatch the whole wave together (not sequentially) and retain every existing footprint, staging, Phase 5 sweep, and Phase 6 admission gate exactly as written.

### 4.1 Per-leaf prompt shape

Each delegation call gets a self-contained prompt:

```
You are leaf-NN of a TDD cascade. Read your brief at <briefs_dir>/leaf-NN.md
in full before doing anything.

Your test file(s) are already written at <test_files paths> and are failing.
Your job: write impl at <impl_files paths> that makes them pass.

Stage your output at .swarm/pending/leaf-NN/ mirroring the destination paths
from the project root (e.g. src/cache.py → .swarm/pending/leaf-NN/src/cache.py).

Do NOT modify test files. Do NOT create files outside impl_files. Do NOT
edit any file in do_not_edit.

Small implementation choices are yours to make and expected: internal
variable/helper names, where you draw a private helper function's
boundary within your own impl_files, ordinary control-flow shape (loop vs.
comprehension, early-return vs. nested-if), how you organize the file's
internal structure — none of that needs a question. This is deliberately
wider when your brief owns more internal surface (a single larger file
with several related functions) than when it owns a narrow slice — you own
more internal structure, so you make more of these calls, same as any
engineer owns the internals of a file they're the sole author of.

Escalate (write a question to .swarm/questions/leaf-NN-Q<n>.md and proceed
under best-guess, recording it in leaf-NN.ASSUMPTIONS.md with
unanswered: true) only for decisions with weight beyond your own file:
anything that changes a public function signature or contract symbol,
anything another leaf's test or the umbrella test depends on, an
ambiguous business rule (a numeric threshold, an ordering, a precedence
rule not pinned by spec_lines or the contract), or anything that would
require touching do_not_edit. If unsure which side a call falls on, ask:
"would a sibling leaf or the umbrella test observe this from outside my
file?" — if yes, escalate; if no, it's yours to decide.

When your test(s) go green in isolation, report back: "leaf-NN green" plus
a summary of what you staged.
```

### 4.2 Subagent type selection

Default to **`general-purpose`** for every impl leaf. `cavecrew-builder`'s toolset is `Read, Edit, Write, Grep, Glob` only — **no `Bash`** — which means it cannot itself run the leaf's test command to confirm RED-then-GREEN; it can only manually trace test-vs-impl by reading, and every leaf that hits this gap has to explicitly flag "I could not execute the tests" rather than give the overlord a real pass/fail signal. That undermines the brief's own Acceptance step ("Confirm RED... Confirm GREEN"), which assumes the leaf itself runs the command. Pick by capability fit, not by habit:

- **`general-purpose`** — default choice for a normal impl leaf. Has `Bash`, so it can actually execute `test_file`'s test command before and after implementing, and report a real (not traced) RED→GREEN result. No hard file-count refusal, so brief sizing is governed by `impl_line_budget`/`test_assertion_budget` and the brief's own no-design-decision discipline, not by an incidental tool-selection ceiling.
- **`caveman:cavecrew-builder`** — optional, narrower-blast-radius alternative for a leaf that is genuinely trivial (single small file, no need for the leaf itself to execute anything — e.g. the overlord or a downstream step will run tests) and where the caveman-compressed report is worth more than execution capability. Needs only `Read, Edit, Write, Grep, Glob` and ≤ 2 impl files (it hard-refuses at 3+). Do not reach for it by default; use it deliberately when its trade-off actually fits the leaf.
- **`caveman:cavecrew-investigator`** — not used for impl leaves (it's read-only), but reach for it inline during Phase 2/3 if you need a quick file-locator pass without burning overlord context.

This is a hint, not a hard rule. The brief's footprint discipline is the actual safety net; the choice of sub-agent type is performance optimization. If a `cavecrew-builder` leaf hard-refuses mid-spawn, or reports it could not execute its own tests, re-spawn that one leaf as `general-purpose` — don't downgrade the whole wave.

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

When `test_owned_by: parent` (default in this skill — tests are written on the parent side per 2.6, not by the leaf), the test files in `declared` are still in scope for file-match (the leaf may not modify them, but they live at the same paths the brief declares).

### 6.4 G1 parent-owned check

For every staged file path, check it does NOT match any glob in `parent_owned`. Any match → reject. A leaf that needed to touch parent territory made a design decision the cascade forbids; the right fix is a contract proposal (Phase 5.3), not a direct edit.

### 6.5 Gate sweep (G2–G6)

- **G2 ASSUMPTIONS file** — note presence/absence. Do not block on absence (means brief was concrete). Do block if brief's prose implies inference happened but no log exists.
- **G3 open-question** — every published question must have a matching answer OR an ASSUMPTIONS entry tagged `unanswered: true`. If a parent answer disagrees with the leaf's recorded inference → block (the leaf wrote against the wrong assumption).
- **G4 contract-proposal** — `.swarm/proposals/leaf-NN.md` must not be `status: pending`. If `accepted`, verify the target parent-owned file actually contains the change (grep for an identifying line).
- **G5 wave-snapshot integrity** — for every path in `.swarm/wave-<wave>.snapshot.json` that is NOT in this leaf's footprint, recompute SHA-256. Any drift → block (some leaf wrote outside its staging dir).
- **G6 escalation-trigger** — for every `escalation_triggers:` entry with a `detect:` command in this brief, run the command with `$STAGING_DIR=.swarm/pending/leaf-NN/`. If a trigger fires and no `.swarm/escalations/leaf-NN.md` exists → block.
- **G8 test-quality gate** (leaves with 2+ `impl_files` only) — run `python "$SWARM_SHARED_DIR/scripts/test_quality_gate.py" --leaf leaf-NN`. Reachability findings (a function nothing in the leaf's own impl calls — an orphaned/unwired implementation) block. Mutation findings (a function whose tests still pass after one mechanical mutation) print as advisory, not blocking by default — a single mutant can miss by bad luck rather than prove the test is weak; pass `--strict` (hardcore does) to block on those too.
- **G9 complexity gate** (all leaves) — run `python "$SWARM_SHARED_DIR/scripts/complexity_gate.py" --leaf leaf-NN`. Flags any function over `--max-cyclomatic` (default 10) decision points or `--max-nesting` (default 3) block levels. Advisory by default — a high score is not proof of a defect the way G8's reachability is, this is a new, uncalibrated heuristic (see `experiments/scaling-test/phaseH-ceiling-search/` for the evidence it should be recalibrated against) — pass `--strict` (hardcore does) to block on findings.

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

| wave | shard | leaf_id | files | delta | timestamp | status |
|------|-------|---------|-------|-------|-----------|--------|
```

- Append one row:

```
| <wave> | <shard-or-default> | leaf-NN | <impl_files>, <test_files> | +N | <ISO timestamp> | clean |
```

The log is append-only. Never edit, reorder, or delete entries.

- If `graphify_cmd` is set, run it and inspect for unexpected couplings (new import edge between leaf-owned modules that wasn't in the design). Flag for user; do not block.

### 6.9b Revert

- For every backup under `.swarm/backups/leaf-NN/`: overwrite the destination with backup contents.
- For every declared file that had no backup (new file): delete from destination.
- Delete `.swarm/pending/leaf-NN/`.
- Append to `post-review-log.md`:

```
| <wave> | <shard-or-default> | leaf-NN | <impl_files>, <test_files> | REVERTED | <ISO timestamp> | regression: <test-name> |
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

---

## What this skill does NOT do

- **Write impl code itself.** The overlord writes spec, contract, and the umbrella test; the shard-test-writer writes per-leaf tests. Impl is the leaf's job.
- **Delegate the DECISION or hide the review.** Spec approval, contract locking, brief emission, and gate enforcement are decisions and always happen in the overlord chat, visible to the user. What the overlord MAY do (see "Delegated drafting passes" below) is spawn a fresh sub-agent to produce a DRAFT of a hard synthesis artifact — a proposed decomposition shape, a proposed spec section, a proposed resolution of an ambiguity — which the overlord must then independently verify against everything it already knows (the spec, the contract, prior wave history, the user's own words in this chat) before adopting any part of it. The draft and the overlord's verification/edits are both rendered to the user; nothing about the reasoning is hidden. This is drafting-labor delegation, not decision delegation. If the overlord ever adopts a drafted artifact without recording its own independent check against it, that IS the banned failure mode — the boundary is the verification step, not the existence of a draft.
- **Use git.** All state lives in `.swarm/`. Staging dir replaces branches; backup dir replaces revert; post-review-log replaces git log; per-test set-diff replaces commit metadata for regression attribution. The cascade's guarantees are equivalent; the one thing lost is cryptographic commit signing (acceptable in single-project trust models).
- **Auto-spawn leaves before Phase 3 passes.** Phase 4 only fires after Phase 3 reports `all PASS`. Pre-audit spawn re-introduces every failure mode the audit prevents.
- **Make architecture decisions silently.** Phase 1 surfaces Bible Compliance + each draft as an explicit approval gate. Phase 2 surfaces fat-file collisions + leaf-count guardrails. Phase 3 surfaces invariant violations. Phase 5 surfaces aggregated assumption drift. Phase 6 surfaces per-leaf gate failures. Silence at any of these is the failure mode; explicit user choice is the success path.

---

## Delegated drafting passes (plan-mode-style, reviewed-authorship)

For a genuinely hard synthesis sub-decision inside a phase the overlord already owns — e.g. Phase 2.1's dependency map on a large/unfamiliar codebase, or resolving a hard spec ambiguity during Phase 1 lite-discovery before locking — the overlord chat may spawn a fresh-context sub-agent to do a deep exploration/synthesis pass and report back a distilled draft, the same pattern Claude Code's own plan mode uses (an Explore/Plan agent does the deep digging, the orchestrating chat reviews and decides, everything renders to the user for approval).

Available at exactly three points, and nowhere else:

- **Phase 2.1 (dependency map)** — on a codebase with no `graphify_cmd` configured and a large/unfamiliar import graph, the overlord may spawn a read-only investigator (`caveman:cavecrew-investigator` fits) to produce a draft dependency map. The overlord must independently confirm non-overlap against the draft before slicing briefs from it.
- **Phase 2.2 (consolidation pass)** — on a large or unfamiliar spec, the overlord may spawn a fresh sub-agent to draft the consolidation grouping (which slices merge into which leaves, with rubric rationale). The overlord must independently run 2.2's completeness sweep against the draft before adopting it — a delegated draft is exactly where a missed requirement is most likely to hide, since the sub-agent doesn't share the overlord's accumulated context of the conversation or prior waves.
- **Phase 1 lite-discovery, structural ambiguity resolution** — when the user's ask genuinely underspecifies something structural (not a one-line clarifying question — a real synthesis question, e.g. "what's the natural module boundary for this feature given the existing codebase's conventions"), the overlord may spawn a fresh sub-agent to propose a resolution with rationale, then present BOTH the sub-agent's proposal and the overlord's own assessment of it at the normal Phase 1 approval gate. The user still approves/edits/restarts exactly as today.

Not available anywhere else: brief emission (2.5), the invariant audit (Phase 3), admission (Phase 6), and the test-audit gate itself (3.4) never delegate their actual decision to a fresh sub-agent's report without the overlord's own independent check being the thing that actually gates. Delegating the CHECK itself — rather than upstream drafting labor feeding into a check the overlord still performs — is exactly the invisible-decision failure mode this section exists to prevent.

---

## File-mediated coordination (recap)

Leaves never message each other directly — the cascade is a tree, leaf-to-leaf edges would destroy regression attribution. Three file-mediated patterns let them coordinate, all parent-arbitrated:

| Pattern | What | Gate |
|---|---|---|
| Sibling-ASSUMPTIONS read | Leaf reads (never writes) sibling `.ASSUMPTIONS.md` before logging its own inferences. Catches drift at leaf-time. | Brief boilerplate; no skill enforcement |
| Question ledger | Leaf publishes `.swarm/questions/leaf-NN-Q<n>.md`; parent answers in `.swarm/answers/`. Leaf proceeds under best-guess, tags ASSUMPTIONS `unanswered: true`. | G3 (Phase 6.5) |
| Contract proposals | Leaf publishes `.swarm/proposals/leaf-NN.md` instead of editing parent-owned files. Parent applies + marks accepted. | G4 (Phase 6.5) |

Full theory at `$SWARM_SHARED_DIR/references/playbook.md`.

---

## Task-size discipline

Phase 2.3 refuses past 16 leaves — drift between siblings, context fill, missed cross-leaf contradictions. Phase 2.2's consolidation pass is what should keep most waves well under this; a wave still near 16 after honest consolidation judgment likely needs re-scoping, not a bigger cap.

Past 16 even after consolidation: split into sequential waves (`wave:` field sequences cross-wave file edits).

The refusal at >16 is non-negotiable in this skill. If the user wants to push past it, that decision belongs upstream — re-scope the spec, not the gate.

## Shard-based parallelism, for specs that outgrow one wave

The 16 cap above is a ceiling on *one wave's* leaf count, not on how much work the cascade can do in parallel overall. A large, genuinely-decomposable spec (dozens of independent slices, no shared-file dependencies between groups of them) doesn't have to run those groups one sequential wave at a time — it can run several waves **concurrently**, each in its own isolated staging tree, the same way a large real-world multi-agent rewrite (64 concurrent Claude instances porting a 500K-line codebase, organized as 4 isolated worktrees of 16 agents each rather than one flat pool of 64) actually scaled: the ceiling on parallelism there wasn't the agents' reasoning quality, it was **write-collision on shared state** — agents running conflicting git commands against the same checkout. The fix was architectural isolation (separate worktrees, no cross-shard git operations), not a bigger flat pool.

Manager-mode's equivalent shared state is `.swarm/pending/`, `post-review-log.md`, and the wave snapshot/sweep files — those are exactly what breaks if two waves try to run concurrently against the same paths. A **shard** is an isolated copy of that state:

- Instead of one `.swarm/pending/leaf-NN/` staging tree, run N parallel staging trees: `.swarm/pending/shard-A/leaf-NN/`, `.swarm/pending/shard-B/leaf-NN/`, and so on — one per concurrent wave.
- Each shard gets its own wave number, its own `post-review-log.md` entries (still one shared log file is fine since admission is still one-at-a-time per shard; the append-only format already tolerates interleaved waves), and its own `.swarm/wave-<wave>.snapshot.json` / `.SWEEP.md` / `.AUDIT.md`.
- **No file overlap across shards, ever** — this is the same non-overlap invariant Phase 3 already enforces within one wave's briefs, just extended to hold across every shard running at the same time. Two shards racing to write the same file is exactly the collision this whole pattern exists to prevent; if the dependency map from Phase 2.1 can't guarantee that separation up front, don't shard — run sequential waves instead.
- Each shard still obeys the normal refuse->16 leaf-count cap on its own. Sharding is how you go past that ceiling *in aggregate* without raising it for any single wave — mirrors 4 isolated groups of 16 rather than one ungoverned pool of 64.

This is additive, not a replacement for the default path. Most specs fit in one wave and don't need this section at all — reach for shards only when the dependency map already shows multiple large, file-disjoint groups of slices, and running them sequentially would just be waiting with no coordination benefit.
