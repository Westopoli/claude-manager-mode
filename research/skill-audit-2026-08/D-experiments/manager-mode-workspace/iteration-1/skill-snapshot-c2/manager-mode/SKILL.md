---
name: manager-mode
description: Single-command parallel-agent TDD cascade. Use when the user wants to build a feature with parallel sub-agents — phrases like "swarm this", "decompose and spawn", "run the cascade", "spawn N agents on this", "build feature X with parallel agents", "set up the wave", "let's parallelize this". Walks through all phases internally (preflight → lite-discovery → plan-consistency → decompose → audit → spawn → wait + sweep → admission loop → final report) — no sibling slash commands to chain. Overlord chat writes spec/contract/umbrella (lite drafts if missing); a separate shard-test-writer writes per-leaf failing tests; leaves only write impl — no agent ever grades its own tests. A blocking plan-consistency pass checks the locked spec/contract/umbrella against each other before decomposition. Leaves build in per-leaf git worktrees, so a leaf's green cannot be produced by a sibling's edits. A fresh test-auditor per shard reviews goal-fidelity and umbrella-alignment before any leaf spawns — no post-admission adversarial pass exists. Decomposition consolidates file-disjoint slices into one leaf when they're one coherent responsibility, scored by a spec-text rubric (rule-clusters, exception branches, integrations, cross-cutting concerns), not a leaf-per-file default. Git-worktree isolation — leaves never run git; one script (`worktree_ops.py`) does, and the user's branch is written only by a confirmed base commit and a confirmed final fast-forward. Hard-refuses when decomposition exceeds 16 leaves. Always invoke this when the user wants parallel sub-agent work — not separate commands for spawn / review / post-review (they no longer exist).
---

# /manager-mode — single-command parallel-agent cascade

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

Three roles, three model tiers — pick by what kind of work the role does, not by habit:

- **Overlord (this chat)** — Opus 5. Decomposition (2.2/2.2a), spec/contract/umbrella drafting, and admission judgment calls are synthesis-shaped work where the stronger model earns its cost; this is the one context running for the whole cascade's duration. If the current chat is not already on Opus 5, tell the user before Phase 0 proceeds and let them switch (`/model opus`) — the skill does not switch its own host chat's model.
- **Shard-test-writer** — Opus 5. Writing a correct, non-tautological test from spec+contract text alone (2.6) is the same judgment-quality bar as decomposition: a weak test here is invisible until a leaf has already implemented against it. Pass `model: "opus"` on the spawn call.
- **Leaf implementers** — Sonnet 4.6, always, regardless of which `subagent_type` (Phase 4.2) is picked for a leaf. Implementing against an already-locked, already-audited failing test is bounded, mechanical work by design — that boundedness is the whole point of the brief template (see brief-template.md "Why this template"). Pass `model: "claude-sonnet-4-6"` explicitly on every Phase 4 delegation call; do not let it inherit whatever the overlord happens to be running on.

- **Test-fixer** — Sonnet 4.6. Repairing a test against an already-adjudicated audit finding (3.4.3) is bounded work with the answer attached, unlike authoring one from spec text. Pass `model: "claude-sonnet-4-6"`.
- **Test-quality auditors** — Opus 5. Judging goal-fidelity and umbrella-alignment against a locked spec is the same judgment-quality bar as decomposition. Pass `model: "opus"` on every 3.4.2 spawn call.

- **Sweep-runner (5.2) and admission-runner (Phase 6)** — Sonnet 4.6, `model: "claude-sonnet-4-6"`. Both execute already-scripted checks and return the scripts' own summary lines; they exist as context boundaries so the files and gate tables they touch never enter the overlord's prefix. Every judgment call (same-count confirm, revert, flagged-assumption triage) still comes back to the overlord.

Dependency-map/consolidation/ambiguity-resolution drafting sub-agents (Delegated drafting passes) run on Sonnet 4.6, `model: "claude-sonnet-4-6"`, explicitly on every spawn call — bounded drafting labor the overlord independently verifies (see "Delegated drafting passes" below), not judgment work that needs the heavier tier. Do not let this inherit whatever the overlord happens to be running on.

---

## Phases at a glance

```
Phase 0    Preflight            — find/bootstrap .claude-swarm.toml; list which of {spec, contract, umbrella} exist
Phase 1    Lite-discovery       — fire only for missing inputs; one-question drafts, Bible Compliance footer on spec
Phase 1.5  Plan-consistency     — overlord checks the locked spec/contract/umbrella against each other; BLOCKING
Phase 2    Decompose            — dependency map + consolidation pass + emit briefs + shard-test-writer authors per-leaf failing tests (Spec Link Rule + composition assertion + boundary/scale sweep + task-size guardrail)
Phase 3    Audit briefs         — run check_invariants.py (incl. contradiction check) + codebase-preconditions + external test-quality audit (goal-fidelity + umbrella-alignment + composition + boundary/scale); fix & re-run on FAIL
Phase 4    Spawn leaves         — wave base commit; one git worktree per leaf; N sub-agents in parallel through the client delegation adapter
Phase 5    Wait + sweep         — wait all green; commit each leaf worktree onto its branch (one loop); sweep-runner sub-agent writes wave-N.SWEEP.md
Phase 6    Admission loop       — per leaf, one admission-runner sub-agent: G1–G10 + file-match + umbrella pre/post + admit-or-revert (overlord decides same-count/revert) + log
Phase 7    Final report         — counts + follow-up direction
```

If all three inputs (spec, contract, umbrella RED) already exist on disk, Phase 1 is skipped entirely. That is the common path for a returning project. **Phase 1.5 still runs** — it is a check on the locked artifacts, not on the drafting of them, and skipping it for returning projects would exempt exactly the specs that have been edited the most times.

---

## Phase 0 — Preflight

**0.0 Git preflight.** Leaves build in git worktrees, so the project must be a git repository with a clean, attached checkout. Run:

```bash
python "$SWARM_SHARED_DIR/scripts/worktree_ops.py" preflight --slug <cascade-slug>
```

It refuses on: not a git repo (manager-mode requires git — there is no file-based fallback), detached HEAD, tracked changes (commit or stash first — the skill never stashes for the user), or leftover `swarm/<cascade-slug>/*` branches or worktrees from an earlier run (inspect, then `cleanup --slug <cascade-slug> --purge --yes`). It warns about untracked files, which will not exist inside any worktree — add the ones a leaf needs to `worktree_copy`. Every git command the cascade runs goes through this one script; the target project needs a single permission entry for it (`Bash(python3 *worktree_ops.py*)`) rather than one per git verb.

**0.1 Locate config.** Walk up from cwd until a `.claude-swarm.toml` is found. If none: copy `$SWARM_SHARED_DIR/templates/.claude-swarm.toml.example` to `<project_root>/.claude-swarm.toml`, then ask the user to fill each required field — do not guess values, wrong values here propagate everywhere:

- `spec_dir` — directory for the spec file (often `specs/`).
- `briefs_dir` — leaf briefs go here. Default derives per-cascade: `.swarm/<cascade-slug>/briefs/`, where `<cascade-slug>` comes from the spec's `<name>` (0.2), normalized — see config.md's "Cascade-slug derivation" note. Set explicitly here to override (e.g. to force a flat shared dir across cascades).
- `type_contract_path` — contract file (often `src/<pkg>/types.py`).
- `umbrella_test_cmd` — command that runs the umbrella (e.g., `pytest tests/umbrella.py`).
- `parent_owned` — globs leaves cannot touch.
- `footprint_ignore` — paths G5 and the Phase 5.1 commit step disregard inside a worktree (test-runner scratch a green run leaves behind). Defaults cover `.git/`, `.swarm/`, `__pycache__/`, `node_modules/`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, coverage output. (Old name `snapshot_ignore` still accepted.)
- `worktree_link` — untracked dependency trees symlinked from the main checkout into every worktree (Phase 4.1), so the leaf's own test command runs. Defaults cover `node_modules`, `.venv`, `venv`, `vendor`, `target`. (Old name `sandbox_link` still accepted.)
- `worktree_copy` — untracked files a leaf needs that must be *copied*, not linked (e.g. `.env.test`). Default empty.

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

> Test files at `<test_files paths>` are already written and failing. You are working inside your own git worktree at `.swarm/<cascade-slug>/worktrees/leaf-NN/`, which is your working directory — a checkout the parent manages. Never run git. Your job: edit `<impl_files paths>` in place there until those tests pass — confirm RED first, then GREEN. Do not stage, copy, or move anything; the parent commits your declared files. Do not modify the test files. Do not create any files outside `impl_files`.

### 2.6 Write per-leaf failing tests

**How many shard-test-writers.** One per shard, and a shard holds **5-6 leaves at most** — see "Shards" below for why that number and not the wave's own 16. A wave of 6 or fewer leaves is **one shard**, writing to `audits/wave-<wave>/default/`. Do not create a shard per leaf: shard count multiplies through every downstream per-shard phase — test-writer, test-auditor, `TEST-AUDIT-BRIEF.md`, the A3/A4 artifacts — so a 5-leaf wave split four ways buys four spawn-and-audit cycles for tests one writer could hold, and loses the cross-leaf contradictions only a shared context can see.

Per-leaf tests are **not** written by the overlord directly, with no exception for small or single-wave runs. Spawn one **shard-test-writer** sub-agent per shard, on Opus 5 (see "Model defaults" above — pass `model: "opus"` on the spawn call), with the locked spec/contract and that shard's brief set only. It writes every `test_files` path in that shard, exercising only each leaf's contract symbols, and never touches impl. See `swarm-shared/references/playbook.md` "Roles" for the role's full boundary. This keeps test authorship independent of whichever agent later resolves an ambiguity in impl — the failure mode where a leaf writes a test that only certifies its own guess.

**Writer prompt shape.** "With the locked spec/contract and that shard's brief set" means *in the prompt*, not as a list of paths to open. You are holding all three from Phase 1–2.5 already, so inlining them is free here and removes the writer's whole opening read-phase:

```
You are the shard-test-writer for shard <shard-or-default> of a TDD cascade.
Everything you need to write these tests is inlined below.

--- BEGIN SPEC EXCERPT (<spec_file>, ACs <the ACs this shard's briefs cite>) ---
<verbatim spec text for the union of this shard's briefs' spec_lines ranges,
plus the spec's Scale & Boundary Profile section>
--- END SPEC EXCERPT ---

--- BEGIN CONTRACT EXCERPT (<type_contract_path>) ---
<verbatim definition of each symbol named in this shard's briefs'
contract_imports — those symbols only, not the whole contract file>
--- END CONTRACT EXCERPT ---

--- BEGIN BRIEF SET ---
<verbatim body of every leaf-NN.md in this shard, frontmatter included>
--- END BRIEF SET ---

Write every test_files path the briefs above declare. Exercise only each
leaf's own contract symbols. Never touch impl.

Reading the impl files you are testing against: use `grep -n '<symbol>' <file>`
and then read the matching line range, not the whole file — you need the
signatures and call shapes your assertions target, not the bodies. Whole-file
reads are fine (and simpler) only when the file is under ~300 lines; check with
`wc -l` first. A file that does not exist yet is the normal case — the leaf
writes it — so do not go looking for it.

When done, return AT MOST 10 LINES: one line per test file written
(`<path> — <N> tests, RED confirmed`), the BOUNDARIES.md path with its row
count, and the count of open boundaries you sent to the question ledger.
Do not paste test code or restate the boundary table — both are on disk and
the auditor reads them from there.
```

The excerpts above are exactly what `build_audit_brief.py` (3.4.1) later compiles for the auditor, from the same fields — the writer and the auditor read the same scoped slice, one by prompt and one by file.

**Boundary + scale sweep** — give the shard-test-writer `$SWARM_SHARED_DIR/references/test-design.md` and require the boundary table it specifies at `.swarm/<cascade-slug>/audits/wave-<wave>/<shard-or-default>/BOUNDARIES.md` before its tests count as done. Acceptance criteria describe the happy middle, so tests written from them alone certify the happy middle; the sweep is what forces a second pass over the edges, and its cardinality axis is where a leaf's `growth_claim` turns into an actual assertion. Boundaries the spec pins become tests citing the spec line. Boundaries the spec is **silent** on go to the question ledger (`.swarm/<cascade-slug>/questions/`) — the overlord batches every shard's open boundaries into one block for the user rather than letting the test-writer guess, since a guessed boundary is the same silent design decision this phase's authorship split exists to prevent.

**No auto-pass (generated/matrix tests)** — if a leaf's tests are data-driven or parametrized from a generated set of cases (a probe's output, a fixture matrix, anything wider than hand-written cases), see test-design.md's "No auto-pass" section before writing them: every non-degenerate case needs a positively-defined, independently-computed expectation (never derived from the input under test itself), verdicts are a closed enum with no silent fall-through to PASS, and the grader itself gets validated against a stub-empty and a stub-all implementation before its output is trusted. Prefer a false-positive FAIL an investigation later clears over a false-negative auto-PASS nobody ever sees.

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

### 3.2 Render the summary, read the detail only on failure

Every script in `$SWARM_SHARED_DIR/scripts/` reports through its **exit code**, and ends its output with a one-line summary block (`check_invariants.py`: `--- N/M briefs PASS, K findings ---`). Use them in that order:

- **Exit 0** — surface the summary line and move on. Do not re-transcribe the script's output into your own message: it is already in the transcript once, and repeating it pays output tokens to put a second copy in your context for the rest of the cascade.
- **Non-zero** — now the detail matters. Render the failing rows verbatim, to yourself and to the user. Do not paraphrase them: the leaf_id + invariant + reason all matter for fixing the brief. Passing rows still do not need re-transcribing.

This is a rendering rule, not a checking rule. Nothing about what the script checks, or what counts as a FAIL, changes — only how much of a clean run you copy forward.

### 3.3 On FAIL

For each failing brief: read it, identify the offending line, fix the brief inline (or re-run Phase 2 if the failure is structural — wrong slicing, fat-file collision the dependency map missed). Then re-run the audit. Do not advance to Phase 4 with any FAIL outstanding.

If FAIL is on **non-overlap**, surface both resolution paths (sequential waves vs prep-step split) — these are seam-axis decisions, present them to the user.

### 3.4 Test-quality audit (external, before any leaf spawns)

Once a shard's tests exist (2.6) and pass the invariant audit (3.0–3.3), spawn one fresh-context auditor per shard on Opus 5 (`model: "opus"` — see "Model defaults" above) — same `caveman:cavecrew-reviewer`/`general-purpose`-fallback pattern used elsewhere in this skill, scoped to tests only — to audit that shard's test output before any leaf ever sees it. This is where test quality is judged: the overlord never grades its own (or the shard-test-writer's) tests directly, and no agent-based review of the implementation runs after admission. G8 (`test_quality_gate.py`, Phase 6.5) remains the mechanical backstop against orphaned/unreachable impl and weak assertions — this step is upstream and agent-judgment-based, G8 is downstream and scripted; they check different things and neither replaces the other.

#### 3.4.1 Overlord compiles the test-audit context package

Before spawning, build the package with the script — one command per shard:

```bash
python "$SWARM_SHARED_DIR/scripts/build_audit_brief.py" --cascade <cascade-slug> --wave <wave> [--shard shard-A]
```

It writes `.swarm/<cascade-slug>/audits/wave-<wave>/<shard-or-default>/TEST-AUDIT-BRIEF.md` holding everything the auditor needs and nothing it must infer, read straight off disk:

- **Umbrella test.** Full text of `umbrella_test_cmd`'s test file(s) — the auditor needs the top-level behavioral contract to judge whether a shard's tests are a coherent decomposition of it, not just traced to a spec line in isolation.
- **The shard's own stated goal.** The shard's brief set as a table (paths + `spec_lines` + `contract_imports` per brief), plus the spec excerpt below.
- **Spec excerpt.** Only the `spec_lines` ranges this shard's briefs actually cite, quoted verbatim — not the whole spec — plus the spec's `Scale & Boundary Profile` section whole, since 3.4.2 grades `BOUNDARIES.md` against it and it sits outside any one leaf's range.
- **The tests under audit.** Full text of every `test_files` path written in 2.6 for this shard.
- **The shard's `BOUNDARIES.md`** (2.6). Without it the auditor can only judge the tests that exist, never the boundary that was swept and then quietly dropped.
- **Composition-relevant contract excerpts.** Only the locked `type_contract_path` symbols the shard's `contract_imports` reference — not the whole contract file, to keep the package bounded.

Exit 0 = complete. **Exit 1 = the brief was written but a section has a gap** — a missing umbrella/test/`BOUNDARIES.md` file, a contract symbol a brief imports that is not in the contract, an unparseable `spec_lines`. Each gap prints on stderr; fix the underlying input and re-run rather than shipping the auditor a package with a hole in it. Exit 2 = config/cascade resolution error.

Then add **by hand**, into the two placeholder sections the script leaves at the bottom (this is the only part of the package that needs the overlord's own cross-shard knowledge — everything above is a file copy, and copying it through the overlord costs a read plus a write of the same bytes and then sits in its context for the rest of the cascade):

- **§7 Sibling-shard awareness, if relevant.** If a sibling shard's brief set shares a contract symbol or an adjacent AC, name the sibling shard and quote only the overlapping symbol/AC — not its full brief set. Lets the auditor catch a test that only makes sense assuming a cross-shard interface shape nothing else confirms. Write `none` when there is no sibling shard.
- **§8 Anything already litigated.** Wave-sweep dismissals or yellow-flags touching this shard's territory, so the auditor doesn't re-open a decision the user already made (it may still disagree if it looks wrong). Write `none` when there are none.

Compilation step, not a judgment step — don't pre-filter what looks fine, and do not read the generated brief back to yourself or to the user. Its whole point is that the auditor reads it and the overlord does not have to. The summary line the script prints (brief/test/symbol counts + gap count) is what you surface.

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

The report file is the deliverable. Return to the parent ONLY: the severity
counts (🔴 N / 🟡 N / 🟢 N), the report path, and for each 🔴/🟡 one line of
`<finding-id>: <test file> — <ten-word gist>`. Do not restate quotes,
evidence or remedies in the return message — the parent reads those from
the file, only for the findings it has to route.
```

Dispatch one auditor per shard in parallel (shards already don't share footprint, per Phase 3's non-overlap check).

#### 3.4.3 On findings

Any 🔴/🟡 finding blocks that shard's leaves from Phase 4 spawn. Fixes are sized, and the size decides who makes them:

- **Trivial** — the auditor quoted a replacement for a specific line, the change adds no new assertion and creates no new test file. The overlord may apply it inline and record it in `TEST-AUDIT.md`'s follow-up section.
- **Everything else** — spawn a fresh **test-fixer** sub-agent on Sonnet 4.6 (`model: "claude-sonnet-4-6"`), give it the audit finding, the test under repair, and the spec/contract excerpts it needs. It revises the test and confirms RED again, and returns at most 5 lines (finding id, file, RED confirmation, one-line description of the change) — the diff is on disk. Not the flagged auditor, and not the context that wrote the original test.

Then 3.4.2 re-runs. Never silently wave through an unresolved 🔴.

Two reasons the line sits there. First, authorship: a finding that needs a new assertion is a test-writing decision, and the overlord grading work it authored is the bias this whole phase exists to remove — a real cascade applied all eight of its audit findings inline, including authoring a new test, and the hatch is what let it. Second, cost: the overlord is the one context alive for the whole cascade, and spending it on hand-editing test bodies is the most expensive way possible to do mechanical work.

Note the deliberate asymmetry with 2.6, which puts original test *authoring* on Opus. Writing a test from spec text alone is a judgment call; repairing one against a specific, already-adjudicated finding is bounded work with the answer attached. Different jobs, different tiers.

---

## Phase 4 — Spawn leaves

After Phase 3 reports `all PASS`: take the wave base commit (4.0), create one worktree per leaf (4.1), then spawn one sub-agent per brief **in parallel**, every one on Sonnet 4.6 (`model: "claude-sonnet-4-6"` — see "Model defaults" above; override whatever the chosen `subagent_type` would otherwise default to). Use the client delegation adapter: Claude Code issues its native `Task` delegation calls; Codex calls `spawn_agent`. Dispatch the whole wave together, not sequentially.

### 4.0 Wave base commit

**Before any worktree is created and before any leaf spawns**, the artifacts Phases 1–3 wrote into the checkout (spec, contract, umbrella, briefs, shard tests, audits) must be committed — a worktree branches from a commit, not from a working tree. Run:

```bash
python "$SWARM_SHARED_DIR/scripts/worktree_ops.py" base --slug <cascade-slug> --wave <wave>
```

If the checkout has uncommitted changes it refuses and lists them. Show that list to the user and ask; on approval re-run with `--commit-artifacts --yes`, which commits exactly those paths on the user's branch as `swarm(<slug>): wave <N> base — …`. This is one of the two writes the cascade ever makes to the user's branch (the other is 7.4's fast-forward); it is reversible with `git reset --soft HEAD~1`.

`base` then records `.swarm/<cascade-slug>/wave-<wave>.base.json`:

```json
{
  "wave": <wave>,
  "base_sha": "<commit every leaf branches from>",
  "integration_sha": "<HEAD of swarm/<cascade-slug>/integration>",
  "user_branch": "<branch the user was on>",
  "created_at": "<ISO timestamp>",
  "leaves": {"leaf-NN": {"branch": "swarm/<cascade-slug>/leaf-NN", "worktree": "...", "commit": null}, ...}
}
```

and creates `swarm/<cascade-slug>/integration` (branch + worktree at `.swarm/<cascade-slug>/worktrees/integration/`) if this is the cascade's first wave. For a later wave, base = integration's HEAD, which must contain the user's HEAD (run `sync` at the end of the previous wave so Phase 2/3 writes for the new wave land on top of admitted work).

The timing is load-bearing: a base taken after leaves have started cannot say what they changed. The base is a commit rather than a hash table because git already answers "what differs from here" (`diff --name-only`), including for files the leaf created — the previous design's snapshot had to hash every file to get the same answer, and its live-tree half produced a false positive in every real cascade.

### 4.1 Create one worktree per leaf

```bash
python "$SWARM_SHARED_DIR/scripts/worktree_ops.py" add --slug <cascade-slug> --wave <wave>
```

For each brief in the wave this runs `git worktree add -b swarm/<cascade-slug>/leaf-NN .swarm/<cascade-slug>/worktrees/leaf-NN <base_sha>`, then:

- **Symlinks** each `worktree_link` entry (default `node_modules`, `.venv`, `venv`, `vendor`, `target`) from the main checkout. These are untracked, usually most of a repo by size, and never leaf-owned — but without them the leaf's own test command breaks, which is the entire point of the worktree. The link names are also written to the worktree's own `info/exclude`, because a *symlink* named `.venv` is not matched by a `.venv/` ignore pattern.
- **Copies** each `worktree_copy` entry.
- The leaf's `test_files` are already committed (4.0) and so present at their real paths. The leaf may read them and must not modify them.

The worktree is the leaf's working directory. Inside it the leaf edits its declared `impl_files` at their normal paths and observes a real RED→GREEN, because the test imports impl at its real path and inside the worktree that path is the leaf's own file. Nothing it does is visible to a sibling or to the user's checkout.

**Honest limit:** a worktree is a full checkout of tracked files per leaf (git shares the object store, so it is far cheaper than a copy, but it is still N trees on disk). A very large repo should run sequential waves rather than a wide parallel one. `worktree_link` is what keeps the per-leaf footprint small in the common case. Also: `git clean -fdx` in the main checkout would delete `.swarm/` and every worktree in it — warn the user if they habitually run it.

### 4.2 Per-leaf prompt shape

Each delegation call gets a self-contained prompt. **Self-contained means the brief travels in the prompt, not as a path to go read.** Paste the brief's body verbatim (frontmatter included) and the spec text its `spec_lines` range actually covers into the two blocks below — you already have both in hand from Phase 2, so inlining them costs nothing here and saves every leaf two read-turns before it can make its first edit, on every leaf, in parallel. The brief file is still written to disk exactly as 2.5 says: `check_invariants.py` parses it in Phase 3, and the paths below still name it so the leaf can re-read it if the prompt gets truncated.

```
You are leaf-NN of a TDD cascade. Your brief is inlined below — read it here,
not from disk. The same text is on disk at <absolute_briefs_dir>/leaf-NN.md
if you ever need to re-check it.

--- BEGIN BRIEF leaf-NN ---
<verbatim body of <briefs_dir>/leaf-NN.md, frontmatter included>
--- END BRIEF ---

--- BEGIN SPEC EXCERPT (<spec_file> lines <spec_lines>) ---
<verbatim spec text for exactly that line range>
--- END SPEC EXCERPT ---

That excerpt is the whole of the spec you need. Do not open the spec file for
more context; if the excerpt does not answer a question, that is an
escalation (see below), not a reason to go reading.

You are working inside your own git worktree at
<absolute_worktree_root> — a private checkout the parent manages. This is an
ABSOLUTE path; a subagent's shell cwd is the PARENT session's cwd, not this
worktree, so you must not assume you start inside it. Prefix every
impl/test file path you touch with <absolute_worktree_root> (e.g.
<absolute_worktree_root>/<impl_file>), and run the test command with
`cd <absolute_worktree_root> && <test_command>` — never a bare relative
path. NEVER run git (no add, commit, stash, checkout, branch — nothing);
the parent commits for you. Nothing you do there is visible to a sibling
leaf or to the user's checkout.

Your test file(s) are already written at <absolute_worktree_root>-prefixed
<test_files paths> and are failing. Your job: edit
<absolute_worktree_root>-prefixed <impl_files paths> IN PLACE, at their
normal paths inside the worktree, until those tests pass. Run the test
command yourself, from inside the worktree: confirm RED first, then GREEN.

Do NOT stage, copy, or move anything anywhere — the parent commits your
declared files from the worktree after you finish. Do NOT modify test files.
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

Before you log any inference in leaf-NN.ASSUMPTIONS.md, check the siblings
with ONE command — do not list the directory first, and do not read sibling
briefs:

  grep -il '<term>' <absolute_briefs_dir>/leaf-*.ASSUMPTIONS.md

No output (including "no such file") = no sibling has published anything
related; carry on. If it names a sibling's file, read that one file and
follow the brief's Sibling-assumption rule: adopt a compatible value
verbatim, escalate a contradictory one.

When your test(s) go green, write anything you want the parent to be able
to look up later — what you changed and why, anything surprising — to
<absolute_project_root>/.swarm/<cascade-slug>/reports/leaf-NN.md. Then return to the parent AT MOST
12 LINES, this shape and nothing else:

  leaf-NN green
  test: <command> — <N passed>
  changed: <path>, <path>
  assumptions: <count> (leaf-NN.ASSUMPTIONS.md)  questions: <count>
  report: <absolute_project_root>/.swarm/<cascade-slug>/reports/leaf-NN.md

No diffs, no code, no narrative in the return message. Everything you return
lands verbatim in the parent's context for the rest of the cascade; the file
does not.
```

### 4.3 Subagent type selection

This picks the *tool profile* (`subagent_type`), not the model — every impl leaf runs on Sonnet 4.6 regardless of which type below is chosen (see "Model defaults"). Default to **`general-purpose`** for every impl leaf. `cavecrew-builder`'s toolset is `Read, Edit, Write, Grep, Glob` only — **no `Bash`** — which means it cannot itself run the leaf's test command to confirm RED-then-GREEN; it can only manually trace test-vs-impl by reading, and every leaf that hits this gap has to explicitly flag "I could not execute the tests" rather than give the overlord a real pass/fail signal. That undermines the brief's own Acceptance step ("Confirm RED... Confirm GREEN"), which assumes the leaf itself runs the command. Pick by capability fit, not by habit:

- **`general-purpose`** — default choice for a normal impl leaf. Has `Bash`, so it can actually execute `test_file`'s test command before and after implementing, and report a real (not traced) RED→GREEN result. No hard file-count refusal, so brief sizing is governed by `impl_line_budget`/`test_assertion_budget` and the brief's own no-design-decision discipline, not by an incidental tool-selection ceiling.
- **`caveman:cavecrew-builder`** — optional, narrower-blast-radius alternative for a leaf that is genuinely trivial (single small file, no need for the leaf itself to execute anything — e.g. the overlord or a downstream step will run tests) and where the caveman-compressed report is worth more than execution capability. Needs only `Read, Edit, Write, Grep, Glob` and ≤ 2 impl files (it hard-refuses at 3+). Do not reach for it by default; use it deliberately when its trade-off actually fits the leaf.
- **`caveman:cavecrew-investigator`** — not used for impl leaves (it's read-only), but reach for it inline during Phase 2/3 if you need a quick file-locator pass without burning overlord context.

This is a hint, not a hard rule. The brief's footprint discipline is the actual safety net; the choice of sub-agent type is performance optimization. If a `cavecrew-builder` leaf hard-refuses mid-spawn, or reports it could not execute its own tests, re-spawn that one leaf as `general-purpose` — don't downgrade the whole wave.

### 4.4 Wait for all leaves to report

Do not advance to Phase 5 until every spawned leaf has reported green. Green now genuinely means green-in-isolation: each leaf measured it inside its own worktree, where no sibling's edits exist. A leaf that reports red after multiple attempts → escalate to user (the leaf may need a re-spawn with corrected brief, or the brief itself was wrong).

---

## Phase 5 — Wait + aggregate sweep

All leaves reported green. Before any admission:

### 5.1 Commit leaf worktrees

The wave base was taken in Phase 4.0, before any leaf ran. This step turns what each leaf produced into a commit on its own branch. For each leaf:

```bash
python "$SWARM_SHARED_DIR/scripts/worktree_ops.py" commit --slug <cascade-slug> --leaf leaf-NN
```

It refuses — and keeps the worktree untouched for inspection — when the worktree's `HEAD` is no longer the base (the leaf ran git), when `git status` shows any change outside `test_files + impl_files` (an undeclared write), when a declared `impl_file` does not exist, or when nothing changed at all (the leaf reported green without producing its files). Otherwise it stages exactly the declared paths that changed, commits `swarm(<slug>): leaf-NN — <task>`, records the sha in `wave-<wave>.base.json` and in `audits/wave-<wave>/leaf-NN.COMMIT`.

Run it for the whole wave in **one** shell call — `for L in leaf-01 leaf-02 …; do python … commit --slug <slug> --leaf $L; done` — not one tool call per leaf. Each call prints one line; the loop's output is the whole record. A refusal names its leaf, so nothing is lost by batching.

The overlord runs this, not the leaf. That is what makes Phase 6.3's file-match rule satisfiable by construction: the commit contains only declared paths, including nothing under `test_owned_by: parent` files the leaf may not touch — the leaf is never asked to place, stage, or commit anything.

Leave the worktree in place until the leaf is admitted or reverted; G5 reads it, and a refused commit is the forensic record of what the leaf actually did.

### 5.2 Aggregate assumption-sweep

Delegate this to one fresh **sweep-runner** sub-agent (Sonnet 4.6, `model: "claude-sonnet-4-6"`, `general-purpose`) — it is a read-and-classify pass over files, and every ASSUMPTIONS file it reads would otherwise sit in the overlord's context for the rest of the cascade. Give it in the prompt: the absolute `briefs_dir`, the absolute spec and contract paths, the bible path if the spec's Bible Compliance names one, the five categories below verbatim, the SWEEP.md template below verbatim, and the output path. It reads every `<briefs_dir>/leaf-NN.ASSUMPTIONS.md`, writes the sweep file, and returns at most 15 lines: `Total N, flagged M`, then one line per flagged entry (`leaf-NN / category K — <ten-word gist>`). The overlord reads flagged entries from SWEEP.md only when there are any. Nothing about the classification changes; only who holds the files while doing it.

The runner categorizes entries:

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

The overlord presents flagged entries to the user (from the runner's return lines; open SWEEP.md for the quotes only when the user asks). Default bias: patch, do not redo — redo costs an afternoon, patch usually costs minutes. User decides per entry.

If zero entries flag, write the file anyway with a single line: `Assumption-sweep clean. N assumptions reviewed, none drift.` G7 in Phase 6 requires the file to exist and to be newer than every leaf ASSUMPTIONS.

### 5.3 Open-question + proposal triage

- List `.swarm/<cascade-slug>/questions/leaf-NN-Q*.md`. For each, ensure either an answer at `.swarm/<cascade-slug>/answers/leaf-NN-Q<n>.md` exists OR the leaf's ASSUMPTIONS file tags it `unanswered: true`. If neither, the leaf made a silent decision — escalate to user for an answer before Phase 6.
- List `.swarm/<cascade-slug>/proposals/leaf-NN.md`. Resolve every `status: pending` proposal (parent applies + marks `accepted`, OR `rejected` / `superseded`). G4 in Phase 6 blocks on `pending`.

---

## Phase 6 — Admission loop

For every leaf with a commit recorded in `wave-<wave>.base.json`, in ascending NN order, spawn one fresh **admission-runner** sub-agent (Sonnet 4.6, `model: "claude-sonnet-4-6"`, `general-purpose`), **sequentially — never two at once**: 6.0 reads the previous leaf's log row and GATES.md, and `admit` mutates the shared integration branch. The runner executes 6.5 and 6.6–6.9 exactly as written below (both are single script calls that carry their own checks; the runner adds no judgment), then returns at most 10 lines:

```
leaf-NN: run_gates exit <0|1|2> — <Verdict line>
leaf-NN: admit exit <0|1|3> — <ADMITTED merge … (umbrella +N) | REVERTED — … | umbrella count unchanged …>
GATES.md: <path>
<on any non-zero exit: the FAIL/ADVISORY rows or the REFUSED line, verbatim, nothing else>
```

The runner **never** passes `--confirm-same`, never runs `revert`, and never edits anything: exit 3 (6.8's same-count yellow flag) and any FAIL row come back to the overlord, who decides and asks the user per 6.8. Two things stay with the overlord, not the runner, because they are judgment or forensics: reading a refused commit's reason (6.2) and routing a blocked leaf (re-spawn vs escalate). Every line the runner returns is the same line the scripts print; the runner is a context boundary, not a new reviewer. Why: a 16-leaf admission loop is ~50 tool calls whose full output — gate tables, umbrella listings, merge messages — the overlord would otherwise carry through every later turn, and the corpus shows that accumulated tool output, not judgment, is what makes the overlord the dominant cost of a cascade.

Per leaf, the sequence is:

### 6.0 Bypass detection

Read `.swarm/post-review-log.md`. List all `leaf-NN.md` files in `briefs_dir` whose NN predates the current leaf. For each, require **both**:

1. a row in the log, and
2. a gate-evidence file at `.swarm/<cascade-slug>/audits/wave-<wave>/leaf-NN.GATES.md` (written by 6.5).

Either one missing is a bypass:

> ⚠ BYPASS: `leaf-NN` has a brief but no post-review-log entry / no GATES.md. The file-match rule, parent-owned check, and umbrella were never verified for it. Confirm whether to audit now or accept the risk before continuing.

Requiring both is the point. A log row records that a leaf was *admitted*; it is not evidence that anything was *checked*. A wave whose leaves were verified in bulk and then logged afterwards produces a complete, clean-looking log and no GATES files at all — which is exactly what a collapsed admission loop looks like from the outside.

Two further tells, both cheap to check and both non-obvious once the log looks tidy:

- **Identical timestamps** across every row in a wave. The loop is per-leaf and sequential; rows minted in one pass share a timestamp to the second.
- **A surviving `worktrees/leaf-NN/` or `swarm/<cascade-slug>/leaf-NN` branch** for a leaf logged `clean`. 6.9a removes both on admit, so their presence means admission did not run the path that would have removed them (`worktree_ops.py status` lists them).
- **`git-ops.log` silence.** Every git call the cascade makes is appended to `.swarm/<cascade-slug>/git-ops.log` with a timestamp. A leaf logged `clean` with no `merge --no-ff` line for its branch was never merged.

Do not silently continue past a detected bypass. If `post-review-log.md` exists but lacks the required header (see 6.7), warn — the audit trail may have been tampered with.

### 6.1 G7 wave-sweep check (first admission of wave only)

If this is the first admission for this wave: require `.swarm/<cascade-slug>/wave-<wave>.SWEEP.md` to exist and to have an mtime newer than every `leaf-NN.ASSUMPTIONS.md` for this wave. If missing → block. If older than any leaf ASSUMPTIONS → block (re-run Phase 5.2).

For subsequent admissions of the same wave, skip this gate (it passed at first admission).

### 6.2 Verify the leaf commit exists

`wave-<wave>.base.json` must record a `commit` for this leaf and `audits/wave-<wave>/leaf-NN.COMMIT` must name the same sha. If absent: 5.1 refused or never ran for this leaf — read its refusal (undeclared write, HEAD moved, nothing produced) and re-spawn or escalate. Do not admit from a worktree directly.

### 6.3 File-match rule

Read the brief. Take the union of `test_files` + `impl_files`; call it `declared`. The set of paths the leaf's commit changes against base (`git diff --name-only <base_sha>..<leaf commit>`) must be a subset of `declared`, and every `impl_file` must exist on the branch. No extras, no renames.

- Any changed path outside `declared` → reject.
- Any declared `impl_file` missing from the branch → reject.

When `test_owned_by: parent` (default in this skill — tests are written on the parent side per 2.6, not by the leaf), the test files in `declared` are legitimately *absent* from the diff: the leaf may not modify them, so an unchanged test file is the expected shape, not a missing one.

### 6.4 G1 parent-owned check

For every path the leaf's commit changes, check it does NOT match any glob in `parent_owned`. Any match → reject. A leaf that needed to touch parent territory made a design decision the cascade forbids; the right fix is a contract proposal (Phase 5.3), not a direct edit.

### 6.5 Gate sweep — one command

```bash
python "$SWARM_SHARED_DIR/scripts/run_gates.py" --leaf leaf-NN --cascade <cascade-slug>
```

That runs every gate below, plus the artifact preconditions each one depends on, and writes the evidence file 6.5a describes. Exit 0 = clear to admit, 1 = blocking findings, 2 = paths could not be resolved. `--strict` (hardcore) blocks on the advisory gates and on a missing `BOUNDARIES.md`.

**Why a runner rather than a checklist.** These gates were prose for a long time, and prose has no failure mode: an overlord that ran all of them and one that ran none produced the same clean report and the same log row. A survey of 64 brief-carrying cascades found `BOUNDARIES.md` present 0 times, `TEST-AUDIT.md` 6 times, the wave baseline 12 times, and 13 of 15 `post-review-log.md` files holding a header and no rows at all. None of that was visible from inside a run.

The runner also treats a **missing input as a failure rather than a silence** — G5 with no wave base and G7 with no sweep used to read as "nothing to report" instead of "this gate could not run".

It deliberately does **not** admit anything: no merge, no reset, no umbrella run, no log row — every git call it makes is a read-only query. Those mutations belong to `worktree_ops.py admit` (6.6–6.9), which refuses to run until this runner has written a GATES.md with no FAIL row. The runner is the read-only verification that runs first, and the one file it writes is its own report.

Report it the same way as Phase 3's (3.2): on exit 0 surface only the runner's own `**Verdict:** … N blocking, N advisory, N pass` line plus the path of the GATES.md it wrote; on non-zero, render the FAIL/ADVISORY rows verbatim — gate, evidence, timestamp — because those are what the fix is written against. The full table is on disk in GATES.md either way, and `worktree_ops.py admit` reads it from there, not from your context. What it checks:


- **A1–A4 artifact preconditions** — the wave base commit (4.0, `wave-<wave>.base.json`), the assumption-sweep and its mtime against every ASSUMPTIONS (5.2/G7), the shard's `TEST-AUDIT.md` (3.4), and its `BOUNDARIES.md` (2.6). The first three block; `BOUNDARIES.md` is advisory unless `--strict`. Each of these is an input another gate reads, so a missing one is a gate that cannot run — reported as a failure rather than passed over.
- **6.3 file-match and 6.0 bypass detection** run here too, as part of the same pass.
- **G2 ASSUMPTIONS file** — note presence/absence. Do not block on absence (means brief was concrete). Do block if brief's prose implies inference happened but no log exists.
- **G3 open-question** — every published question must have a matching answer OR an ASSUMPTIONS entry tagged `unanswered: true`. If a parent answer disagrees with the leaf's recorded inference → block (the leaf wrote against the wrong assumption).
- **G4 contract-proposal** — `.swarm/<cascade-slug>/proposals/leaf-NN.md` must not be `status: pending`. If `accepted`, verify the target parent-owned file actually contains the change (grep for an identifying line).
- **G5 footprint integrity** — from `wave-<wave>.base.json` (Phase 4.0): every path in `git diff --name-only <base_sha>..<leaf commit>` must appear in this leaf's `declared` set, the commit must sit exactly one step above base (a leaf that ran git itself shows up here as extra parents or a moved worktree `HEAD`), and the worktree must carry no uncommitted change outside `footprint_ignore`. Any of these → block: the leaf wrote outside its footprint or touched git. Drift in the *user's checkout* during the wave is reported as `G5 live-tree drift | ADVISORY`, not a block — admission merges into the integration branch and never writes that tree, so nothing there can corrupt an admission. (Under the previous design this half blocked, and every real cascade ended up hand-writing a waiver for it.)

  The form before that compared only paths *outside* the leaf's footprint, against a snapshot taken *after* every leaf had already finished. It could not detect a footprint breach on either axis, and reported clean through one.
- **G6 escalation-trigger** — for every `escalation_triggers:` entry with a `detect:` command in this brief, run the command with `$STAGING_DIR=.swarm/<cascade-slug>/worktrees/leaf-NN/` (the leaf's tree, declared files at their real paths). If a trigger fires and no `.swarm/<cascade-slug>/escalations/leaf-NN.md` exists → block.
- **G8 test-quality gate** (leaves with 2+ `impl_files` only) — `test_quality_gate.py`, run for you by the runner. Reachability findings (a function nothing in the leaf's own impl calls — an orphaned/unwired implementation) block. Mutation findings (a function whose tests still pass after one mechanical mutation) print as advisory, not blocking by default — a single mutant can miss by bad luck rather than prove the test is weak; pass `--strict` (hardcore does) to block on those too.
- **G9 complexity gate** (all leaves) — `complexity_gate.py`, run for you by the runner. Flags any function over `--max-cyclomatic` (default 10) decision points or `--max-nesting` (default 3) block levels. Advisory by default — a high score is not proof of a defect the way G8's reachability is — pass `--strict` (hardcore does) to block on findings. Calibration, measured across 72 functions / 1,583 LOC of real cascade output (`experiments/scaling-test/phaseH-ceiling-search/` rungs H1–H3): cyclomatic peaked at exactly 10 and never exceeded it, so 10 sits on the natural ceiling; nesting never reached 3, so that half of the gate is untested rather than calibrated.
- **G10 scale gate** (all leaves) — `scale_gate.py`, run for you by the runner. Covers what G9 structurally cannot: G9 scores *cyclomatic* complexity, so `if item in big_list` inside a loop scores 3 and passes clean while running quadratically. Half A flags loop-nested shapes that turn a linear pass quadratic (self-join, membership scan, string concat, re-sort, N+1 IO); Half B, on leaves whose brief sets `scale_assertions: true`, confirms the test compares two input sizes rather than measuring one. Advisory by default, `--strict` (hardcore) blocks — a flagged shape is strong evidence, not proof.

### 6.5a Gate evidence

`run_gates.py` writes `.swarm/<cascade-slug>/audits/wave-<wave>/leaf-NN.GATES.md` itself, as each check returns:

```markdown
# leaf-NN gate evidence — wave <wave>

| gate | result | evidence | timestamp |
|------|--------|----------|-----------|
| file-match (6.3) | PASS | 1 changed path ⊆ 3 declared; all impl files present (commit abc1234) | <ISO> |
| G1 parent-owned  | PASS | no changed path matches parent_owned | <ISO> |
| G5 footprint     | PASS | every commit difference is declared; leaf never ran git | <ISO> |
| G8 test-quality  | ADVISORY | 1 mutation finding, non-blocking | <ISO> |
| ...              |      |          |           |
```

One file per leaf. This is what 6.0 checks for on the *next* leaf, and it is the only artifact that distinguishes a loop that ran from a log filled in afterwards. Because the runner writes it, a gate that did not execute has no row — the evidence cannot drift from what actually happened, which is exactly what an overlord writing it from memory could not guarantee.

Do not hand-write this file. If you find yourself composing one, the runner did not run.

Do not read it back either, on a clean pass. `run_gates.py`'s exit code already says whether any row blocks, and `worktree_ops.py admit` re-reads the file itself and refuses on a `| FAIL |` row — so on exit 0 the file needs no reader, and the summary line is the whole signal. Open GATES.md only when the exit code is non-zero, or when the user asks for a gate's evidence string. Same rule as 3.2: what is checked is unchanged, only how much of a passing run you carry forward.

### 6.6–6.9 Admit — one command

```bash
python "$SWARM_SHARED_DIR/scripts/worktree_ops.py" admit --slug <cascade-slug> --leaf leaf-NN
```

This is the mutating half of admission and it only touches `swarm/<cascade-slug>/integration` — never the user's checkout. It refuses unless `leaf-NN.GATES.md` exists with no `| FAIL |` row (6.5), and unless the integration worktree is clean. Then, in order:

**6.6 Umbrella pre-admission.** In the integration worktree, run `umbrella_test_cmd` (for pytest it appends `-v --tb=no -q` so results are per-test names). Record `pre_passing_tests` and `pre_count`. Count-only runners degrade the regression check to count-only (weaker gate; the log row says so).

**6.7 Merge + post-admission umbrella.** Before merging, the leaf's changed set is intersected with every other committed leaf's changed set in this wave — a non-empty intersection is an overlap breach (`G1/overlap breach | FAIL` is appended to GATES.md and the leaf is not admitted), whether or not git would have reported a conflict: two edits to one file can auto-merge cleanly and still be the collision the invariant forbids. Then `git merge --no-ff --no-edit swarm/<cascade-slug>/leaf-NN`. A conflict is impossible for a file-disjoint leaf; if one occurs it is an undeclared overlap — the merge is aborted, the same FAIL row is appended, a `BLOCKED` log row is written, and the loop continues with the next leaf. Run the umbrella again; capture `post_passing_tests` + `post_count`. If the brief's `## Acceptance` names a test command, run it in the integration worktree as a second independent gate.

**6.8 Decide.** Per-test regression first: `regressed = pre_passing_tests − post_passing_tests`; non-empty → revert. Then the net count: more → admit; fewer → revert; **same** → the yellow flag — the merge is left in place and the command exits 3. Ask the user (possible integration-boundary slice, or an umbrella that already passed); then either `admit --leaf leaf-NN --confirm-same` or `revert --leaf leaf-NN`.

**6.9a Admit.** The merge commit is the admission. The leaf worktree is removed (`--force` — its symlinked deps are untracked; the commit already exists so nothing is lost), its branch deleted (`git branch -d`, safe because it is merged), and one row appended to `.swarm/post-review-log.md`:

```
# Post-Review Log — append-only, do not edit manually
# Editing this file invalidates bypass-detection.

| wave | shard | leaf_id | files | delta | timestamp | status | leaf_commit | merge_commit |
|------|-------|---------|-------|-------|-----------|--------|-------------|--------------|
| <wave> | <shard-or-default> | leaf-NN | <impl_files>, <test_files> | +N | <ISO> | clean | <sha> | <sha> |
```

An existing seven-column log keeps its header; the two shas are folded into the status cell. The row's timestamp is the real admission time — rows sharing one timestamp across a wave are a bypass signal (6.0), because the loop that produces them is sequential. The log is append-only. Never edit, reorder, or delete entries.

If `graphify_cmd` is set, run it and inspect for unexpected couplings (new import edge between leaf-owned modules that wasn't in the design). Flag for user; do not block.

**6.9b Revert.** `git reset --hard <pre-merge sha>` in the integration worktree — the admitted siblings before this leaf are untouched, the leaf's merge is gone. The leaf worktree is removed and its branch renamed to `swarm/<cascade-slug>/reverted/leaf-NN`: the commit is the forensic record of what the leaf actually did, and it costs nothing to keep. A `REVERTED` row goes into the log with the regressed test named, and a `## Post-review regression` block is appended to `<briefs_dir>/leaf-NN.md`. The loop continues with the next leaf — one revert does not stop the rest of the wave.

**End of wave — `sync`.** After the last admission, `worktree_ops.py sync --slug <cascade-slug> --yes` fast-forwards the user's branch to integration so the next wave's Phase 2/3 writes land on top of admitted work. If the user committed on their branch meanwhile, fast-forward is impossible: the command stops and prints the two commands the user may choose from; the skill never rebases or merges on the user's behalf.

---

## Phase 7 — Final report

After every leaf in the wave has been processed:

### 7.1 Apex test (if configured)

If `apex_test_cmd` is set in `.claude-swarm.toml`, run it. Apex is the behavioral integration test — distinct from `umbrella_test_cmd` (per-leaf isolation). Apex catches the failure mode where every leaf's umbrella passed but the integration composes incorrectly.

**Apex owns absolute numbers; per-leaf tests own ratios only.** Apex is the one place a wall-clock or throughput budget means anything, because it runs alone after the wave. Leaf tests run while up to 16 siblings compete for the same CPU, so a duration threshold there flakes both ways — false RED stalling a wave, false GREEN admitting a quadratic. That is why 2.6's scale assertions are growth ratios: it is the only scale signal parallel spawn leaves intact.

Apex failure does NOT auto-revert (multiple leaves admitted; attributing the failure to one is a separate forensic step). Report the failure + suggest investigation paths (likely candidate: any leaf whose test was source-grep heavy rather than behavioral).

### 7.2 Report

Before printing, record the cascade — one command, zero LLM tokens:

```bash
python "$SWARM_SHARED_DIR/scripts/cascade_metrics.py" --cascade <cascade-slug> --live [--variant <label>]
```

It reads the local Claude Code transcripts for this cascade's window (first `git-ops.log` line → now), attributes tokens and $ to the overlord and to each sub-agent role (deduped by `message.id`, priced from `rates.json`), joins the cascade's own artifacts (gate rows, audit severities and rounds, log rows, questions/proposals, sweep flags), and writes `.swarm/<cascade-slug>/METRICS.{md,json}` plus a copy in `~/.claude/swarm-metrics/` that survives a gitignored `.swarm/`. Pass `--variant` when a skill variant is under test so runs can be compared later. Surface only its summary line; the cost line below comes from it. Exit 1 means it recorded with a gap (named on stderr) — say so in the report, do not hand-fill numbers. Why this runs every time: the 2026-08 audit found the overlord chat is ~78% of a cascade's cost and had never been measured, because nothing recorded it at the time.

Print to the user:

```
Wave <wave> complete.

| leaf    | delta | status   |
|---------|-------|----------|
| leaf-01 | +2    | clean    |
| leaf-02 | REVERTED | regression: tests/test_cache.py::test_miss |
| ...     |       |          |

Cost: overlord $X (P%), sub-agents $Y over N spawns, total $Z, W min  (METRICS.md)
Totals: N admitted, M reverted, K escalated.
Apex: <PASS | skipped | FAILED>.

Residual git state (worktree_ops.py status):
  reverted        swarm/<cascade-slug>/reverted/leaf-02   # commit kept for forensics
  leaf-worktree   .swarm/<cascade-slug>/worktrees/leaf-05  # refused at commit — inspect
```

The residual block is printed verbatim from `worktree_ops.py status`. Nothing the cascade created on disk or in refs is allowed to linger silently: every surviving worktree or branch is either listed here with its reason, or gone.

### 7.3 Direction for follow-ups

- For each reverted leaf: name the regressed test, point at the appended `## Post-review regression` block, suggest re-spawn with corrected brief.
- For each escalation (G3/G4/G6 blocks resolved during the loop): list what got resolved and how.
- For wave-sweep flags accepted as patches: confirm the patches landed.

### 7.4 Finish — fast-forward and clean up

```bash
python "$SWARM_SHARED_DIR/scripts/worktree_ops.py" finish --slug <cascade-slug>
```

Without `--yes` it shows `git log --oneline <user-branch>..swarm/<cascade-slug>/integration` and stops (exit 3). Show that to the user; on approval re-run with `--yes`: the user's branch is fast-forwarded to integration (the second and last write to it), the integration worktree and branch are removed, `git worktree prune` runs, and the residual list is printed again. Reverted branches and refused worktrees survive `finish`; `cleanup --slug <cascade-slug> --purge --yes` removes them once the user has looked. If fast-forward is impossible the command prints the two options and stops — never rebase or merge non-ff on the user's behalf.

---

## What this skill does NOT do

- **Write impl code itself.** The overlord writes spec, contract, and the umbrella test; the shard-test-writer writes per-leaf tests. Impl is the leaf's job.
- **Delegate the DECISION or hide the review.** Spec approval, contract locking, brief emission, and gate enforcement are decisions and always happen in the overlord chat, visible to the user. What the overlord MAY do (see "Delegated drafting passes" below) is spawn a fresh sub-agent to produce a DRAFT of a hard synthesis artifact — a proposed decomposition shape, a proposed spec section, a proposed resolution of an ambiguity — which the overlord must then independently verify against everything it already knows (the spec, the contract, prior wave history, the user's own words in this chat) before adopting any part of it. The draft and the overlord's verification/edits are both rendered to the user; nothing about the reasoning is hidden. This is drafting-labor delegation, not decision delegation. If the overlord ever adopts a drafted artifact without recording its own independent check against it, that IS the banned failure mode — the boundary is the verification step, not the existence of a draft.
- **Run git anywhere except `worktree_ops.py`, or touch the user's branch without asking.** Leaves never run git — their prompt says so and G5 catches a leaf that does. The overlord never types a raw git command either; every branch, worktree, commit, merge, reset and deletion goes through the one script, is logged to `.swarm/<cascade-slug>/git-ops.log`, and stays on `swarm/<cascade-slug>/*` refs. The user's own branch is written exactly twice, both after an explicit yes: the wave base commit (4.0) and the final fast-forward (7.4). No stash, no rebase, no `reset --hard` on the user's checkout, ever.
- **Auto-spawn leaves before Phase 3 passes.** Phase 4 only fires after Phase 3 reports `all PASS`. Pre-audit spawn re-introduces every failure mode the audit prevents.
- **Make architecture decisions silently.** Phase 1 surfaces Bible Compliance + each draft as an explicit approval gate. Phase 1.5 surfaces contradictions between the locked artifacts, and any external capability the spec assumes. Phase 2 surfaces fat-file collisions + leaf-count guardrails. Phase 3 surfaces invariant violations. Phase 5 surfaces aggregated assumption drift. Phase 6 surfaces per-leaf gate failures. Silence at any of these is the failure mode; explicit user choice is the success path.

---

## Return-message discipline (every spawn)

A sub-agent's final message arrives in the overlord's context verbatim as a task notification, and stays in the prefix for every remaining turn of the cascade. Real cascades returned 25k–40k-character leaf reports — essays with diffs — and a wave of them is a larger share of the overlord's prefix than SKILL.md itself. So every spawn prompt in this skill ends with a line cap and a file path for the rest: the leaf (4.2, 12 lines + `.swarm/<cascade-slug>/reports/leaf-NN.md`), the shard-test-writer (2.6, 10 lines), the auditor (3.4.2, counts + one line per 🔴/🟡), the test-fixer (3.4.3, 5 lines), the sweep-runner (5.2, 15 lines) and the admission-runner (Phase 6, 10 lines). Delegated drafting passes below already return a file path plus a short summary. If a sub-agent returns more than its cap, do not re-summarize it in your own words — that pays output tokens to add a second copy — just proceed; the cap is a prompt rule, not a gate.

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

A **shard** is a partition of one wave: its own shard-test-writer, its own test-auditor, and its own audit dir. It is a label, not a git object — shards inside a wave share the wave number, the wave base commit, the integration branch, and the sweep. Every gate script already resolves a shard from the brief's `shard:` field independently of `wave:`, so nothing needs a distinct wave number per shard.

### Sizing — 5-6 leaves per shard

Two limits are in play and they are **not** the same number:

- The **16-leaf cap** (Phase 2.3) bounds one wave. It is sized for worktree isolation and for the overlord's brief-writing load — roughly 120 lines of brief per leaf.
- The **5-6 leaf shard cap** bounds one shard-test-writer. That agent holds the shard's entire brief set *and* every impl file its tests target, then emits working test code plus one boundary table covering all of them.

Measured on a real cascade: ~376 lines of test code, ~17 assertions and ~28 `BOUNDARIES.md` rows per leaf, against target impl files ranging from 10 to 3,975 lines. At 16 leaves that is ~6,000 lines of test code, ~320 assertions and a ~450-row boundary table, emitted from one context that has already read ~19,000 lines in. The three failure modes the 16 cap cites — drift between siblings, context fill, missed cross-leaf contradictions — bite the writer *harder* than they bite a leaf: each leaf holds only its own brief, while the writer holds every one of them and has to produce working code against each.

So: **`shards = ceil(leaves / 6)`**. A wave of 6 or fewer is one shard and writes to `default/`.

Two overrides sit on top of the arithmetic:

- **Volume.** A leaf whose target impl exceeds ~2,000 lines counts as more than one against the shard budget. A single 4,000-line target can earn its own shard even in a small wave — reading it is most of that writer's context.
- **Co-location.** Leaves whose ACs cite each other's symbols, units, or constants go in the **same** shard. This is the inverse of Phase 3's non-overlap rule: non-overlap keeps *files* apart, co-location keeps *semantics* together, because a contradiction between two ACs is only findable inside one context. In the cascade the numbers above come from, a counter specified in three incompatible units was caught by the one shard that happened to hold two leaves, and by nothing else in the run.

**No file overlap across shards, ever** — the same non-overlap invariant Phase 3 enforces within a wave, extended to every shard running at the same time. Two shards racing to write one file is the collision this whole partition exists to prevent. If the Phase 2.1 dependency map can't guarantee that separation, don't shard the wave — sequence it instead.

### Going past one wave

The 16 cap bounds one wave's leaf count, not the cascade's total parallelism. A large, genuinely-decomposable spec (dozens of independent slices, no shared-file dependencies between groups of them) can run several waves **concurrently**, each branching from the same integration HEAD — the way a real multi-agent rewrite (64 concurrent Claude instances porting a 500K-line codebase, organized as 4 isolated worktrees of 16 agents each rather than one flat pool of 64) actually scaled. The ceiling there wasn't the agents' reasoning quality, it was **write-collision on shared state** — agents running conflicting git commands against the same checkout. The fix was architectural isolation, not a bigger flat pool.

Manager-mode's equivalent shared state is `swarm/<cascade-slug>/integration`, `post-review-log.md`, and the wave base/sweep files. Concurrent waves each take their own wave number and their own `.swarm/<cascade-slug>/wave-<N>.base.json` / `.SWEEP.md` / `.AUDIT.md`; `post-review-log.md` stays a single append-only file, disambiguated by its `wave` and `shard` columns, since admission is still one leaf at a time. Each concurrent wave obeys the 16 cap on its own, and is itself partitioned into shards by the 5-6 rule above — so a 4-wave run is up to 64 leaves in ~12 shards, mirroring 4 isolated groups rather than one ungoverned pool.

Most specs fit in one wave and never need this subsection. Reach for concurrent waves only when the dependency map already shows multiple large, file-disjoint groups of slices and running them sequentially would just be waiting with no coordination benefit.
