# claude-manager-mode config

Each project that uses the cascade places a `.claude-swarm.toml` at its project root. `/manager-mode` reads it at Phase 0 preflight. Missing file is fine — defaults apply.

## Schema

```toml
# Paths — all relative to project root unless noted

spec_dir          = "specs/"
briefs_dir        = ".swarm/<cascade-slug>/briefs/"  # <cascade-slug> auto-derives from
                     # the spec's <name> (Phase 0.1/0.2), normalized to lowercase
                     # hyphen-case. Override explicitly to force a flat/shared dir.
questions_dir     = ".swarm/questions/"   # leaves publish here, parent reads
answers_dir       = ".swarm/answers/"     # parent publishes here, leaves consume
proposals_dir     = ".swarm/proposals/"   # leaves propose parent-owned-file changes
type_contract_path = "src/<pkg>/types.py"

# Test + dependency-map commands. The skill shells out exactly as written.

umbrella_test_cmd = "pytest tests/umbrella.py"
# Optional: behavioral integration test run by /manager-mode Phase 7.1 after all leaves admit.
# Distinct from umbrella_test_cmd (which is per-leaf-isolation). Catches the
# failure mode where every leaf's umbrella was a source-grep pattern but the
# integrated behavior is still broken.
apex_test_cmd     = ""
graphify_cmd      = ""                   # empty string → fall back to import-graph heuristic

# Optional: paths excluded from G5 wave-snapshot integrity check.
# Defaults below. Add project-specific generated dirs as needed.
snapshot_ignore   = [
  ".git/**", ".swarm/**", "__pycache__/**",
  "node_modules/**", ".venv/**", "*.pyc",
]

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

## Defaults

If `.claude-swarm.toml` is missing, the skill uses every default above. `type_contract_path` has no sensible global default — the skill asks the user once and writes a `.claude-swarm.toml` with the answer.

## Precedence

1. `.claude-swarm.toml` at project root.
2. Built-in defaults.

Environment variables can override individual keys for one-off runs: `CLAUDE_SWARM_SPEC_DIR=alt-specs/ /manager-mode`.

## Why a config file rather than CLI flags

The cascade is a workflow, not a one-shot script. A given project always slices the same way; encoding the parameters once means the slash command stays short and the audit results stay reproducible across sessions.
