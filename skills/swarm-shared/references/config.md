# claude-manager-mode config

Each project that uses the cascade places a `.claude-swarm.toml` at its project root. `/manager-mode` reads it at Phase 0 preflight. Missing file is fine — defaults apply.

## Schema

```toml
# Paths — all relative to project root unless noted

spec_dir          = "specs/"
briefs_dir        = ".swarm/<cascade-slug>/briefs/"  # <cascade-slug> auto-derives from
                     # the spec's <name> (Phase 0.1/0.2), normalized to lowercase
                     # hyphen-case. Override explicitly to force a flat/shared dir.
questions_dir     = ".swarm/<cascade-slug>/questions/"  # leaves publish, parent reads
answers_dir       = ".swarm/<cascade-slug>/answers/"    # parent publishes, leaves consume
proposals_dir     = ".swarm/<cascade-slug>/proposals/"  # leaf -> parent-owned-file changes
type_contract_path = "src/<pkg>/types.py"

# Test + dependency-map commands. The skill shells out exactly as written.

umbrella_test_cmd = "pytest tests/umbrella.py"
# Optional: behavioral integration test run by /manager-mode Phase 7.1 after all leaves admit.
# Distinct from umbrella_test_cmd (which is per-leaf-isolation). Catches the
# failure mode where every leaf's umbrella was a source-grep pattern but the
# integrated behavior is still broken.
apex_test_cmd     = ""
graphify_cmd      = ""                   # empty string → fall back to import-graph heuristic

# Optional: paths excluded from the Phase 4.0 wave-baseline snapshot (and so
# from G5), and skipped when a leaf sandbox is built. Defaults below. Add
# project-specific generated dirs as needed.
snapshot_ignore   = [
  ".git/**", ".swarm/**", "__pycache__/**",
  "node_modules/**", ".venv/**", "*.pyc",
  # Test-runner scratch. The leaf runs its own test command inside the
  # sandbox, so these appear there and nowhere else — without them every
  # Python leaf trips G5 on caches its own passing test wrote.
  ".pytest_cache/**", ".mypy_cache/**", ".ruff_cache/**",
  ".coverage", "htmlcov/**", "*.egg-info/**",
]

# Optional: dependency trees a leaf sandbox SYMLINKS instead of copying
# (Phase 4.1). These are usually the bulk of a repo by size and are never
# leaf-owned, so copying them per leaf is pure cost — but omitting them
# entirely breaks the leaf's own test command, which is the whole point of
# the sandbox. Symlinking is the only option that satisfies both.
sandbox_link      = ["node_modules", ".venv", "venv", "vendor", "target"]

# Files the parent owns. Globs. No leaf may name a file matching these.

parent_owned = [
  "src/**/types.py",
  "tests/conftest.py",
  "tests/umbrella*.py",
  "tests/integration/**",
]

[invariants]
max_impl_lines        = 200
max_test_assertions   = 20

# Words that, if found in a brief's task prose, indicate a design decision
# is being delegated to the leaf. /manager-mode Phase 3 fails the brief.
ambiguous_verbs = [
  "decide", "choose", "design", "determine",
  "figure out", "resolve", "as appropriate",
  "use your judgment", "pick", "select an approach",
]

[scale]
# G10 growth bands (Phase 6.5), as the ratio cost(2N)/cost(N). Each sits at
# the geometric midpoint between the complexity classes it separates, so a
# class jump fails while ordinary variation does not. `linear_ish`
# deliberately admits both O(n) (2.0) and O(n log n) (2.2) — they sit 10%
# apart under doubling, which no measurement resolves reliably.
# Recipe and rationale: references/test-design.md.
sublinear    = 1.5   # O(1)=1.0, O(log n)=1.10 pass; O(n)=2.0 fails
linear_ish   = 3.0   # O(n), O(n log n) pass; O(n^2)=4.0 fails
quadratic_ok = 6.0   # O(n^2) passes; O(n^3)=8.0 fails

[gates]
# Optional project-specific gates run by /manager-mode Phase 1.A after the spec draft is approved.
# Each entry is a shell command. Non-zero exit blocks. Empty list = no extra gates.
# $SPEC_FILE is exported by the skill before each command.
extra_spec_gate_cmds = []

# Example: require spec to contain a compliance-report section.
# extra_spec_gate_cmds = [
#   "grep -q '^## Compliance Report' \"$SPEC_FILE\"",
# ]
```

### Cascade-slug derivation for `briefs_dir`

If `briefs_dir` is not explicitly set in `.claude-swarm.toml`, `/manager-mode`
derives it as `.swarm/<cascade-slug>/briefs/`, where `<cascade-slug>` is the
spec's `<name>` (the `<spec_dir>/<name>.md` filename stem from Phase 0.2),
lowercased, with runs of whitespace/underscore collapsed to a single hyphen
and any character outside `[a-z0-9-]` stripped. If no spec name is yet known
(bootstrap case — spec doesn't exist on disk yet), Phase 0.1 asks the user
for a short slug directly, same "do not guess" discipline as its other
required fields.

An explicit `briefs_dir` in the config always wins — this derivation only
fills the default. Existing projects with a bare `.swarm/briefs/` already
set keep working unchanged; nothing about this is a breaking migration.

### The full per-cascade layout

The slug scopes every working file a cascade produces, not just its briefs.
One cascade, one directory:

```
.swarm/
  post-review-log.md              # shared across cascades — NOT slug-scoped
  <cascade-slug>/
    PLAN-CHECK.md                 # Phase 1.5
    briefs/          leaf-NN.md, leaf-NN.ASSUMPTIONS.md
    sandbox/         leaf-NN/<project tree>        # Phase 4.1
    pending/         [shard-<id>/]leaf-NN/<staged paths>
    backups/         leaf-NN/<pre-admission copies>
    audits/          wave-<N>/<shard-or-default>/...
                     wave-<N>/leaf-NN.GATES.md
    questions/       answers/       proposals/
    wave-<N>.snapshot.json
    wave-<N>.SWEEP.md
```

`post-review-log.md` deliberately stays at the `.swarm/` root: it is
append-only history across every cascade in the project and already carries a
`shard` column to disambiguate rows.

**Legacy flat layout still resolves.** `check_invariants.py`,
`test_quality_gate.py` and `scale_gate.py` look for the per-cascade shape
first and fall back to flat `.swarm/briefs/` + `.swarm/pending/<leaf>` when it
is absent, so a project that predates the slug keeps working. Each accepts
`--cascade <slug>`; the slug auto-detects when exactly one `.swarm/*/briefs/`
exists, and the scripts ask rather than guess when several do.

The mismatch this closes was real and silent: the docs described the
per-cascade layout while the scripts hardcoded the flat one, so G8/G9 found no
brief for a per-cascade run and reported the leaf as not-applicable instead of
failing.

## Defaults

If `.claude-swarm.toml` is missing, the skill uses every default above. `type_contract_path` has no sensible global default — the skill asks the user once and writes a `.claude-swarm.toml` with the answer.

## Precedence

1. `.claude-swarm.toml` at project root.
2. Built-in defaults.

Environment variables can override individual keys for one-off runs: `CLAUDE_SWARM_SPEC_DIR=alt-specs/ /manager-mode`.

## Why a config file rather than CLI flags

The cascade is a workflow, not a one-shot script. A given project always slices the same way; encoding the parameters once means the slash command stays short and the audit results stay reproducible across sessions.
