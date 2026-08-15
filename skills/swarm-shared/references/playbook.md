# TDD Cascade — Playbook

Condensed theory behind the `/manager-mode` skill's phased cascade. Phase numbers below refer to `/manager-mode` SKILL.md.

This file is the skill's portable summary. If a project ships its own playbook, that one wins on policy questions and `/manager-mode` should defer to it.

---

## Core Principle

The spec is the source of truth. Tests encode the spec as executable assertions. Implementation exists only to make tests pass. Nothing is built without a failing test. Nothing is tested without a reviewed spec.

---

## The Cascade

Every decomposition produces exactly four layers, in this order:

```
Spec (in spec_dir)
  ↓ reviewed and locked by human
Shared type contract (type_contract_path)
  ↓ written by parent, locked before decomposition
Umbrella test
  ↓ written by parent, must fail (RED), encodes all acceptance criteria
Decomposition into leaf tasks (briefs_dir)
  ↓ parent slices, assigns, never touches again until admission
```

If the project's playbook adds a gate (e.g., an extra compliance check between spec and type contract, configured via `[gates].extra_spec_gate_cmds`), respect it. The cascade above is the minimum.

---

## The Three Invariants

These are the structural rules a leaf assignment must satisfy. Every recurring failure mode in parallel-agent TDD work reduces to violating one of them. `/manager-mode` Phase 3 (the deterministic invariant audit) checks all four (the three classical invariants plus the Spec Link Rule) before any leaf may be spawned.

### 1. File-ownership non-overlap

Every file in the source and test directories has **exactly one owner** at any given time.

- Parent owns: specs, shared type contract, test fixtures, umbrella test, integration tests, dependency config.
- Each leaf owns: one test file + one impl file.
- No file may appear in two briefs.
- No brief may name a parent-owned file.

The graphify (or fallback dependency map) must confirm non-overlap **before** assignment. If the map shows a planned coupling between two slices, restructure the slices until each is isolated.

### 2. No design decisions at the leaf

A leaf agent translates spec assertions into code. It does not choose API shapes, invent type names, pick libraries, decide naming, or resolve ambiguity. If the test references a type, that type must already exist in the locked shared contract. If anything is unclear, the leaf stops and escalates.

In a brief, design-decision risk shows up as:
- Verbs like *decide*, *choose*, *design*, *determine*, *figure out*, *resolve*.
- A spec line range that is vague or empty.
- A type import from a path not on the contract allowlist.
- An invitation to "use your judgment" or "as appropriate".

These are caught at audit time, not at execution time.

### 3. Sizing — one leaf, one slice, and prefer fewer files over more

A leaf must be small enough that the agent can finish it in one pass without intermediate decisions. The unit is fixed: **one test file + one (or a small number of) impl file(s).** Two sizing signals matter, and they are not interchangeable:

- **Impl line budget** (default 1000, configurable) — a ceiling on a leaf Phase 2.2's consolidation pass already judged coherent, not a sizing input itself. Raise toward 1500 as needed; past 2500 is a hard stop requiring explicit user confirmation (Phase 2.4). All three numbers provisional pending validation beyond H2's tested 585-LOC ceiling.
- **File count** — the stronger cost driver in practice: token usage correlates with the number of files a leaf/wave touches more than with raw LOC concentrated in one file (see `experiments/scaling-test/REPORT.md`, Phase E vs. Phase F). All else equal, prefer slicing along fewer, larger, single-owner files over more, smaller ones, provided the file still maps to one coherent responsibility and the impl-line budget for that file is raised to match (do not silently exceed the configured budget — raise it explicitly for that brief and record why).

If the *responsibility* itself doesn't factor into one coherent piece (two genuinely unrelated concerns), split into two leaves regardless of line count — sizing by LOC alone can hide a responsibility-boundary problem a file-count-only read would miss. If it's one coherent responsibility that's just larger, prefer raising that leaf's line budget over fragmenting it into siblings whose only reason to be separate is the old default ceiling.

Phase G (`experiments/scaling-test/phaseG-isolated-single-file/`) is the properly-isolated validation of this preference — G1-G4 held under genuine 3-agent isolation with zero unresolved defects (largest file 339 LOC, mean budget utilization 46%), never finding an actual ceiling. Phase H (`experiments/scaling-test/phaseH-ceiling-search/`) pushes rungs deliberately far past G4's scale to look for where one actually exists; G9 (the cyclomatic-complexity/nesting-depth admission gate, Phase 6.5) is the mechanical backstop in the meantime, in case a large single file trades LOC headroom for tangled control flow LOC alone wouldn't catch.

---

## Roles

### Parent

Runs on Opus 5. Writes the spec; writes the shared type contract; writes the umbrella test (and confirms RED); slices into leaf briefs; admits leaf diffs one at a time; reruns the umbrella after each admission. Never writes impl code, never writes per-leaf tests (that's the shard test-writer's job — a parent grading its own leaf tests is the same self-enhancement bias the cascade forbids leaves from having).

### Shard test-writer

Runs on Opus 5, same tier as the parent — judging whether a test correctly encodes an ambiguous spec line is the same caliber of call as decomposition, and a weak test here is invisible until a leaf has already built against it. One per shard, always spawned separately from the parent, even for a single-wave run with no shard. Given the locked spec/contract and that shard's brief set only — writes every per-leaf test in the shard, confirms each RED, never touches impl, never sees sibling shards' briefs. When a leaf's brief declares 2+ `impl_files`, its test must include one interaction assertion (does the orchestrator actually call the collaborator?) alongside the state checks — a leaf never gets to be the only thing that verifies its own resolution of an ambiguity.

### Leaf

Runs on Sonnet 5, always — implementing against an already-locked, already-audited failing test is bounded mechanical work by design, not a judgment call, so it doesn't need the heavier tier. Receives one assignment: one test file, one impl file, the spec line range it must satisfy, the DO-NOT-EDIT list, and the contract imports it may use. Runs test → confirms RED → writes minimum impl → confirms GREEN → commits → stops. Never creates files. Never edits anything outside its assignment. Never makes design decisions. On ambiguity, stops and reports — does not guess.

---

## Intake interview and the assumption log

`/manager-mode` Phase 0 locks the scope of the batch *before* any procedure runs, because the most common cascade failure mode traces post-mortem to one of the intake questions being silently inferred by the parent agent instead of stated by the user.

Leaf agents follow the assumption-log convention: if a leaf had to infer anything during its run, it writes `<briefs_dir>/leaf-NN.ASSUMPTIONS.md`. The brief boilerplate (`brief-template.md`) gives leaves the format.

After all leaves report green (`/manager-mode` Phase 5), the parent runs the **aggregate assumption-sweep**. The sweep reads every leaf log, classifies entries against the spec, the bible (source-of-truth doc), and the type contract, and surfaces drift with a damage assessment and a patch suggestion. The user makes the call on patch vs. redo. Default bias: patch — redo costs an afternoon, a patch usually costs minutes. The sweep output is written to `.swarm/wave-<wave>.SWEEP.md` and is required (G7) before any admission of the wave begins.

The reason this is a written convention rather than a free-form check: an LLM auditing its own inferences in the same turn rarely catches them. A separate sweep, against persisted logs, with explicit categories (contradicts-spec / contradicts-strategy-doc / cross-leaf / fabricated / compounded), forces structured re-examination.

---

## Prep steps and long-term seam stability

The cascade works on existing projects, not just green-field ones. Two patterns emerge specifically on mature codebases.

### Prep steps

A **prep step** is a parent-owned architectural commit that happens *before* decomposition — not a leaf brief, not a code-writing task. It exists when reslicing alone cannot resolve a fat-file collision: one existing file covers multiple ACs that must become separate leaves, and sequential waves would cost too much parallelism.

Prep step protocol:
1. Parent identifies the file and the split seam (e.g., one function per AC, one sub-file per feature).
2. Parent commits the refactor. No new behavior — only structural split.
3. Parent runs the umbrella. Must be green before and green after. If it regresses, the split introduced a bug; fix before proceeding.
4. Parent re-emits briefs against the new sub-files. Each sub-file maps cleanly to one leaf.

The prep step is the parent's move, not the leaf's. No leaf may restructure a file it didn't own before — that is a design decision the cascade explicitly forbids at the leaf layer.

### Seam-axis commitment

The split seam chosen in a prep step (by function, by module, by feature, by data type) is an architectural commitment. Changing seams later costs a re-restructuring pass. Before committing, ask:
- Is this axis stable through the next few waves of work?
- Does the axis map to a stable dimension of the spec (e.g., the strategy doc's taxonomy) rather than to the current wave's AC list?
- Will new features add new slices along this axis, or cross-cut it?

Record the seam-axis decision in `decisions.md` with an explicit "review at wave N" clause. That makes future re-seaming a planned event, not a surprise.

### When not to do a prep step

If sequential waves cost only 1–2 admissions of serialization, that is cheaper than a prep-step split. Reserve prep steps for cases where the serialization cost is high (many sequential leaves on the same file over multiple waves) or where the fat file is a recurrence risk (every new wave hits the same collision).

### Long-term accumulation risk

Many sub-files solve the leaf-isolation problem but introduce new ones at scale: a thin dispatcher gains coordination logic and grows fat; cross-cutting concerns (shared SQL views, shared helpers) must live somewhere and become new parent-owned surfaces; schema rename touches N files instead of 1. These are not reasons to avoid prep steps — they are reasons to commit the seam axis carefully and enforce the "dispatcher stays mechanical" rule in `decisions.md`.

---

## File-mediated async coordination

Leaves never message each other directly. The cascade is a tree: parent at the root, leaves at the fringe, no edges between leaves. Direct leaf-to-leaf messaging would turn the cascade into a graph and destroy regression attribution — when a regression appears, you would no longer be able to point at one leaf and say "this is the cause." Three coordination patterns exist; all are file-mediated, parent-arbitrated, and strictly additive to the cascade invariants.

### 1. Sibling-ASSUMPTIONS read

Leaves may **read** (never write) other leaves' `leaf-NN.ASSUMPTIONS.md` files before logging their own inferences. The brief boilerplate instructs leaves to grep sibling logs for related entries and either adopt the sibling's value (compatible) or escalate (contradictory) instead of silently logging a clashing assumption.

Catches drift at leaf-time instead of at the parent's post-admission sweep. The sweep still runs — this is an early filter that reduces what survives to the sweep.

Failure mode prevented: two leaves silently inferring incompatible shapes of the same shared interface. Today: caught at admission-time, after both wrote code. With sibling-read: caught at leaf-time, before either commits to code.

### 2. Question ledger

Leaves publish questions to `.swarm/questions/leaf-NN-Q<n>.md` instead of inferring silently. The parent answers asynchronously at `.swarm/answers/leaf-NN-Q<n>.md`. The leaf proceeds under a best-guess inference if no answer arrives; the inference is recorded with an explicit `unanswered: true` tag.

`/manager-mode` Phase 6.5 gate **G3** enforces resolution before admission: every published question must either have an answer or be acknowledged as unanswered in ASSUMPTIONS.

This is forensic, not synchronous. Leaves do not block on questions — they record them and continue under best-guess. The gate converts "silent inference" into "logged inference with explicit parent acknowledgement." If the parent's answer contradicts the leaf's guess, G3 surfaces the contradiction by name.

Failure mode prevented: a leaf needs to know X, brief is ambiguous, leaf infers and writes code. Today the inference might appear in ASSUMPTIONS but is indistinguishable from any other inference. With the question ledger, the existence of `.swarm/questions/leaf-NN-Q<n>.md` proves the leaf flagged the uncertainty rather than absorbing it silently — and the parent's answer (if present) is the canonical decision.

### 3. Contract proposals

When a leaf needs a parent-owned file changed to satisfy its brief, it writes `.swarm/proposals/leaf-NN.md` instead of editing the file (which G1 would reject) or duplicating the file (which silent drift would absorb). The proposal contains the proposed diff and the reason it is required.

The parent reviews and sets `status: accepted | rejected | superseded`. Accepted proposals require the parent to first apply the diff to the target file; `/manager-mode` Phase 6.5 gate **G4** verifies the change is actually present, not just marked accepted.

Failure mode prevented: leaf needs a type contract extended. Today the leaf either escalates and stalls the wave or invents a duplicate type. With proposals, the request is visible, the change is applied by the parent (preserving G1), and the gate ensures application before admission.

### What is intentionally not built

- **Direct leaf-to-leaf messaging.** Would make the cascade a graph; would destroy regression attribution; would create deadlock and ordering bugs. Not added under any pretext.
- **Shared mutable state owned by N leaves.** Would break file-ownership invariant (the first invariant). Not added.
- **Synchronous waits.** A leaf cannot block on parent action; it proceeds under best-guess and the gate checks consistency at admission time. Async by design.
- **Cross-leaf reads of pending impl code.** Leaves may read sibling ASSUMPTIONS (immutable once published, structurally separate from impl) but never sibling impl in `.swarm/pending/`. Coupling admission order to file resolution would create dependency hell.

All three additions are strictly additive: each is a gate that, if turned off, reverts to the pre-coordination behavior. They do not change the cascade shape, the three invariants, or the parent-only-arbitrates rule.

---

## Staging is the only canonical mode

Leaves write to `.swarm/pending/leaf-NN/`. The skill copies from staging to real at admission time and only if every gate passes. There is no override that lets a leaf "write to real to save a step" — across session compacts, parallel agents, and audit trails, the staging dir is the only thing that preserves provenance. A workflow that lets leaves write directly to real for any reason re-introduces three failure modes simultaneously: ownership ambiguity (which leaf authored this hunk?), audit-log gaps (post-review-log claims clean while HEAD says otherwise), and bypass of every G1–G6 gate (none of them run on direct writes).

`/manager-mode` Phase 6.5 gate **G5** (wave-snapshot integrity) is the post-hoc detection for this: if a leaf writes directly to real, the hash of that file at admission time will not match the wave-start snapshot, and G5 blocks the admission of any leaf in the wave. Detection, not prevention — but the gate forces the violation to surface before it propagates.

---

## Why the cascade exists

It is the only known way to run many AI agents in parallel without one stepping on another's work, without any of them silently making architectural decisions, and without any of them quietly producing more code than they can keep coherent. The three invariants are not stylistic — they are the structural guarantees that make parallel decomposition safe. Skip one and you re-introduce the failure mode it was preventing.
