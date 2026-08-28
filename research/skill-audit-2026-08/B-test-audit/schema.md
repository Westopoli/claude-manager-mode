# Ledger schema — `ledgers/<repo>/<cascade>.json`

Produced by `extract_ledgers.py`. Pure extraction; every value is a quote, a count, or a path. No judgment.

| key | content |
|---|---|
| `repo`, `cascade`, `cascade_dir`, `repo_root`, `extracted_at` | provenance. `cascade == "_flat"` = legacy layout (`.swarm/briefs/` at root). |
| `summary` | counts used by `coverage.py` (leaves, waves, shards, spec_acs, acs_with_tests, acs_without_tests, test_files[_found], test_fns, assertions, audits, audit_passes, findings, findings_by_sev, audit_dialects, audit_kinds, brief_dialects, boundaries_rows, gates_files, gate_waivers, gate_fail_rows, log_rows, admitted, reverted, delta_zero_rows, has_skill_observations) |
| `specs{spec_file}` | `exists`, `acs{AC-N: {text ≤1200 chars, line_start, line_end, section}}`. ACs found under `## Acceptance criteria`; if the spec has no such heading the whole document is scanned for `AC-N` / `C2-AC-N` labels. **Older plan-doc specs have no AC labels → `acs` empty**; use the brief's `spec_lines` instead. |
| `briefs{leaf}` | frontmatter: `spec_file, spec_lines, wave, shard, test_files[], impl_files[], test_owned_by, impl_line_budget, test_assertion_budget, has_assumptions, post_review_regression` |
| `tests{path}` | `exists, lines, spec_link, spec_acs[]` (from the `# spec:` header), `tests[] {name, line, assertions (py only), acs_mentioned[]}`, `assertions` (py: AST `assert` + `pytest.raises`; js: `expect(`/`assert.` count), `kinds[]` ⊂ {source-grep, ast-structural, scale-ratio, uses-mocks}, `leaf`. Falls back to `backups/` or `pending/` copies when the live file is gone. |
| `impls{path}` | `exists, lines, leaf` — live tree today, **not** the state at admission. |
| `audits[]` | per audit file: `path, kind` ∈ {pre-spawn (TEST-AUDIT.md), post-admission (auditor.md/POST-MORTEM.md/batch-*), legacy-wave-audit (wave-N.AUDIT.md)}, `dialect` ∈ {table, check-sections, stage-legacy, prose}, `brief_dialect` ∈ {path-list (<200 lines), inlined, none}, `brief_lines, lines, declared_counts{red,yellow,green}` (the auditor's own summary — **authoritative**), `mentions_test_design_ref, ran_tests, passes[] {label, verdict, red, yellow, green, chars, findings[]}`. `passes[0]` is the original audit; later passes are `## Re-audit`/`## Follow-up` sections appended to the same file. |
| `audits[].passes[].findings[]` | `id, severity, line, kind` ∈ {table, heading, inline, bullet}, `text ≤600`, `test_files[], test_fns[], acs[]`. Deduped by id within a pass. Parsed counts can differ from `declared_counts` where 🟢 notes are un-numbered prose; treat parsed findings as the *join surface*, declared counts as the *tally*. |
| `boundaries[]` | `path, rows, spec_silent_rows` (`—` in "spec says"), `escalated_rows, not_covered_rows` |
| `gates{leaf}` | `verdict, gates{name: {result, evidence}}, waiver` (overlord G5 waiver paragraph present), `fails[]` |
| `log_rows[]` | `wave, shard, leaf, files, delta, timestamp, status` from `post-review-log.md` (per-cascade file, or root file filtered by shard==slug, else by test-file membership) |
| `backups{leaf}` | `files, absent_markers` (`.ABSENT` = file did not exist pre-admission) |
| `ac_index{AC}` | join: `spec, text, line_start, line_end, section, tests[] (paths claiming it via header or in-body mention), findings[] {audit, pass, id, severity}, leaves[]` |
| `outcomes{leaf}` | `log_rows[], admitted, reverted, gates_verdict, gate_fails[], gate_waiver, backup, impl_exists` |
| `skill_observations{path}` | verbatim `## Skill observation…` sections from SWEEP/REPORT/STATE |

## Known limits

- **TODO, confirmed by B3 judgment pass**: `ac_index[AC].tests` only links via the test's `# spec:` header or an audit-finding citation — a correctly-tested AC never flagged by any audit shows as `tests: []`. Deep-check found 13/18 such flags in Agora cascades were false-negatives (real test exists, just uncited). Fix: also scan every test file's body for `AC-\d+` mentions in assertion messages/docstrings/comments, not just the header, and union with header-linked tests. Not fixed this session — `SYNTHESIS.md` corrects the headline stat instead of silently trusting it.

- `impls` reflect the live tree; several impl files are owned by multiple cascades across waves (Agora `scripts/next.py` ×4). Admission-time content is only recoverable from git history (`git log --follow -- <path>` in the repo) — the judgment pass must do that explicitly when it matters.
- Legacy repos keep audits at `.swarm/audits/wave-N/<batch>/` without a slug; they are attached to a cascade when the audit text names one of its test files. Unattached audits are not in any ledger (list them with `find .swarm/audits -name '*.md'` vs ledger paths).
- JS test assertion counts are file-level regex counts, not per test.
- The `era` column in `coverage.py` is derived from artefacts present, not from the skill commit that ran; cross-check with `C-tokens/out/agents.csv` `skill_commit_guess` when the date matters.
