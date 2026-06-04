# Leaf Brief — Canonical Template

Every leaf brief emitted by `/manager-mode` Phase 2 follows this shape. `/manager-mode` Phase 3 (via `check_invariants.py`) parses these fields directly and will fail audit if any are missing or malformed.

A brief is the *entire* context a leaf agent receives. Nothing else. No project overview, no rationale, no description of sibling leaves. The minimum that lets the leaf finish its slice without needing to make a decision.

---

## Format

```markdown
---
leaf_id: leaf-NN
spec_file: <path to spec>
spec_lines: <start>-<end>
test_file: <single test file path>
impl_file: <single impl file path — owned by this leaf>
# Optional plural forms (use ALONGSIDE singular when a leaf legitimately
# spans multiple files — e.g. pgTAP unit+integration test pair, or an
# adapter that needs a tiny __init__.py re-export):
# test_files:
#   - tests/db/test_fn_X_unit.sql
#   - tests/db/test_X_integration.sql
# impl_files:
#   - src/pkg/__init__.py
#   - src/pkg/adapter.py
contract_imports:
  - <fully-qualified symbol from locked type contract>
  - <fully-qualified symbol from locked type contract>
do_not_edit:
  - <glob or path>
  - <glob or path>
impl_line_budget: <int>
test_assertion_budget: <int>
# Optional: who writes the RED test. Default `leaf` (leaf owns both test
# and impl). Set to `parent` for projects where parent-agent authors the
# umbrella + integration tests and the leaf only writes impl. When
# `parent`, the test_file is NOT subject to the parent-owned glob check
# and other briefs don't need to include it in their do_not_edit.
# test_owned_by: parent | leaf
# Optional: parallelism wave. Default 1. Leaves in different waves run
# sequentially (e.g. wave-2 follow-up edits a file wave-1 already owned).
# Cross-wave leaves skip overlap + do_not_edit checks against each other.
# wave: 1
# Optional: codebase preconditions. /manager-mode Phase 3.1 runs each `verify:`
# command; non-zero exit = brief makes a false claim about codebase state.
# Required when the brief asserts that some prior code/state exists
# ("X is in place", "Y was added in wave N-1"). Without verify, Phase 3.1
# heuristic-warns on claim-words in task prose but cannot block.
# codebase_preconditions:
#   - name: "wave-2 gate exists"
#     verify: "grep -q 'def wave2_gate' src/gates.py"
#   - name: "damage.py has cover term"
#     verify: "grep -qE '\\(1\\.0 - cover\\)' simulation/damage.py"
# Optional: escalation triggers with `detect:` commands. /manager-mode Phase 6.5 G6
# runs each detect command at admission time; if any exit 0 (match found) and
# no `.swarm/escalations/leaf-NN.md` exists, the admission blocks.
# escalation_triggers:
#   - name: "signature_change"
#     detect: "! diff <(grep -E '^def ' src/module.py.bak) <(grep -E '^def ' $STAGING_DIR/src/module.py) > /dev/null"
#   - name: "new_file_creation"
#     detect: "test ! -f src/new_module.py"   # exits 0 if file is new
---

## Task

<One-paragraph imperative description. Must reference spec_lines for any
behavioral claim. Must not contain ambiguous verbs (decide, choose, design,
determine, figure out, resolve, "as appropriate").

Must NOT contain ready-to-paste implementation bodies — the leaf authors the
body. Permitted shape-carriers in the brief:
  - `spec_lines` refs (cite line ranges in the spec file).
  - `contract_imports` (named symbols the impl must use).
  - Stub signatures (≤ `max_brief_code_lines` total lines across all fenced
    code blocks — function headers, type aliases, SQL signatures only).
  - Mirror-pointers in prose: "match the structure of `path/to/sibling.py`"
    or "mirror the comment-header style of `004_families_realign.sql`".
  - Invariant statements: "this function must be idempotent",
    "must short-circuit on empty input", etc.

Embedding a full implementation collapses the parallelism payoff: the parent
absorbs leaf work and the leaf becomes a copy-paste courier. Audit blocks
briefs whose fenced code exceeds `max_brief_code_lines`.>

## Acceptance

Run `<test command>` for this test_file. Confirm RED. Implement in impl_file
only. Confirm GREEN. Write your final `test_file` and `impl_file` to
`.swarm/pending/leaf-NN/` mirroring their paths from the project root
(e.g. `src/cache.py` → `.swarm/pending/leaf-03/src/cache.py`). Stop.
Do not copy files to their real destinations — `/manager-mode` Phase 6 does that after gating.

## Escalation triggers

Stop and report to the parent if:
- A type the test imports is not in contract_imports.
- The impl would need to create a new file.
- The impl would need to edit a file in do_not_edit.
- Two sibling assertions seem to require contradictory behavior.
- Impl approaches impl_line_budget with assertions still failing.

## Assumption log

If at any point during your run you had to **infer** something the brief did not specify (a default value, an error code, a representation choice, anything), write it to `<briefs_dir>/leaf-NN.ASSUMPTIONS.md` before you commit. Format:

```markdown
## Assumptions made during leaf-NN

- **<thing>**: <inferred value> — source: <which spec line / contract symbol / file you looked at, or "no source — pure guess">
```

Do not bury inferences inside impl comments. The parent runs an assumption-sweep across all leaves before any admission — that sweep only sees the .ASSUMPTIONS.md files. An undocumented inference cannot be swept.

## Sibling-assumption read (do this before logging)

Before you append a new entry to your own `leaf-NN.ASSUMPTIONS.md`, check whether a sibling already published a related inference:

1. List `<briefs_dir>/leaf-??.ASSUMPTIONS.md` (every leaf's file other than your own).
2. Grep for terms related to the thing you are about to infer (the type name, the field name, the behavior).
3. If a sibling already declared a value:
   - **Compatible** (your inference would match): adopt the sibling's value verbatim and add `— matches sibling leaf-XX` to your log line. Cascade stays coherent.
   - **Contradictory** (your inference would clash): do **not** log your value as a quiet assumption. Instead, write a question (see next section) or escalate to the parent. Two contradictory assumptions across siblings is exactly the drift the cascade exists to prevent.
4. If no sibling published anything related: continue as normal.

You may only **read** sibling ASSUMPTIONS files. You may never edit one. Cross-leaf writes break the file-ownership invariant.

## Question ledger (when you would otherwise infer silently)

If the brief is ambiguous on a point that materially shapes your impl (an API shape, a default value, a precedence rule), publish a question instead of guessing:

1. Write the question to `.swarm/questions/leaf-NN-Q<n>.md` with this shape:

   ```markdown
   ---
   leaf_id: leaf-NN
   question_id: Q<n>
   status: open
   ---

   ## Question

   <one paragraph stating what is unspecified and why it matters for your impl>

   ## Best-guess inference (if parent does not answer)

   <the value you will proceed with if no answer arrives>
   ```

2. Proceed with your best-guess inference and record it in your ASSUMPTIONS file with the line:

   ```
   - **<thing>**: <inferred value> — source: best-guess, question leaf-NN-Q<n>, unanswered: true
   ```

3. The parent may answer mid-run by writing `.swarm/answers/leaf-NN-Q<n>.md`:

   ```markdown
   ---
   leaf_id: leaf-NN
   question_id: Q<n>
   ---

   decision: <value>

   ## Rationale

   <one paragraph>
   ```

   If the answer arrives **before** you finalize, replace your assumption entry's `unanswered: true` with `unanswered: false` and adjust your impl to match the decision.

4. **You may not delete a question file you wrote** — it is part of the audit trail. Status flips happen by the parent writing an answer.

If the question is not resolved by admission time, `/manager-mode` Phase 6.5 gate G3 blocks: either parent must answer or you must keep the `unanswered: true` tag (which makes the inference explicit and reviewable).

## Contract-proposal protocol (when a parent-owned file must change)

If satisfying your brief requires a change to a parent-owned file (a type contract field, a fixture, a config), do **not** edit it. G1 will reject your admission. Instead:

1. Write `.swarm/proposals/leaf-NN.md`:

   ```markdown
   ---
   leaf_id: leaf-NN
   target_file: <path to parent-owned file>
   status: pending
   ---

   ## Proposed change

   <unified diff or precise description of the addition/edit>

   ## Why this is required

   <one paragraph citing brief spec_lines + what fails without the change>

   ## Fallback if rejected

   <how you will proceed — usually "re-spawn with revised brief">
   ```

2. Continue working on the parts of your impl that do not depend on the proposed change. The dependent parts stay incomplete; this is intentional — the test referencing the missing piece will stay RED and the parent will see that on admission attempt.

3. The parent will set status to `accepted` (after applying the diff to the target file), `rejected` (you re-plan), or `superseded` (a related leaf already covered it).

4. `/manager-mode` Phase 6.5 gate G4 blocks any leaf whose proposal is still `pending` at admission time, or whose proposal is marked `accepted` but the target file does not actually contain the change.

Never copy the parent-owned file into your impl as a workaround. Duplication is silent drift; the proposal protocol is how you make the need visible.
```

---

## What `/manager-mode` Phase 3 (`check_invariants.py`) checks per brief

| Field | Check |
|---|---|
| `leaf_id` | Unique across briefs in this decomposition. |
| `spec_file` | Exists, is in `spec_dir`. |
| `spec_lines` | Range is concrete (two integers), not "TBD" / "see above" / empty. |
| `test_file`, `impl_file` | One singular each (required). Plural `test_files` / `impl_files` may add more. Combined set not in any same-wave sibling brief. Impl paths not in parent-owned globs. Test paths not in parent-owned globs UNLESS `test_owned_by: parent`. |
| `contract_imports` | All symbols resolve in the locked type contract file. |
| `do_not_edit` | Includes every same-wave sibling's leaf-owned files; includes parent-owned globs. (Sibling test files only required here when `test_owned_by` is `leaf`.) |
| `test_owned_by` (optional) | `parent` or `leaf`. Default `leaf`. |
| `wave` (optional) | Integer ≥ 1. Default 1. Cross-wave leaves are sequenced, not parallel. |
| `impl_line_budget`, `test_assertion_budget` | Set, ≤ project max from `.claude-swarm.toml`. |
| `codebase_preconditions` (optional) | Each `verify:` command exits 0. If task prose contains claim-words ("already", "in place", "exists as of", "previously added") without backing preconditions, Phase 3.1 heuristic-warns. |
| `escalation_triggers` (optional) | Each `detect:` command (if present) is well-formed shell. Runtime check is Phase 6.5 G6. |
| Task prose | No ambiguous verbs from the configured list. |
| Task fenced code | Total non-blank lines across all fenced code blocks ≤ `max_brief_code_lines` (default 10). Stub signatures + mirror-pointer snippets allowed; full impl bodies blocked. Forces parent to encode shape, not authorship. |

A brief that fails any of these checks blocks the entire decomposition. The parent restructures and re-emits before any leaf is spawned.

---

## Why this template

The brief is the contract between parent and leaf. If the parent encodes the slice correctly here, the leaf has no surface on which to make a **design** decision **but retains full authorship of the body.** Encoding *shape* — spec_lines refs, contract_imports, stub signatures, mirror-pointers, invariants — removes ambiguity without removing authorship. Encoding the *body* — pasting a ready-to-run implementation — removes authorship along with ambiguity, which collapses the parallelism payoff: parent absorbs leaf work, leaf becomes a copy-paste courier, the cascade pays the cost of decomposition for none of the leverage. If the parent encodes incorrectly (ambiguity OR over-specification), the audit catches it before any leaf spawns. Both failure modes (toes-stepping, design-leak) reduce to malformed briefs; sizing is the third axis the budgets enforce.
