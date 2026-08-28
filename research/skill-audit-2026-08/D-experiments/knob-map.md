# Track D1 — knob map

Every tunable surface in `/manager-mode`, current value, evidence for that value, and status: `answered` (corpus/E2E settles it), `needs-experiment` (knob never varied in a controlled way, or varies confounded with other factors), or `irrelevant` (not a real lever, or superseded by Track A's redesign).

| # | Knob | Current value | Evidence | Status |
|---|---|---|---|---|
| K1 | Overlord model | Opus 5, user must `/model opus` | `SKILL.md:30` | answered — host-chat model is a user choice, not a spawn param; not experimentable the same way |
| K2 | Shard-test-writer model | Opus 5, `model: "opus"` | `SKILL.md:31,287` | needs-experiment — Q7 (C-tokens/QUESTIONS.md) shows real Opus/Sonnet cost gap (1.8×) but confounded by project/task, not controlled |
| K3 | Test-quality auditor model | Opus 5, `model: "opus"` | `SKILL.md:35,348` | needs-experiment — same as K2 (1.5× cost gap, confounded); auditor is also the single heaviest payload (K34), so this is the highest-value cell in the matrix |
| K4 | Leaf implementer model | Sonnet 4.6, forced | `SKILL.md:32,424` | answered — B judgment agents found no evidence leaf quality is model-bound in this corpus; leaves are the cheapest role by design |
| K5 | Test-fixer model | Sonnet 4.6 | `SKILL.md:34,412` | answered — bounded repair work, corpus shows small n but no quality complaint |
| K6 | Drafting sub-agent model (dep-map/consolidation/ambiguity) | **Fixed this session**: Sonnet 4.6, explicit (`model: "claude-sonnet-4-6"`) | `SKILL.md:37` (was previously unpinned — inherited overlord's model, a silent Opus leak on an Opus-hosted cascade) | answered — closed as a bug, not a knob to tune |
| K7 | Whole-cascade model floor (manager-mode-lite) | **Removed this session** — superseded by this Track C/D work | `bf7a406` | irrelevant — the question lite existed to answer is now this experiment |
| K8 | Max leaves per wave | 16, hard refuse | `SKILL.md:243-246,812` (line numbers approximate post-edit; grep `16-leaf cap`) | answered — sized for worktree isolation + brief-writing load, not contested by corpus |
| K9 | Max leaves per shard | `max_leaves_per_shard = 6` | `config.md`, `check_invariants.py DEFAULTS` | needs-experiment — the leandrc49 shard-sizing A/B narrative (`runs/manager-mode-post-auditor/leandrc49__shard-sizing-ab-*.md`) is real A/B data on this exact knob; B3 judgment agent extracting it now |
| K10 | Shard count formula | `ceil(leaves/6)` | `SKILL.md` Shards section | derived from K9 |
| K11 | Volume override (>2000-line target = >1 shard-slot) | judgment call | `SKILL.md` Shards section | answered — qualitative rule, not numeric-tunable |
| K12 | Co-location rule (cross-referencing ACs → same shard) | judgment call | `SKILL.md` Shards section | answered — caught a real 3-unit-conflict in one cascade per SKILL.md's own citation |
| K13 | Number of auditors (1 vs 2+adjudicator) | 1 base / hardcore = 2+adjudicator | `manager-mode-hardcore/SKILL.md` | needs-experiment — hardcore triples the heaviest payload; no corpus data on whether the 2nd auditor catches anything the 1st missed (B4 synthesis to check for hardcore cascades in the corpus — currently none observed) |
| K14 | Gate strictness `--strict` | off base / on hardcore | `run_gates.py`, `hardcore:18-20` | answered — promotes G8-mutation/G9/G10/BOUNDARIES advisory→block; mechanism understood, not a quality question |
| K15 | `max_impl_lines` | **Fixed this session**: 1000 everywhere (was 200 in config.md, disagreeing with code DEFAULTS/toml-example/playbook's 1000) | `check_invariants.py DEFAULTS`, `config.md` | answered — was a doc bug, not a real knob disagreement |
| K16 | `max_test_assertions` | 20 | `config.md` | answered — no corpus evidence it binds in practice |
| K17 | `max_brief_code_lines` | 10 | `SKILL.md`, `brief-template.md` | answered |
| K18 | Fat-file target/cap | 1000–1500 target, 2500 hard flag | `SKILL.md` 2.4 | needs-experiment — `playbook.md:67` notes "all three numbers provisional pending validation beyond H2's tested 585-LOC ceiling" — this is the skill's own author flagging it unresolved |
| K19 | `max_cyclomatic`/`max_nesting` (G9) | 10 / 3 | `.toml.example`, `complexity_gate.py` | answered — calibrated on 72 real functions (SKILL.md 6.5 bullet); nesting half explicitly noted as untested (never reached 3 in the calibration set) |
| K20 | G10 growth bands | 1.5 / 3.0 / 6.0 | `.toml.example [scale]` | answered — derived analytically (geometric midpoints between complexity classes), not empirically tuned |
| K21 | `--max-mutants` (G8) | 8 | `test_quality_gate.py` | answered — runtime cost knob, not a token knob |
| K22 | G8 applicability (2+ impl_files only) | no-ops on single-file leaves | `SKILL.md` 6.5 bullet | answered — Phase F (`experiments/scaling-test`) showed all 3 single-file rungs SKIP; consolidation-toward-fewer-larger-leaves systematically disables this gate — a real design tension, not unresolved data |
| K23 | `subagent_type` per leaf | `general-purpose` default; `cavecrew-builder` opt-in | `SKILL.md` 4.3 | answered — tool-profile axis, independent of model (K4) |
| K24 | `worktree_link` (was `sandbox_link`) | `node_modules, .venv, venv, vendor, target` | `config.md` | answered — Track A dry-run (DRYRUN.md finding 3) proved the mechanism; not a quality knob |
| K25 | `footprint_ignore` (was `snapshot_ignore`) | `.git, .swarm, caches, coverage` | `config.md` | answered — same |
| K26 | `graphify_cmd` | `""` default | `config.md` | answered — avoids a delegated investigator spawn when set; no corpus data on token savings |
| K27 | `apex_test_cmd` | `""` default | `config.md` | answered |
| K28 | `extra_spec_gate_cmds` | `[]` default | `config.md` | answered |
| K29 | Delegated drafting passes (exactly 3 points: 2.1, 2.2, 1.A) | fixed set | `SKILL.md` "Delegated drafting passes" | answered — bounded by design |
| K30 | Parallelism (whole wave dispatched together) | yes | `SKILL.md` Phase 4 | answered — `experiments/scaling-test/REPORT.md` Phase A/B: "sharding cost zero wall-clock" |
| K31 | Concurrent waves | up to 4×16 leaves | `SKILL.md` Shards "Going past one wave" | answered — architectural ceiling, not empirically tested at scale (no corpus cascade has run concurrent waves) |
| K32 | **Retry/iteration caps** | **none exist anywhere** — Phase 3 fix-loop, 3.4 audit→fix→re-audit, hardcore's 2-auditor re-run are all uncapped | plan Track C exploration, confirmed by grep: no `max_retries`/`max_iterations` key in config.md or `.toml.example` | needs-experiment — this is the single largest unexposed knob; C-tokens Q6 found no manager-mode-role retry loop in the *current* corpus (may mean it doesn't happen, or the description-based detector misses it — flagged as a real detection-method limitation) |
| K33 | `effortLevel` (Claude Code session-level) | inherited from host; no per-spawn override surface on `general-purpose` | research doc §3 | needs-experiment — real, unexploited lever per the original research; Track A/B/C work this session ran at whatever the host session's effort was, unmeasured as a variable |
| K34 | Audit-brief pre-filtering | **explicitly forbidden** (`SKILL.md:353`-area, "compilation step, not a judgment step") | plan Track A background | answered as a design decision, but its *cost* is the single biggest lever — B judgment agents' brief-dialect finding (path-list vs inlined, 14 vs 2600+ lines) is real corpus variation on a *related* axis (how the un-trimmed content is packaged, not whether it's trimmed) |

## New knob found this session (not in the original K1–K34 list)

| # | Knob | Current value | Evidence | Status |
|---|---|---|---|---|
| K35 | Audit-brief packaging dialect (path-list vs fully-inlined) | Both occur in the wild: 14–21 lines (driver, verify, foundation) vs 1830–2808 lines (qa-profile, director) | `B-test-audit/COVERAGE.md` "Audits by brief dialect" table | needs-experiment (partially answered by B4 synthesis — see `B-test-audit/SYNTHESIS.md` once written; the confound is severe: dialect correlates with skill version and possibly with cascade complexity, not randomized) |
| K36 | Number of judgment/audit passes before spawn (1 vs 2 re-audit rounds) | Every audited cascade in the corpus shows exactly one `## Re-audit` pass after the initial audit — SKILL.md doesn't cap this, it's emergent | `B-test-audit/COVERAGE.md`, `out/audits.csv` `passes` column | answered — corpus consistently shows 2 passes (audit + one re-audit-to-clear), never 3+; the audit→fix→re-audit loop in practice self-terminates after one cycle |

## Priority for Track D2 experiment design

Ranked by (plausible token/quality impact) × (how confounded the corpus evidence is):

1. **K3/K2 — auditor and writer model (Opus vs Sonnet vs Fable)**, same shard, same task. This is the plan's headline question and the corpus data (Q7) is real but confounded by project selection.
2. **K9 — shard size**, using the leandrc49 shard-sizing A/B narrative as a *prior*, then a controlled rerun at 2–3 sizes on the same target repo.
3. **K32 — retry caps**, specifically whether an uncapped audit→fix→re-audit loop ever actually runs more than once in practice (K36 suggests it self-limits) — cheap to check against more corpus data before spending an experiment on it.
4. **K18 — fat-file ceiling**, already flagged unresolved by the skill's own author; low cost to extend H-phase-style experiments one more rung.
