# Research: pre-code spec sizing for LLM sub-agent allocation

Research pass (single agent, web search), not independently fact-checked
line-by-line — treat citations as leads, not verified claims. Full
prompt/context: this file exists to ground Part 1's Consolidation pass
(2.2) rubric in `../overlord-allocation-redesign-DRAFT.md`.

## 1. Traditional sizing methods — what they measure, transferability

- **Function Point Analysis (FPA/IFPUG)**: counts external inputs/outputs,
  inquiries, internal/external data groupings, weighted by complexity
  tiers. Measures functional size of the data model/I-O surface, not
  logic complexity.
- **COSMIC FP**: decomposes each functional process into four movement
  types (Entry/Exit/Read/Write) across data groups. More rigorous,
  technology-agnostic; correlates with actual effort better than story
  points per multiple studies.
- **Use Case Points**: weights actors/use-cases by transaction-count
  tiers, plus technical/environmental adjustment factors.
- **Story points / planning poker**: relative, team-calibrated gut feel —
  meaningless outside the team that generated them.
- **T-shirt sizing**: same idea, coarser.

**Verdict**: all size data/transaction surface area, not decision-rule
density or branching logic — the thing that actually breaks LLM agents.
None were built to predict LLM difficulty; calibrated to human dev-hours
via historical regression. A spec with tiny I/O surface but deep layered
exception logic would score "small" under all of these while being
genuinely hard to implement correctly. None transfer directly — but
COSMIC's move (decompose into discrete elements counted from the spec
itself) is the right shape of technique, wrong axis.

## 2. Requirement-complexity heuristics

Established literature scores specs by: distinct functional requirements,
exception/alternate-flow branches per use case, cross-references/
dependencies between requirements, ambiguity-indicator words. Closer to
useful, but mostly used as a quality gate (is this requirement testable),
not an allocation signal — no widely adopted numeric split threshold.

## 3. LLM/agent-specific findings (2025-2026)

- Multi-agent orchestration research: returns to added agents go negative
  once a single agent's baseline accuracy is high; systems with >~10
  tool/integration touchpoints suffer 2-6x efficiency loss from context
  fragmentation — direct support for "external integrations" as a real
  splitting signal.
- "Runtime-Structured Task Decomposition" work: large gains from
  isolating failure domains so retries don't cascade — the splitting
  criterion that matters is blast radius of a wrong assumption, not code
  volume.
- Complexity-feedback code-gen research (2025): standard complexity
  metrics predict LLM Pass@1 failure, fed back iteratively — but this is
  post-hoc, measured on generated code, same chicken-and-egg problem
  this research exists to escape.

**No literature defines a pre-code, read-only spec-difficulty score for
LLM agents.** Genuine gap, not a missed existing answer.

## 4. Synthesis adopted in the draft

Score each candidate spec-section on four axes, countable by reading
alone: rule-cluster count, exception-branch count, external-integration
count, cross-cutting-concern count. One leaf when ≤1 cross-cutting
concern, ≤2-3 integrations, one shared failure domain. Split along the
cross-cutting-concern or integration boundary first when over — that's
where compositional bugs live. An incident-driven spec amendment counts
as an added cross-cutting concern on whatever it touches.

## Sources (unverified beyond the search snippet)

- [COSMIC Function Point sizes vs Story Points for predicting effort](https://cosmic-sizing.org/2017/11/14/cosmic-function-point-sizes-far-superior-story-points-predicting-effort/)
- [Function Point counting — compared with other approaches](https://www.scopemaster.com/blog/function-points/)
- [A Complexity measure based on Requirement Engineering Document](https://arxiv.org/abs/1006.2840)
- [Metrics for software requirements specification quality quantification](https://www.sciencedirect.com/science/article/abs/pii/S0045790621004043)
- [Runtime-Structured Task Decomposition for Agentic Coding Systems](https://arxiv.org/html/2605.15425)
- [Enhancing LLM-Based Code Generation with Complexity Metrics: A Feedback-Driven Approach](https://arxiv.org/abs/2505.23953)
- [The Market Shift: Why Multi-agent LLM Coordination Matters in 2026](https://sesamedisk.com/multi-agent-llm-coordination-2026/)
