# Track D2 — experiment design (designed, NOT executed in this session)

Execution is gated on `00-DECISIONS.md` approval (per the plan). This document specifies exactly what would run, so approval is a yes/no on a concrete spec, not an open-ended "run some experiments."

## Target and harness

Reuse `experiments/scaling-test/target-repo/` (Python stdlib, pytest, `SPEC.md` with numbered ACs, seeded-fault grading already proven in `experiments/scaling-test/REPORT.md` Phase A/B: builders independently caught 2/2 seeded contradictions and 1/1 overload case with zero silent slip-through, verified by direct pytest execution and an independent auditor). Do not build a new harness — extend this one.

New in this design: every run is driven through `worktree_ops.py` (Track A), not the pre-worktree sandbox mechanism Phase A/B used, and recorded through `mine_transcripts.py` (Track C) rather than the manual token accounting Phase A/B used. This makes each run's cost measurement automatic and consistent with the rest of this audit, and doubles as further Track A validation under real (not fixture) load.

## Matrix — rows are `needs-experiment` items from `knob-map.md`, in priority order

### Row 1 (highest priority) — K2/K3: writer and auditor model

**Question:** does Opus earn its ~1.5–1.8× fresh-token / up to 3× output-token cost (C-tokens/QUESTIONS.md Q7) in defect-catching quality, on the *same* task?

**Design:** one shard, 3 leaves, held constant (same briefs, same spec, same seeded faults as Phase A/B or a fresh equivalent set — reuse to avoid re-validating the harness). Vary only the shard-test-writer's model across three runs: `claude-opus-5`, `claude-sonnet-4-6`, `claude-fable-5`. Same for a second matrix cell varying only the test-auditor's model, writer held at whichever model row 1 finds adequate.

**Success metrics:** seeded faults caught (binary, per fault) × tokens spent (from `mine_transcripts.py`, run against this session's own transcripts) × wall-clock × whether the resulting tests are behavioral or tautological (manual read, since this is exactly what Track B's judgment pass does — reuse that rubric, `B-test-audit/judgments/CATEGORY_VOCAB.md`).

**Sample size:** 3 models × 2 roles = 6 runs minimum; repeat each once (12 runs total) since a single run per cell can't distinguish model capability from run-to-run variance — this is the corpus's own confound (Q7) and the whole point of running it controlled this time.

### Row 2 — K9: shard size

**Question:** the leandrc49 shard-sizing A/B narrative (`Agora/runs/manager-mode-post-auditor/leandrc49__shard-sizing-ab-2026-08-18-19.md`, read by the B2 judgment agent) is real production A/B on this knob — use it as a prior, not a blind start.

**Design:** decompose a spec into 12 leaves (large enough that shard size matters). Run once at `max_leaves_per_shard = 6` (current default, 2 shards) and once at `max_leaves_per_shard = 3` (4 shards) and once at `max_leaves_per_shard = 12` (1 shard, writer holds everything). Same spec, same seeded faults, same model for writer/auditor across all three (control for row 1's finding).

**Success metrics:** findings count and category mix per shard size (does a smaller shard's writer/auditor context produce measurably different test quality, not just different token cost?); total tokens; whether the co-location rule (K12 — cross-referencing ACs must share a shard) gets violated at any shard count, which would show up as a Phase 1.5-style contradiction slipping through.

### Row 3 — K32: retry caps

**Question:** K36 found the corpus's audit→fix→re-audit loop empirically self-limits to exactly one re-audit pass in every observed cascade. Does that hold under an adversarial spec (deliberately ambiguous, more findings than a real spec would have), or does the uncapped loop actually run away?

**Design:** seed a spec with 3x the typical finding density (multiple tautological tests, one boundary-drop, one umbrella contradiction — pull from `CATEGORY_VOCAB.md`) in one shard. Run Phase 3.4 normally (no artificial cap) and count how many audit→fix→re-audit cycles actually occur before the shard clears.

**Success metrics:** cycle count (1 predicted from corpus; >2 would be a real finding worth capping); tokens per cycle; whether later cycles find genuinely new issues or just re-litigate the same one (materiality check, same rubric as Track B's judgment agents).

### Row 4 — K18: fat-file ceiling

**Question:** `playbook.md`'s own author flagged the 1000/1500/2500-line budget as "provisional pending validation beyond H2's tested 585-LOC ceiling" (`experiments/scaling-test/phaseH-ceiling-search/`).

**Design:** extend the existing H-phase ladder one rung past H3 (the highest previously tested) — H4 at budget 12,000, real target ~800–1000 LOC estimated from the H1→H3 utilization trend. Single leaf, single file, same target-repo pattern.

**Success metrics:** same as H1–H3 (actual LOC vs budget, test count, correction-cycle count) plus, new to this row, an explicit token-scaling check (H3's own report flagged this as unmeasured: "do not cite a token-scaling verdict for H3") — record fresh/cache tokens per LOC written and check whether cost grows linearly, faster, or slower than H1–H3's trend.

## Recording

Each run → `D-experiments/runs/<row>-<cell>-<n>/` containing: `run_manifest.json` (row, cell, model(s), config values, spec+brief paths, seeded faults list), the cascade's own `.swarm/<slug>/git-ops.log` (Track A's audit trail, copied in), and a `mine_transcripts.py` slice (agents whose session/timestamp falls inside this run's window). No hand-transcription of token counts — always through the miner, so Track C's dedupe fix applies uniformly.

## What is NOT in this design

- No row for K4/K5 (leaf/fixer model) — corpus already answered these (K4/K5 in knob-map.md), no controlled variation needed.
- No row for K13 (hardcore's 2-auditor+adjudicator) — zero hardcore cascades observed in the corpus; before spending tokens on a controlled run, first re-check whether any exist in repos not yet scanned (a cheap corpus-extension step, not an experiment).
- No row for K35 (audit-brief dialect) — B4 synthesis may answer this from the existing corpus (14 audits already split path-list vs inlined); only promote to an experiment if B4 finds it inconclusive.

## Gate to execute

Per the plan: run only after B5 (misconceptions) and C3 (decision rule) are both filed and `00-DECISIONS.md` records explicit approval of this document, row by row — a partial approval (e.g. "run row 1 only") is a valid outcome.
