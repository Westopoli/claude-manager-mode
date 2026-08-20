---
name: manager-mode-lite
description: Sonnet-4.6-only parallel-agent TDD cascade. Identical to manager-mode in every phase and gate, but enforces claude-sonnet-4-6 at every level — overlord, shard-test-writer, test-quality auditors, test-fixers, and leaf implementers all run on Sonnet 4.6. Use when cost or quota constraints require a single-model run, or when you want faster wall-clock time at the expense of the judgment-tier gap. Trigger phrases: same as manager-mode ("swarm this", "decompose and spawn", "run the cascade", "spawn N agents on this", "build feature X with parallel agents") plus "lite mode", "sonnet cascade", "cheap cascade".
---

# /manager-mode-lite — single-command parallel-agent cascade (Sonnet 4.6 everywhere)

One slash command. The overlord (this chat) drives every phase. Sub-agents only write impl against pre-written failing tests.

The cascade prevents three structural failures in parallel-agent TDD: (1) leaves stepping on each other's files, (2) leaves silently making design decisions, (3) leaves receiving slices too big to finish coherently. Phases 0–7 are the procedure for keeping those guarantees.

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

## Model defaults

**All roles run on Sonnet 4.6 (`model: "claude-sonnet-4-6"`), no exceptions.** This is the defining constraint of manager-mode-lite — the only difference from manager-mode. Every spawn call below that names a model passes `model: "claude-sonnet-4-6"` regardless of the role's judgment demand.

- **Overlord (this chat)** — Sonnet 4.6. No model-switch prompt; proceed directly into Phase 0.
- **Shard-test-writer** — Sonnet 4.6. Pass `model: "claude-sonnet-4-6"` on the spawn call.
- **Leaf implementers** — Sonnet 4.6. Pass `model: "claude-sonnet-4-6"` explicitly on every Phase 4 delegation call.
- **Test-fixer** — Sonnet 4.6. Pass `model: "claude-sonnet-4-6"`.
- **Test-quality auditors** — Sonnet 4.6. Pass `model: "claude-sonnet-4-6"` on every 3.4.2 spawn call.

Dependency-map/consolidation drafting sub-agents (Delegated drafting passes) also pass `model: "claude-sonnet-4-6"` explicitly.

---

## Phases at a glance

```
Phase 0    Preflight            — find/bootstrap .claude-swarm.toml; list which of {spec, contract, umbrella} exist
Phase 1    Lite-discovery       — fire only for missing inputs; one-question drafts, Bible Compliance footer on spec
Phase 1.5  Plan-consistency     — overlord checks the locked spec/contract/umbrella against each other; BLOCKING
Phase 2    Decompose            — dependency map + consolidation pass + emit briefs + shard-test-writer authors per-leaf failing tests (Spec Link Rule + composition assertion + boundary/scale sweep + task-size guardrail)
Phase 3    Audit briefs         — run check_invariants.py (incl. contradiction check) + codebase-preconditions + external test-quality audit (goal-fidelity + umbrella-alignment + composition + boundary/scale); fix & re-run on FAIL
Phase 4    Spawn leaves         — wave-baseline snapshot; one sandbox per leaf; N sub-agents in parallel through the client delegation adapter
Phase 5    Wait + sweep         — wait all green; harvest sandboxes into staging; aggregate assumption-sweep; write wave-N.SWEEP.md
Phase 6    Admission loop       — per leaf: G1–G10 + file-match + umbrella pre/post + admit-or-revert + log
Phase 7    Final report         — counts + follow-up direction
```

If all three inputs (spec, contract, umbrella RED) already exist on disk, Phase 1 is skipped entirely. That is the common path for a returning project. **Phase 1.5 still runs** — it is a check on the locked artifacts, not on the drafting of them, and skipping it for returning projects would exempt exactly the specs that have been edited the most times.

---

## Phase 0 — Preflight

**0.1 Locate config.** Walk up from cwd until a `.claude-swarm.toml` is found. If none: copy `$SWARM_SHARED_DIR/templates/.claude-swarm.toml.example` to `<project_root>/.claude-swarm.toml`, then ask the user to fill each required field — do not guess values, wrong values here propagate everywhere:

- `spec_dir` — directory for the spec file (often `specs/`).
- `briefs_dir` — leaf briefs go here. Default derives per-cascade: `.swarm/<cascade-slug>/briefs/`, where `<cascade-slug>` comes from the spec's `<name>` (0.2), normalized — see config.md's "Cascade-slug derivation" note. Set explicitly here to override (e.g. to force a flat shared dir across cascades).
- `type_contract_path` — contract file (often `src/<pkg>/types.py`).
- `umbrella_test_cmd` — command that runs the umbrella (e.g., `pytest tests/umbrella.py`).
- `parent_owned` — globs leaves cannot touch.
- `snapshot_ignore` — paths excluded from the Phase 4.0 baseline and skipped when building a leaf sandbox. Defaults cover `.git/`, `.swarm/`, `__pycache__/`, `node_modules/`, `.venv/`, and test-runner scratch (`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, coverage output).
- `sandbox_link` — dependency trees a sandbox symlinks rather than copies (Phase 4.1). Defaults cover `node_modules`, `.venv`, `venv`, `vendor`, `target`.

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

## Scale & Boundary Profile
- **N typical / N peak:** <e.g. 5k rows typical, 2M peak>
- **Growth claim per hot path:** <path> is `sublinear` | `linear-ish` | `quadratic-ok`
- **Memory posture:** streaming | bounded-buffer | full-load-ok
- **External call budget:** <e.g. one query per request, not per row>

## Bible Compliance
- **Bible path:** `<path>` (or "none — this project has no source-of-truth doc")
- **Sections referenced:** <section names / line refs the spec implements>
- **Deliberate divergences:** <list any spec line that intentionally diverges from the bible, with the reason. If none: "none.">
```

`unbounded-unknown — assert growth only, no absolutes` is a valid answer to the whole Scale & Boundary Profile, the same escape hatch Bible Compliance gives a project with no bible. What is not valid is leaving it out: the shard-test-writer needs a stated growth claim to write a scale assertion against, and without one it would have to invent a number — a design decision made by a sub-agent, which is exactly what 2.6's authorship split exists to prevent.

Render the draft to the user. They approve, edit, or restart. Bible Compliance is the one piece of heavyweight discovery rigor worth keeping — omitting it has a documented cost: a wave shipped four Python stages when the bible specified Postgres, costing an afternoon + 15 leaf agents to re-do. Skipping the footer is acceptable when the project genuinely has no bible; lying that there is none is the failure mode.

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

## Phase 1.5 — Plan-consistency pass

The overlord reads the locked spec, contract, and umbrella test **against each other** and reports what does not line up. Runs inline in this chat — no sub-agent. It is a reading pass over three files, not a research task, and the overlord is the only context holding the conversation that produced them.

**Always runs**, including the returning-project path where all three already existed at Phase 0 and Phase 1 never fired. That path is not the safe case: an artifact edited across many sessions has had more chances to acquire a contradiction than one drafted ten minutes ago.

### 1.5.1 The five checks

Answer each explicitly, in order. A check with no recorded answer counts as not run.

1. **AC ↔ AC.** Do two acceptance criteria require different values or different behavior for the same thing? Includes a criterion an amendment revised without revising the original it contradicts.
2. **AC ↔ contract.** Does every AC's behavior have a contract symbol to hang on, and does every symbol an AC names actually exist in the locked contract? An AC with nowhere to land produces either a fabricated symbol or a silent drop.
3. **AC ↔ umbrella.** Does the umbrella test assert anything an AC contradicts? The umbrella is the top-level behavioral claim; a spec that disagrees with it will be discovered by a leaf, at implementation time, as a test that cannot pass.
4. **Observability.** Does every AC state an outcome something could assert on? An AC with no observable outcome cannot produce anything but a tautological test — the shard-test-writer will write *something*, and that something will pass no matter what the impl does.
5. **Named-entity resolution.** Every entity an AC names — a path, an env var, a field, an endpoint, an external capability — is either defined in the spec/contract, or tagged `external-unverified` in the finding table.

### 1.5.2 What check 5 is and is not

Check 5 does **not** research feasibility. The overlord is not required to know whether a third-party product can do what an AC assumes, and pretending otherwise would turn a five-minute pass into an open-ended investigation.

What it refuses is *silence*. An AC that assumes an external capability must say so out loud, in front of the user, who usually does know. The worked example: an AC reading "a Dropbox app scoped to `/n8n/_print_queue/` only" is not internally contradictory and passes checks 1–4 clean. Under check 5 it surfaces as `external-unverified: Dropbox path-scoped app`, and the person reading it knows immediately that Dropbox offers App-folder or Full-Dropbox access and nothing in between. That AC reached five leaves and an entire wave of implementation before anyone noticed.

The pass does not have to be right about the world. It has to stop the spec from quietly assuming.

### 1.5.3 Output and gate

Write `.swarm/<cascade-slug>/PLAN-CHECK.md`:

```markdown
# Plan-consistency — <cascade-slug>

| # | check | finding | artifact + line | resolution |
|---|-------|---------|-----------------|------------|
| 1 | AC ↔ AC | AC-4 and AC-12 both set the retry ceiling, to 3 and to 5 | specs/x.md:41, :88 | open |
| 5 | named-entity | AC-35 assumes a path-scoped Dropbox app | specs/x.md:210 | external-unverified |

## Checks with no finding
- AC ↔ contract: no gap.
- AC ↔ umbrella: no gap.
- Observability: no gap.
```

Record the clean checks too. A table listing only findings is indistinguishable from a pass that never ran — the same reason 2.2a requires logging its "no gap" answers.

**Blocking.** Any open finding stops Phase 2. Resolve it by amending the spec, contract, or umbrella — which returns to Phase 1's approval gate, since those artifacts are locked — or by the user recording an explicit waiver in the `resolution` column with a reason. `external-unverified` is a waiver the user grants, not one the overlord grants itself.

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
- **Hot paths** — paths the Scale & Boundary Profile gives a growth claim for. A leaf owning a hot path *and* a cross-cutting concern splits: scale bugs are cross-cutting by nature, so the two together is where an implementation satisfies each rule locally and degrades globally.

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

For each slice, write `<briefs_dir>/leaf-NN.md` following `$SWARM_SHARED_DIR/references/brief-template.md`. Set `test_owned_by: parent` in every brief frontmatter (the leaf does not author or modify these files — ownership sits on the parent side of the cascade; see 2.6 for who actually writes them). The field is **required** by `check_invariants.py`, with no default — a brief that omits it fails schema rather than quietly parsing as `leaf`.

Key brief rules:
- `spec_lines`: concrete `int-int` range.
- `contract_imports`: only symbols present in the locked contract.
- `do_not_edit`: every other same-wave brief's `impl_files` + parent-owned globs.
- Task prose: imperative, no ambiguous verbs (decide / choose / design / determine / figure out / resolve / pick).
- Task fenced code: total non-blank lines across all fenced blocks ≤ `max_brief_code_lines` (default 10). Stub signatures + mirror-pointer snippets only. **Do not embed ready-to-paste impl bodies — the leaf authors the body.** Use shape-carriers instead: `spec_lines` refs, `contract_imports`, mirror-pointers ("match the structure of `path/to/sibling.py`"), invariant statements. Embedding the body collapses parallelism — parent absorbs leaf work, leaf becomes a copy-paste courier. Audit blocks briefs that exceed the ceiling.
- `impl_line_budget`, `test_assertion_budget`: from `.claude-swarm.toml`; tighten if you can.
- `growth_claim`, `scale_assertions`: set on any leaf owning a hot path — copy the claim from the spec's Scale & Boundary Profile, and set `scale_assertions: true` so G10 checks the test actually measures growth.

The brief's `## Task` section must instruct the leaf:

> Test files at `<test_files paths>` are already written and failing. You are working inside your own sandbox at `.swarm/<cascade-slug>/sandbox/leaf-NN/`, which is your working directory. Your job: edit `<impl_files paths>` in place there until those tests pass — confirm RED first, then GREEN. Do not stage, copy, or move anything; the parent harvests your declared files. Do not modify the test files. Do not create any files outside `impl_files`.

### 2.6 Write per-leaf failing tests

**How many shard-test-writers.** One per shard, and a shard holds **5-6 leaves at most** — see "Shards" below for why that number and not the wave's own 16. A wave of 6 or fewer leaves is **one shard**, writing to `audits/wave-<wave>/default/`. Do not create a shard per leaf: shard count multiplies through every downstream per-shard phase — test-writer, test-auditor, `TEST-AUDIT-BRIEF.md`, the A3/A4 artifacts — so a 5-leaf wave split four ways buys four spawn-and-audit cycles for tests one writer could hold, and loses the cross-leaf contradictions only a shared context can see.

Per-leaf tests are **not** written by the overlord directly, with no exception for small or single-wave runs. Spawn one **shard-test-writer** sub-agent per shard, on Sonnet 4.6 (see "Model defaults" above — pass `model: "claude-sonnet-4-6"` on the spawn call), with the locked spec/contract and that shard's brief set only. It writes every `test_files` path in that shard, exercising only each leaf's contract symbols, and never touches impl. See `swarm-shared/references/playbook.md` "Roles" for the role's full boundary. This keeps test authorship independent of whichever agent later resolves an ambiguity in impl — the failure mode where a leaf writes a test that only certifies its own guess.

**Boundary + scale sweep** — give the shard-test-writer `$SWARM_SHARED_DIR/references/test-design.md` and require the boundary table it specifies at `.swarm/<cascade-slug>/audits/wave-<wave>/<shard-or-default>/BOUNDARIES.md` before its tests count as done. Acceptance criteria describe the happy middle, so tests written from them alone certify the happy middle; the sweep is what forces a second pass over the edges, and its cardinality axis is where a leaf's `growth_claim` turns into an actual assertion. Boundaries the spec pins become tests citing the spec line. Boundaries the spec is **silent** on go to the question ledger (`.swarm/<cascade-slug>/questions/`) — the overlord batches every shard's open boundaries into one block for the user rather than letting the test-writer guess, since a guessed boundary is the same silent design decision this phase's authorship split exists to prevent.

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
- **shard-sizing** — no `(wave, shard)` group holds more than `max_leaves_per_shard` (default 6) leaves. One shard is one shard-test-writer; see "Shards". An unsharded wave is one group, so a 7-leaf wave fails here until it is split.
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

Once a shard's tests exist (2.6) and pass the invariant audit (3.0–3.3), spawn one fresh-context auditor per shard on Sonnet 4.6 (`model: "claude-sonnet-4-6"` — see "Model defaults" above) — same `caveman:cavecrew-reviewer`/`general-purpose`-fallback pattern used elsewhere in this skill, scoped to tests only — to audit that shard's test output before any leaf ever sees it. This is where test quality is judged: the overlord never grades its own (or the shard-test-writer's) tests directly, and no agent-based review of the implementation runs after admission. G8 (`test_quality_gate.py`, Phase 6.5) remains the mechanical backstop against orphaned/unreachable impl and weak assertions — this step is upstream and agent-judgment-based, G8 is downstream and scripted; they check different things and neither replaces the other.

#### 3.4.1 Overlord compiles the test-audit context package

Before spawning, write `.swarm/<cascade-slug>/audits/wave-<wave>/<shard-or-default>/TEST-AUDIT-BRIEF.md` containing everything the auditor needs and nothing it must infer:

- **Umbrella test.** Full text of `umbrella_test_cmd`'s test file(s) — the auditor needs the top-level behavioral contract to judge whether a shard's tests are a coherent decomposition of it, not just traced to a spec line in isolation.
- **The shard's own stated goal.** The relevant spec Summary + Acceptance Criteria this shard's briefs cover, quoted, plus the shard's brief set (paths + `spec_lines` + `contract_imports` per brief).
- **The tests under audit.** Full text of every `test_files` path written in 2.6 for this shard.
- **The shard's `BOUNDARIES.md`** (2.6) and the spec's Scale & Boundary Profile. Without these the auditor can only judge the tests that exist, never the boundary that was swept and then quietly dropped.
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
   impl_files has 2+ entries. SEVERITY FLOOR: a field, value or format the
   spec names explicitly, with zero assertions anywhere in this shard, is
   at least 🟡. Never file it as a 🟢 note. "The spec pins this and nothing
   checks it" is a gap, not a confidence observation — a real cascade filed
   exactly that as green ("job_id's documented format is unchecked") and
   shipped the defect it described.
4. BOUNDARY & SCALE FIDELITY — read BOUNDARIES.md against the tests. Is
   every boundary it lists either tested or escalated as a question, with
   none quietly guessed? Where the brief sets scale_assertions, does the
   test compare two input sizes and assert a ratio, and could a memoizing
   or test-shaped implementation pass it anyway? Rules and gotchas:
   swarm-shared/references/test-design.md.

Every finding needs a quote from the test, the umbrella, or the spec —
"looks thin" is not a finding. Write your report to
.swarm/<cascade-slug>/audits/wave-<wave>/<shard-or-default>/TEST-AUDIT.md.
```

Dispatch one auditor per shard in parallel (shards already don't share footprint, per Phase 3's non-overlap check).

#### 3.4.3 On findings

Any 🔴/🟡 finding blocks that shard's leaves from Phase 4 spawn. Fixes are sized, and the size decides who makes them:

- **Trivial** — the auditor quoted a replacement for a specific line, the change adds no new assertion and creates no new test file. The overlord may apply it inline and record it in `TEST-AUDIT.md`'s follow-up section.
- **Everything else** — spawn a fresh **test-fixer** sub-agent on Sonnet 4.6 (`model: "claude-sonnet-4-6"`), give it the audit finding, the test under repair, and the spec/contract excerpts it needs. It revises the test and confirms RED again. Not the flagged auditor, and not the context that wrote the original test.

Then 3.4.2 re-runs. Never silently wave through an unresolved 🔴.

Two reasons the line sits there. First, authorship: a finding that needs a new assertion is a test-writing decision, and the overlord grading work it authored is the bias this whole phase exists to remove — a real cascade applied all eight of its audit findings inline, including authoring a new test, and the hatch is what let it. Second, cost: the overlord is the one context alive for the whole cascade, and spending it on hand-editing test bodies is the most expensive way possible to do mechanical work.

Note: in manager-mode, original test authoring uses Opus and fixing uses Sonnet — different tiers for different judgment demands. In manager-mode-lite both use Sonnet 4.6.

---

## Phase 4 — Spawn leaves

After Phase 3 reports `all PASS`: take the wave baseline (4.0), build one sandbox per leaf (4.1), then spawn one sub-agent per brief **in parallel**, every one on Sonnet 4.6 (`model: "claude-sonnet-4-6"` — see "Model defaults" above). Use the client delegation adapter: Claude Code issues its native `Task` delegation calls; Codex calls `spawn_agent`. Dispatch the whole wave together, not sequentially.

### 4.0 Wave-baseline snapshot

**Before any sandbox is built and before any leaf spawns**, compute SHA-256 of **every** file in the repo — no leaf-owned exclusion — and write `.swarm/<cascade-slug>/wave-<wave>.snapshot.json`:

```json
{
  "wave": <wave>,
  "created_at": "<ISO timestamp>",
  "leaf_owned_paths": ["src/cache.py", "tests/test_cache.py", ...],
  "hashes": {"<path>": "<sha256>", ...}
}
```

Skip only paths matching `snapshot_ignore` in `.claude-swarm.toml` (defaults: `.git/**`, `.swarm/**`, `__pycache__/**`, `node_modules/**`, `.venv/**`, `*.pyc`, plus test-runner scratch — `.pytest_cache/**`, `.mypy_cache/**`, `.ruff_cache/**`, `.coverage`, `htmlcov/**`, `*.egg-info/**`).

The scratch entries are not cosmetic. The leaf runs its own test command inside its sandbox, so a passing test leaves cache directories there that exist nowhere in the baseline — and G5 would read every one of them as a write outside the leaf's footprint. If a project's runner writes somewhere else, add it here; a G5 block on a cache file is a false positive that will otherwise stop the wave.

`leaf_owned_paths` is still recorded — G5 needs to know which differences are *expected* — but those paths are now hashed like everything else. Two things about the timing and the scope are load-bearing, and the previous design got both wrong: a snapshot taken after the leaves have run cannot detect what the leaves did, and a snapshot that excludes leaf-owned paths is blind to precisely the paths a footprint breach touches.

### 4.1 Build one sandbox per leaf

For each leaf, create `.swarm/<cascade-slug>/sandbox/leaf-NN/` as a copy of the project root:

- Skip `snapshot_ignore` paths.
- **Symlink**, do not copy, each entry in `sandbox_link` (default `node_modules`, `.venv`, `venv`, `vendor`, `target`). These are usually most of a repo by size and are never leaf-owned, so copying them per leaf is pure cost — but dropping them breaks the leaf's own test command, which is the entire point of the sandbox.
- The leaf's `test_files` are already written (2.6) and are copied in like everything else. The leaf may read them and must not modify them.

The sandbox is the leaf's working directory. Inside it the leaf edits its declared `impl_files` at their normal paths and observes a real RED→GREEN, because the test imports impl at its real path and inside the sandbox that path is the leaf's own file. Nothing it does is visible to a sibling or to the real project.

**Honest limit:** this costs one project copy per leaf. A repo too large to copy N times should run sequential waves rather than a wide parallel one — that is a real trade-off, not a footnote. `sandbox_link` is what keeps the copy small in the common case.

### 4.2 Per-leaf prompt shape

Each delegation call gets a self-contained prompt:

```
You are leaf-NN of a TDD cascade. Read your brief at <briefs_dir>/leaf-NN.md
in full before doing anything.

You are working inside your own sandbox at
.swarm/<cascade-slug>/sandbox/leaf-NN/ — a private copy of the project, and
your working directory. Nothing you do there is visible to a sibling leaf or
to the real project.

Your test file(s) are already written at <test_files paths> and are failing.
Your job: edit <impl_files paths> IN PLACE, at their normal paths inside the
sandbox, until those tests pass. Run the test command yourself: confirm RED
first, then GREEN.

Do NOT stage, copy, or move anything anywhere — the parent harvests your
declared files out of the sandbox after you finish. Do NOT modify test files.
Do NOT create files outside impl_files (creating a file that IS in impl_files
is normal — a declared impl file often does not exist yet). Do NOT edit any
file in do_not_edit.

Small implementation choices are yours to make and expected: internal
variable/helper names, where you draw a private helper function's
boundary within your own impl_files, ordinary control-flow shape (loop vs.
comprehension, early-return vs. nested-if), how you organize the file's
internal structure — none of that needs a question. This is deliberately
wider when your brief owns more internal surface (a single larger file
with several related functions) than when it owns a narrow slice — you own
more internal structure, so you make more of these calls, same as any
engineer owns the internals of a file they're the sole author of.

Escalate (write a question to .swarm/<cascade-slug>/questions/leaf-NN-Q<n>.md and proceed
under best-guess, recording it in leaf-NN.ASSUMPTIONS.md with
unanswered: true) only for decisions with weight beyond your own file:
anything that changes a public function signature or contract symbol,
anything another leaf's test or the umbrella test depends on, an
ambiguous business rule (a numeric threshold, an ordering, a precedence
rule not pinned by spec_lines or the contract), or anything that would
require touching do_not_edit. If unsure which side a call falls on, ask:
"would a sibling leaf or the umbrella test observe this from outside my
file?" — if yes, escalate; if no, it's yours to decide.

When your test(s) go green, report back: "leaf-NN green" plus a summary of
what you changed and the paths you changed it at.
```

### 4.3 Subagent type selection

This picks the *tool profile* (`subagent_type`), not the model — every impl leaf runs on Sonnet 4.6 regardless of which type below is chosen (see "Model defaults"). Default to **`general-purpose`** for every impl leaf. `cavecrew-builder`'s toolset is `Read, Edit, Write, Grep, Glob` only — **no `Bash`** — which means it cannot itself run the leaf's test command to confirm RED-then-GREEN; it can only manually trace test-vs-impl by reading, and every leaf that hits this gap has to explicitly flag "I could not execute the tests" rather than give the overlord a real pass/fail signal. That undermines the brief's own Acceptance step ("Confirm RED... Confirm GREEN"), which assumes the leaf itself runs the command. Pick by capability fit, not by habit:

- **`general-purpose`** — default choice for a normal impl leaf. Has `Bash`, so it can actually execute `test_file`'s test command before and after implementing, and report a real (not traced) RED→GREEN result. No hard file-count refusal, so brief sizing is governed by `impl_line_budget`/`test_assertion_budget` and the brief's own no-design-decision discipline, not by an incidental tool-selection ceiling.
- **`caveman:cavecrew-builder`** — optional, narrower-blast-radius alternative for a leaf that is genuinely trivial (single small file, no need for the leaf itself to execute anything — e.g. the overlord or a downstream step will run tests) and where the caveman-compressed report is worth more than execution capability. Needs only `Read, Edit, Write, Grep, Glob` and ≤ 2 impl files (it hard-refuses at 3+). Do not reach for it by default; use it deliberately when its trade-off actually fits the leaf.
- **`caveman:cavecrew-investigator`** — not used for impl leaves (it's read-only), but reach for it inline during Phase 2/3 if you need a quick file-locator pass without burning overlord context.

This is a hint, not a hard rule. The brief's footprint discipline is the actual safety net; the choice of sub-agent type is performance optimization. If a `cavecrew-builder` leaf hard-refuses mid-spawn, or reports it could not execute its own tests, re-spawn that one leaf as `general-purpose` — don't downgrade the whole wave.

### 4.4 Wait for all leaves to report

Do not advance to Phase 5 until every spawned leaf has reported green. Green now genuinely means green-in-isolation: each leaf measured it inside its own sandbox, where no sibling's edits exist. A leaf that reports red after multiple attempts → escalate to user (the leaf may need a re-spawn with corrected brief, or the brief itself was wrong).

---

## Phase 5 — Wait + aggregate sweep

All leaves reported green. Before any admission:

### 5.1 Harvest sandboxes into staging

The wave-baseline snapshot was taken in Phase 4.0, before any leaf ran. This step collects what the leaves produced.

For each leaf, copy every path in its brief's `test_files + impl_files` out of `.swarm/<cascade-slug>/sandbox/leaf-NN/` into `.swarm/<cascade-slug>/pending/leaf-NN/`, mirroring the layout from the project root (`src/cache.py` → `.swarm/<cascade-slug>/pending/leaf-NN/src/cache.py`). For a sharded wave, staging is `.swarm/<cascade-slug>/pending/<shard>/leaf-NN/`.

The overlord does this, not the leaf. That is what makes Phase 6.3's file-match rule satisfiable: staging contains exactly `declared` by construction, including the `test_owned_by: parent` test files the leaf may not touch — the leaf is never asked to place a file it is forbidden to modify.

Leave the sandbox in place until the leaf is admitted or reverted; G5 reads it.

### 5.2 Aggregate assumption-sweep

Read every `<briefs_dir>/leaf-NN.ASSUMPTIONS.md`. Categorize entries:

1. **Contradicts the spec.** Assumption picks a value the spec explicitly contradicts.
2. **Contradicts the bible.** Assumption picks a value the source-of-truth doc forbids.
3. **Cross-leaf contradiction.** Two leaves made incompatible assumptions about the same shared interface.
4. **Fabricated symbol or path.** References a type/function/file that does not exist in the contract or repo.
5. **Compounded inference.** A leaf assumption is justified by another assumption rather than by a spec line or contract symbol.

Write `.swarm/<cascade-slug>/wave-<wave>.SWEEP.md`:

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

- List `.swarm/<cascade-slug>/questions/leaf-NN-Q*.md`. For each, ensure either an answer at `.swarm/<cascade-slug>/answers/leaf-NN-Q<n>.md` exists OR the leaf's ASSUMPTIONS file tags it `unanswered: true`. If neither, the leaf made a silent decision — escalate to user for an answer before Phase 6.
- List `.swarm/<cascade-slug>/proposals/leaf-NN.md`. Resolve every `status: pending` proposal (parent applies + marks `accepted`, OR `rejected` / `superseded`). G4 in Phase 6 blocks on `pending`.

---

## Phase 6 — Admission loop

For every leaf with staged output at `.swarm/<cascade-slug>/pending/leaf-NN/`, in ascending NN order:

### 6.0 Bypass detection

Read `.swarm/post-review-log.md`. List all `leaf-NN.md` files in `briefs_dir` whose NN predates the current leaf. For each, require **both**:

1. a row in the log, and
2. a gate-evidence file at `.swarm/<cascade-slug>/audits/wave-<wave>/leaf-NN.GATES.md` (written by 6.5).

Either one missing is a bypass:

> ⚠ BYPASS: `leaf-NN` has a brief but no post-review-log entry / no GATES.md. The file-match rule, parent-owned check, and umbrella were never verified for it. Confirm whether to audit now or accept the risk before continuing.

Requiring both is the point. A log row records that a leaf was *admitted*; it is not evidence that anything was *checked*. A wave whose leaves were verified in bulk and then logged afterwards produces a complete, clean-looking log and no GATES files at all — which is exactly what a collapsed admission loop looks like from the outside.

Two further tells, both cheap to check and both non-obvious once the log looks tidy:

- **Identical timestamps** across every row in a wave. The loop is per-leaf and sequential; rows minted in one pass share a timestamp to the second.
- **A surviving `pending/leaf-NN/`** for a leaf logged `clean`. 6.9a deletes staging on admit, so its presence means admission did not run the path that would have removed it.

Do not silently continue past a detected bypass. If `post-review-log.md` exists but lacks the required header (see 6.7), warn — the audit trail may have been tampered with.

### 6.1 G7 wave-sweep check (first admission of wave only)

If this is the first admission for this wave: require `.swarm/<cascade-slug>/wave-<wave>.SWEEP.md` to exist and to have an mtime newer than every `leaf-NN.ASSUMPTIONS.md` for this wave. If missing → block. If older than any leaf ASSUMPTIONS → block (re-run Phase 5.2).

For subsequent admissions of the same wave, skip this gate (it passed at first admission).

### 6.2 Verify staging non-empty

`.swarm/<cascade-slug>/pending/leaf-NN/` must exist and contain ≥ 1 file. If empty: reject — the harvest (5.1) found nothing at the leaf's declared paths inside its sandbox, so the leaf reported green without producing the files it claimed. Re-spawn or escalate.

### 6.3 File-match rule

Read the brief. Take the union of `test_files` + `impl_files`; call it `declared`. The staging directory must contain exactly `declared` — same count, same paths (relative to project root). No extras, no missing, no renames.

- Count mismatch → reject.
- Path mismatch → reject.

When `test_owned_by: parent` (default in this skill — tests are written on the parent side per 2.6, not by the leaf), the test files in `declared` are still in scope for file-match (the leaf may not modify them, but they live at the same paths the brief declares).

### 6.4 G1 parent-owned check

For every staged file path, check it does NOT match any glob in `parent_owned`. Any match → reject. A leaf that needed to touch parent territory made a design decision the cascade forbids; the right fix is a contract proposal (Phase 5.3), not a direct edit.

### 6.5 Gate sweep — one command

```bash
python "$SWARM_SHARED_DIR/scripts/run_gates.py" --leaf leaf-NN --cascade <cascade-slug>
```

That runs every gate below, plus the artifact preconditions each one depends on, and writes the evidence file 6.5a describes. Exit 0 = clear to admit, 1 = blocking findings, 2 = paths could not be resolved. `--strict` (hardcore) blocks on the advisory gates and on a missing `BOUNDARIES.md`.

**Why a runner rather than a checklist.** These gates were prose for a long time, and prose has no failure mode: an overlord that ran all of them and one that ran none produced the same clean report and the same log row. A survey of 64 brief-carrying cascades found `BOUNDARIES.md` present 0 times, `TEST-AUDIT.md` 6 times, the wave snapshot 12 times, and 13 of 15 `post-review-log.md` files holding a header and no rows at all. None of that was visible from inside a run.

The runner also treats a **missing input as a failure rather than a silence** — G5 with no snapshot and G7 with no sweep used to read as "nothing to report" instead of "this gate could not run".

It deliberately does **not** admit anything: no backup, no copy to destinations, no umbrella run, no log row. Those mutate the project and stay with the overlord under the user's eye (6.6–6.9). The runner is the read-only verification that runs first, and the one file it writes is its own report.

Read its output verbatim to the user, the same as Phase 3's. What it checks:


- **A1–A4 artifact preconditions** — the wave-baseline snapshot (4.0), the assumption-sweep and its mtime against every ASSUMPTIONS (5.2/G7), the shard's `TEST-AUDIT.md` (3.4), and its `BOUNDARIES.md` (2.6). The first three block; `BOUNDARIES.md` is advisory unless `--strict`. Each of these is an input another gate reads, so a missing one is a gate that cannot run — reported as a failure rather than passed over.
- **6.3 file-match and 6.0 bypass detection** run here too, as part of the same pass.
- **G2 ASSUMPTIONS file** — note presence/absence. Do not block on absence (means brief was concrete). Do block if brief's prose implies inference happened but no log exists.
- **G3 open-question** — every published question must have a matching answer OR an ASSUMPTIONS entry tagged `unanswered: true`. If a parent answer disagrees with the leaf's recorded inference → block (the leaf wrote against the wrong assumption).
- **G4 contract-proposal** — `.swarm/<cascade-slug>/proposals/leaf-NN.md` must not be `status: pending`. If `accepted`, verify the target parent-owned file actually contains the change (grep for an identifying line).
- **G5 footprint integrity** — using `.swarm/<cascade-slug>/wave-<wave>.snapshot.json` (Phase 4.0), recompute SHA-256 for every file in this leaf's sandbox. Every file whose hash differs from the baseline, or that the baseline does not contain at all, must appear in this leaf's `declared` set. Any other difference → block: the leaf wrote outside its footprint. Also recompute the real project tree against the same baseline; a difference there, before 6.7 copies anything, means something wrote to the live tree during the wave.

  The old form of this gate compared only paths *outside* the leaf's footprint, against a snapshot taken *after* every leaf had already finished. It could not detect a footprint breach on either axis, and reported clean through one.
- **G6 escalation-trigger** — for every `escalation_triggers:` entry with a `detect:` command in this brief, run the command with `$STAGING_DIR=.swarm/<cascade-slug>/pending/leaf-NN/`. If a trigger fires and no `.swarm/<cascade-slug>/escalations/leaf-NN.md` exists → block.
- **G8 test-quality gate** (leaves with 2+ `impl_files` only) — `test_quality_gate.py`, run for you by the runner. Reachability findings (a function nothing in the leaf's own impl calls — an orphaned/unwired implementation) block. Mutation findings (a function whose tests still pass after one mechanical mutation) print as advisory, not blocking by default — a single mutant can miss by bad luck rather than prove the test is weak; pass `--strict` (hardcore does) to block on those too.
- **G9 complexity gate** (all leaves) — `complexity_gate.py`, run for you by the runner. Flags any function over `--max-cyclomatic` (default 10) decision points or `--max-nesting` (default 3) block levels. Advisory by default — a high score is not proof of a defect the way G8's reachability is — pass `--strict` (hardcore does) to block on findings. Calibration, measured across 72 functions / 1,583 LOC of real cascade output (`experiments/scaling-test/phaseH-ceiling-search/` rungs H1–H3): cyclomatic peaked at exactly 10 and never exceeded it, so 10 sits on the natural ceiling; nesting never reached 3, so that half of the gate is untested rather than calibrated.
- **G10 scale gate** (all leaves) — `scale_gate.py`, run for you by the runner. Covers what G9 structurally cannot: G9 scores *cyclomatic* complexity, so `if item in big_list` inside a loop scores 3 and passes clean while running quadratically. Half A flags loop-nested shapes that turn a linear pass quadratic (self-join, membership scan, string concat, re-sort, N+1 IO); Half B, on leaves whose brief sets `scale_assertions: true`, confirms the test compares two input sizes rather than measuring one. Advisory by default, `--strict` (hardcore) blocks — a flagged shape is strong evidence, not proof.

### 6.5a Gate evidence

`run_gates.py` writes `.swarm/<cascade-slug>/audits/wave-<wave>/leaf-NN.GATES.md` itself, as each check returns:

```markdown
# leaf-NN gate evidence — wave <wave>

| gate | result | evidence | timestamp |
|------|--------|----------|-----------|
| file-match (6.3) | PASS | 3 declared, 3 staged, paths identical | <ISO> |
| G1 parent-owned  | PASS | no staged path matches parent_owned | <ISO> |
| G5 footprint     | PASS | 3 files differ from baseline, all declared | <ISO> |
| G8 test-quality  | ADVISORY | 1 mutation finding, non-blocking | <ISO> |
| ...              |      |          |           |
```

One file per leaf. This is what 6.0 checks for on the *next* leaf, and it is the only artifact that distinguishes a loop that ran from a log filled in afterwards. Because the runner writes it, a gate that did not execute has no row — the evidence cannot drift from what actually happened, which is exactly what an overlord writing it from memory could not guarantee.

Do not hand-write this file. If you find yourself composing one, the runner did not run.

### 6.6 Umbrella pre-admission

Run `umbrella_test_cmd`. Capture per-test named results — for pytest, add `-v --tb=no -q` if not already present. Record `pre_passing_tests` (set of named passes) and `pre_count`.

If the runner emits count-only output, note: per-test regression detection will be count-only (weaker gate).

### 6.7 Copy + post-admission umbrella

For every path in the brief's `test_files + impl_files`: if a file exists at that destination, snapshot it to `.swarm/<cascade-slug>/backups/leaf-NN/<path>` (mirroring the dest layout). If no file exists yet (new file), record the absence — revert will delete instead of restore.

Copy every staged file from `.swarm/<cascade-slug>/pending/leaf-NN/` to its destination path. All declared files copied; no partial admissions.

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
- Delete `.swarm/<cascade-slug>/pending/leaf-NN/` and `.swarm/<cascade-slug>/sandbox/leaf-NN/`.
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

Use the real time at which this leaf was admitted. Rows sharing one timestamp across a whole wave are a bypass signal (6.0), because the loop that produces them is sequential.

The log is append-only. Never edit, reorder, or delete entries.

- If `graphify_cmd` is set, run it and inspect for unexpected couplings (new import edge between leaf-owned modules that wasn't in the design). Flag for user; do not block.

### 6.9b Revert

- For every backup under `.swarm/<cascade-slug>/backups/leaf-NN/`: overwrite the destination with backup contents.
- For every declared file that had no backup (new file): delete from destination.
- Delete `.swarm/<cascade-slug>/pending/leaf-NN/`. Keep `.swarm/<cascade-slug>/sandbox/leaf-NN/` — a reverted leaf's sandbox is the forensic record of what it actually did.
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

**Apex owns absolute numbers; per-leaf tests own ratios only.** Apex is the one place a wall-clock or throughput budget means anything, because it runs alone after the wave. Leaf tests run while up to 16 siblings compete for the same CPU, so a duration threshold there flakes both ways — false RED stalling a wave, false GREEN admitting a quadratic. That is why 2.6's scale assertions are growth ratios: it is the only scale signal parallel spawn leaves intact.

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
- **Use git.** All state lives in `.swarm/<cascade-slug>/`. Per-leaf sandboxes replace branches; the staging dir carries the harvested result; the backup dir replaces revert; post-review-log replaces git log; per-test set-diff replaces commit metadata for regression attribution. The cascade's guarantees are equivalent; the one thing lost is cryptographic commit signing (acceptable in single-project trust models).
- **Auto-spawn leaves before Phase 3 passes.** Phase 4 only fires after Phase 3 reports `all PASS`. Pre-audit spawn re-introduces every failure mode the audit prevents.
- **Make architecture decisions silently.** Phase 1 surfaces Bible Compliance + each draft as an explicit approval gate. Phase 1.5 surfaces contradictions between the locked artifacts, and any external capability the spec assumes. Phase 2 surfaces fat-file collisions + leaf-count guardrails. Phase 3 surfaces invariant violations. Phase 5 surfaces aggregated assumption drift. Phase 6 surfaces per-leaf gate failures. Silence at any of these is the failure mode; explicit user choice is the success path.

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
| Question ledger | Leaf publishes `.swarm/<cascade-slug>/questions/leaf-NN-Q<n>.md`; parent answers in `.swarm/<cascade-slug>/answers/`. Leaf proceeds under best-guess, tags ASSUMPTIONS `unanswered: true`. | G3 (Phase 6.5) |
| Contract proposals | Leaf publishes `.swarm/<cascade-slug>/proposals/leaf-NN.md` instead of editing parent-owned files. Parent applies + marks accepted. | G4 (Phase 6.5) |

Full theory at `$SWARM_SHARED_DIR/references/playbook.md`.

---

## Task-size discipline

Phase 2.3 refuses past 16 leaves — drift between siblings, context fill, missed cross-leaf contradictions. That cap bounds a **wave**; the separate 5-6 cap in "Shards" below bounds a **shard**, and the two are not the same number for the reasons set out there. Phase 2.2's consolidation pass is what should keep most waves well under this; a wave still near 16 after honest consolidation judgment likely needs re-scoping, not a bigger cap.

Past 16 even after consolidation: split into sequential waves (`wave:` field sequences cross-wave file edits).

The refusal at >16 is non-negotiable in this skill. If the user wants to push past it, that decision belongs upstream — re-scope the spec, not the gate.

## Shards

A **shard** is a partition of one wave: an isolated staging tree plus its own shard-test-writer, its own test-auditor, and its own audit dir. It is *not* a separate wave — shards inside a wave share the wave number, the wave snapshot, and the sweep. Every gate script already resolves a shard from the brief's `shard:` field independently of `wave:`, so nothing needs a distinct wave number per shard.

### Sizing — 5-6 leaves per shard

Two limits are in play and they are **not** the same number:

- The **16-leaf cap** (Phase 2.3) bounds one wave. It is sized for staging isolation and for the overlord's brief-writing load — roughly 120 lines of brief per leaf.
- The **5-6 leaf shard cap** bounds one shard-test-writer. That agent holds the shard's entire brief set *and* every impl file its tests target, then emits working test code plus one boundary table covering all of them.

Measured on a real cascade: ~376 lines of test code, ~17 assertions and ~28 `BOUNDARIES.md` rows per leaf, against target impl files ranging from 10 to 3,975 lines. At 16 leaves that is ~6,000 lines of test code, ~320 assertions and a ~450-row boundary table, emitted from one context that has already read ~19,000 lines in. The three failure modes the 16 cap cites — drift between siblings, context fill, missed cross-leaf contradictions — bite the writer *harder* than they bite a leaf: each leaf holds only its own brief, while the writer holds every one of them and has to produce working code against each.

So: **`shards = ceil(leaves / 6)`**. A wave of 6 or fewer is one shard and writes to `default/`.

Two overrides sit on top of the arithmetic:

- **Volume.** A leaf whose target impl exceeds ~2,000 lines counts as more than one against the shard budget. A single 4,000-line target can earn its own shard even in a small wave — reading it is most of that writer's context.
- **Co-location.** Leaves whose ACs cite each other's symbols, units, or constants go in the **same** shard. This is the inverse of Phase 3's non-overlap rule: non-overlap keeps *files* apart, co-location keeps *semantics* together, because a contradiction between two ACs is only findable inside one context. In the cascade the numbers above come from, a counter specified in three incompatible units was caught by the one shard that happened to hold two leaves, and by nothing else in the run.

**No file overlap across shards, ever** — the same non-overlap invariant Phase 3 enforces within a wave, extended to every shard running at the same time. Two shards racing to write one file is the collision this whole partition exists to prevent. If the Phase 2.1 dependency map can't guarantee that separation, don't shard the wave — sequence it instead.

### Going past one wave

The 16 cap bounds one wave's leaf count, not the cascade's total parallelism. A large, genuinely-decomposable spec (dozens of independent slices, no shared-file dependencies between groups of them) can run several waves **concurrently**, each in its own isolated staging tree — the way a real multi-agent rewrite (64 concurrent Claude instances porting a 500K-line codebase, organized as 4 isolated worktrees of 16 agents each rather than one flat pool of 64) actually scaled. The ceiling there wasn't the agents' reasoning quality, it was **write-collision on shared state** — agents running conflicting git commands against the same checkout. The fix was architectural isolation, not a bigger flat pool.

Manager-mode's equivalent shared state is `.swarm/<cascade-slug>/pending/`, `post-review-log.md`, and the wave snapshot/sweep files. Concurrent waves each take their own wave number and their own `.swarm/<cascade-slug>/wave-<N>.snapshot.json` / `.SWEEP.md` / `.AUDIT.md`; `post-review-log.md` stays a single append-only file, disambiguated by its `wave` and `shard` columns, since admission is still one leaf at a time. Each concurrent wave obeys the 16 cap on its own, and is itself partitioned into shards by the 5-6 rule above — so a 4-wave run is up to 64 leaves in ~12 shards, mirroring 4 isolated groups rather than one ungoverned pool.

Most specs fit in one wave and never need this subsection. Reach for concurrent waves only when the dependency map already shows multiple large, file-disjoint groups of slices and running them sequentially would just be waiting with no coordination benefit.
