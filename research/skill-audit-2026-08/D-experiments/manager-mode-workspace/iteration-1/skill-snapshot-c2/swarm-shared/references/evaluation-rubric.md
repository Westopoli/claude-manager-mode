# Evaluation rubric for claude-manager-mode skills

This file records the **actual success criteria** the user cares about so future iterations don't drift into measuring the wrong things. The skill-creator's stock dashboard (pass-rate / time / tokens) is **not the metric**. It is a sanity check, not a verdict.

## What "performing well" means

The cascade exists because a single agent attempting a large plan loses resolution at the leaf level and silently drifts from the source-of-truth design doc (strategy doc). The skill performs well when it **prevents the four failure modes below at scale**.

### Failure modes the cascade must prevent

1. **Solo-implementation.** Parent agent receives "implement X" and starts editing source files itself instead of decomposing. Most common trigger: the invocation is phrased as an implementation request rather than a decomposition request, and the skill fails to reframe it.
2. **Plan drift from strategy doc.** Spec / decomposition silently disagrees with the strategy doc and the planning agent self-certifies "no conflict" without producing evidence. The skill must force a line-by-line comparison, not accept self-certification.
3. **Per-leaf resolution loss.** Leaf scope grows past what one agent can handle in one context window. Small coding mistakes inside an overstretched leaf cascade into the next leaf's input. Bite-size = the metric.
4. **Cascade-mistake leak-through.** Across N sequential admissions, a single silent regression slips through and propagates. The post-review protocol must catch it on the admission where it appears, not three admissions later.

### What "good performance" looks like

| Pass | Fail |
|---|---|
| Skill catches the seeded fault even when N=15 leaves and the fault is buried | Skill catches the fault at N=3 but loses it at N=15 |
| Skill forces parent to produce briefs before any src edit | Parent edits src files directly |
| Skill makes parent diff spec against strategy doc line-by-line and report contradictions | Parent self-certifies "spec matches strategy doc" with no evidence |
| Skill detects mid-cascade regression and forces revert | Skill waves through "umbrella still looks fine overall" |

## What "good performance" is NOT

- Token efficiency. Cascade adds ceremony on purpose. +20% tokens for prevented disaster = trade always worth taking.
- Wall-clock speed. A mis-decomposition can cost a half-day of recovery. A skill that adds 30s per decision to prevent that is free.
- Pass-rate on tiny toy fixtures. 3-leaf seeded-fault evals measure detection-when-told-to-look, not detection-at-scale. They are necessary but not sufficient.

## Required eval shape

Future iterations must include at least one eval in **each** of these categories. Stock pass-rate evals on small inputs are allowed but cannot stand alone.

### A. Scale-resolution (`/manager-mode` Phase 3 audit)

- Brief set size **≥ 15 leaves**, not 3.
- Faults seeded **subtly and deep**: overlap on a file whose name is one character different from a sibling; strategy-doc drift in a single brief whose `contract_imports` cite a type that doesn't exist in `type_contract_path`; sizing violation in the budgets, not in obvious prose.
- With_skill must catch all seeded faults. Baseline likely loses ≥1 as N grows.

### B. Solo-implementation prevention (`/manager-mode` Phase 2)

- Subagent given task **"implement feature X per `specs/X.md`"** — phrased as an implementation request, not as a decomposition request.
- With_skill (skill auto-triggers on "implement" + presence of spec): produces brief set, does **zero** edits to `src/`.
- Baseline: likely opens `src/` and starts writing the impl directly.
- Measure: count of `src/` writes during the run. Pass = 0.

### C. Bible/strategy-doc drift detection (`/manager-mode` Phase 1 Bible Compliance footer)

- `docs/strategy.md` says one thing (e.g., "all aggregation in SQL").
- `specs/wave-N.md` violates it (e.g., "use Python pandas for the aggregator").
- With_skill must **report the contradiction with both quotes side-by-side** and halt at spec-gate.
- Baseline likely produces "spec looks compliant" without quoting either doc — the failure mode this skill exists to prevent.

### D. Cascade-mistake leak-through (`/manager-mode` Phase 6 admission loop)

- 5 sequential admission candidates in one prompt, each with DIFF + UMBRELLA_BEFORE + UMBRELLA_AFTER.
- Candidate 3 introduces a silent regression: umbrella passes drop from prior count. Candidates 1, 2, 4, 5 are clean improvements.
- With_skill must REVERT exactly candidate 3 and ADMIT the other four.
- Baseline likely waves candidate 3 through ("4 of 5 passing, looks fine") or rejects clean admissions (eval-3 from iter-1).

## Grading

For each eval, the grader records:
- **Verdict correctness** — did the skill produce the right top-line decision?
- **Evidence quality** — did it cite the right artifact (file path, line, brief id, quote from strategy doc)? Self-certification with no evidence = fail even if verdict is right.
- **Scale fidelity** — at N=15 does it still cite the right leaf, or does it generalize ("some leaves look risky")?

Verdict-only grading is allowed for iter-1 sanity checks. From iter-2 onward, evidence-quality is required.

## Why this rubric, not the skill-creator default

skill-creator's default rubric is calibrated for skills that produce a deliverable (a docx, a chart, a refactor). Pass = artifact correct. The cascade skill produces a **decision under uncertainty about a multi-agent build**. Its job is to prevent a class of mistakes that only manifest at scale. Measuring it on 3-leaf toys against a token budget is like measuring a fire-suppression system on a kitchen fire — passes the test, doesn't prove it works on the warehouse.
