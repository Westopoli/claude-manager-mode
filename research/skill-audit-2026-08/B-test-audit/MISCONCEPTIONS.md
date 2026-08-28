# B5 — Misconception risks when transferring findings into skill edits

Written before B4 synthesis is finalized, so the risks below are checked against, not derived from, the final numbers — the point is to have the guardrails in place before reading conclusions into the data.

## Survivorship

- `cascade-director` (Agora) has audits but no admitted impl (stopped after re-audit, before any leaf spawned) — it can only speak to pre-spawn audit *output*, never to "did the audit's absence-of-finding correlate with a clean admission." Any catch-rate denominator must exclude it or flag it separately.
- The pre-auditor narrative corpus (`runs/manager-mode-pre-auditor/`) was explicitly curated to keep only cascades whose artifacts survived to be found — a cascade with no surviving admission record (e.g. IsaiahsGame's "outcome not found in artifacts", noted in the corpus's own INDEX.md) is missing from the denominator entirely, which likely biases the *visible* corpus toward cascades that went well enough to leave a clean trail.

## Confounds

- **Era, model, and audit-brief dialect all move together.** Post-auditor-era cascades in this corpus also tend to use different (often newer) models and different brief-packaging styles than pre-auditor cascades. Any "the auditor caught X% more" claim must be checked against whether X% could instead be explained by model improvement alone — B3's judgment agents were asked to cite specific evidence, not aggregate percentages, specifically so this can be checked finding-by-finding rather than trusted as a summary statistic.
- **Findings on tests later rewritten by a test-fixer.** Count on the *original* test text at audit time, not the current live-repo test file — a finding that was correct when written can look "wrong" today only because the fix already landed. The extractor's `judgments/extracted-corpus.json` reads the *live* repo for materiality checks; where a finding predates a later unrelated rewrite of the same file, treat "verdict: already-moot" with suspicion — check whether it's moot because of *this* fix or an unrelated one.

## Spec drift

- Specs get amended mid-cascade (Agora's `PLAN-CHECK.md` files record explicit spec amendments from shard questions). A finding judged against "the spec" must be checked against the spec *as it read when the finding was filed*, not the current spec text — Agora's own git history can recover this where it matters; the extracted ledgers do not carry spec version.

## Format strata

- The 18 leandrc49-import cascades under `Agora/runs/leandrc49/.swarm/` use the **older** `wave-N.AUDIT.md` naming (post-admission audit, not pre-spawn `TEST-AUDIT.md`) — this is a structurally different mechanism (Phase 8 adversarial post-admission review, later removed from the skill per `test_no_post_admission_agent_review_exists` in `test_skill_contract.py`), not an earlier version of the *same* mechanism. Never pool its findings with `TEST-AUDIT.md` findings as if they measure the same thing; `extract_ledgers.py`'s `audit_kinds` field (`pre-spawn` vs `post-admission` vs `legacy-wave-audit`) exists specifically to keep this separable, and `coverage.py`'s era classifier uses it.

## The "+0" signal

- 38 of 41 rows in Agora's `post-review-log.md` show `+0 umbrella, acceptance green` — this does NOT mean the leaves did nothing. It means Agora's cascades are umbrella-first: the umbrella test for a given AC was often written and already passing (against a stub/earlier leaf) before the leaf that "completes" it landed, so the per-leaf umbrella delta undercounts real progress. Any "delta signal is dead" conclusion must be checked against this design pattern specifically, not read as a general finding about the skill.

## The extractor under-links tests to ACs — do not trust `ac_coverage.csv` zero-test counts at face value

`extract_ledgers.py`'s `ac_index` links a test to an AC only via the test's `# spec:` header or via an audit-finding citation. A correctly-tested AC that no audit ever flagged has no citation path in and shows as "zero tests." The B3 judgment agent deep-checked 18 such flags across the 5 Agora cascades by reading the live repo directly: **13/18 were false-negatives** (a real, correct test exists and was found by direct code inspection), 1/18 a genuine gap with correct impl anyway, 4/18 correctly not-applicable (no impl exists). **Zero were a real uncovered-rule violation.** Treat every "N ACs with zero tests" figure in `COVERAGE.md`/`ac_coverage.csv` as "not cited by an audit finding," not "untested," until the extractor is fixed to scan test bodies for AC mentions independent of findings (a mechanical TODO, not executed this session — see `schema.md`).

## What would falsify the headline pre-auditor-corpus finding

The B3 pre-auditor judgment agent found defects caught almost entirely by (a) the overlord's manual admission-time review and (b) a leaf's own TDD cycle discovering a *parent-authored* test was wrong — with zero pre-spawn catches (mechanically, since no pre-spawn auditor existed) and a real fraction (~1/6 of discrete defect events) that no gate — pre- or post-auditor era — currently covers (runtime UI-wiring bugs only found by a human). Before treating "the auditor mainly formalizes what leaf TDD already caught informally" as a conclusion: check whether the post-auditor corpus's pre-spawn findings *overlap* with defect categories the pre-auditor corpus shows leaves already catching via their own RED/GREEN cycle (in which case the auditor is moving detection earlier, which has real value in wasted-leaf-token terms, not in raw catch-rate terms) versus catching genuinely *new* categories leaf TDD structurally cannot see (which would be the stronger claim). B4 must draw this distinction explicitly, not conflate "caught earlier" with "caught more."
