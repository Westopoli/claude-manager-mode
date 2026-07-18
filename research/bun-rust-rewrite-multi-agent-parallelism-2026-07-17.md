# Research: Bun Zig→Rust multi-agent rewrite — verification + parallelism scaling implications for manager-mode

Date: 2026-07-17. Method: deep-research workflow, 101 agents (5 search angles, 19 sources fetched, 88 claims extracted, 25 adversarially 3-vote verified: 16 confirmed / 9 refuted). Primary source for the mechanism: Jarred Sumner (Bun founder), `bun.com/blog/bun-in-rust`, 2026-07-08.

## 1. Claim verdict: mostly TRUE, correction on framing

- **"64 sub-agents" is real, not hype** — but it's peak concurrency, not total team size. Verbatim: "At peak, we were running 4 of these workflows at once each in a separate worktree, each with 16 Claudes per workflow. About 64 Claudes at a time." = 4 worktrees × 16 = 64 peak concurrent.
- ~50 dynamic workflows total ran over 11 days (May 3→14, 2026), porting 1,448 Zig files (535K lines) into 1.04M lines of Rust, ~$165K API cost, peak ~1,300 LOC/min.
- **Andrew Kelley (Zig creator) publicly disputed the quality claim**: called it "1 million lines of unreviewed slop," argued passing the test suite ≠ proof of correctness, and attributed Bun's problems to engineering-discipline/AI-overreliance, not Zig itself. Credible counter-narrative, not dismissible.

## 2. Actual mechanism (verbatim-confirmed)

**Decomposition:** module/crate-level. Loop per crate: `cargo check` → fix compiler errors within that crate → adversarial review → apply.

**Adversarial review — exact pattern ("1 fixes, 2 review, 1 applies"):**
> "1 implementer, 2 or more adversarial reviewers per implementer. The reviewer's only job: find bugs & reasons why the code does not work. The implementer doesn't review. The reviewer doesn't implement."

Reviewer context = **diff only, zero implementer reasoning**, explicitly instructed to assume the code is wrong. Caught real pre-merge bugs: a `Box<uv::Pipe>` use-after-free/double-free, a negative-timespec `floor()` vs `trunc()` bug, an eager-`unwrap_or` panic that should've been `unwrap_or_else`.

**Merge conflicts — solved architecturally, not resolved after the fact.** Early failure: "one Claude ran `git stash` before committing. Another ran `git stash pop`. And then `git reset HEAD --hard`. They were stepping on each other!" Fix: banned `stash`/`reset`/any non-file-scoped git command, split into 4 isolated worktrees so shards never touch shared git state concurrently.

**Correctness backstop:** a pre-existing ~1M-assertion TypeScript conformance/test suite, not code review alone — this is exactly Kelley's critique target (tests substitute for review, don't prove correctness at this scale). Sumner also manually read workflow output for all 11 days — active supervision, not unattended trust.

## 3. Broader field survey — verified findings

- **`arXiv:2604.19049`** (Agarwal, "Refute-or-Promote"): adversarial stage-gate where reviewers must *actively try to refute*, not confirm. Real failure case: an 80+-agent unanimous "confirmation" of an OpenSSL CVE was wrong — one fresh-context agent that actually compiled+ran the code killed it. **Consensus among same-context agents is correlated error, not verification.**
- Same paper: cross-context (fresh) review beats same-session review; *more debate rounds degrade quality* — isolate context, don't stack rounds.
- **`arXiv:2511.16708`**: combining independent-pattern detector agents improves bug-catch rate with diminishing returns — 4th added detector is near-zero marginal value (measured pairwise correlation 0.05–0.25, genuinely near-independent).
- **`github.com/ng/adversarial-review`** (real, live Claude Code plugin): dual Optimizer/Skeptic, every verdict must be backed by actual command/tool output, not reasoning alone — explicit anti-rubber-stamp design.
- **Documented failure mode** (`szymonpaluch.com`): 80+ agents including dedicated adversarial reviewers unanimously endorsed a non-existent vulnerability. Correlated-error risk isn't theoretical.
- **Coordination cost scaling**: merge/coordination overhead grows worse-than-linear (Universal-Scalability-Law-shaped) with agent count — real throughput peak beyond which adding agents *reduces* net velocity, independent of model quality.

## 4. Implications for manager-mode

**Quality patterns worth adopting (catch real bugs, not false confidence):**
- Reviewer sees diff only, zero implementer context — prevents anchoring. Phase 8's overlord-compiled brief + fresh reviewer already approximates this; keep it.
- Reviewer mandate = "try to refute," never "check this is fine." Agreement-seeking framing is what produced the false-positive OpenSSL case.
- Verdicts must cite concrete evidence (test run, compiler output, actual command) — sharpest signal across every source separating real catches from rubber-stamps. Worth hardening into Phase 8's B/C stages explicitly.
- Cross-context/cross-model review beats same-session multi-round debate — more rounds ≠ better.
- 2 reviewers (Bun's real number) plus "≥2-must-agree-to-kill" sits close to the literature's empirically-justified sweet spot (diminishing returns after ~3–4 independent detectors).

**Parallelism ceiling — concrete lever:**
- Bun's real bottleneck wasn't model reasoning quality, it was **git-level coordination**. Fix was worktree sharding + banning cross-shard git ops (stash/reset outside file-scoped commits) — not a flat concurrency cap.
- Directly portable to manager-mode's open wave-size gap: instead of raising the ~16-leaf flat cap, **shard leaves into N isolated worktrees** (Bun-equivalent: 4 shards × 16 = 64). Isolation boundary, not raw agent count, is what lets that scale without collision.
- Cross-wave sequencing (existing open gap) maps to Bun's crate-by-crate loop: a "wave" = one shard's ordered task queue; shards run in parallel; sequencing only matters *within* a shard where files have order dependencies, not across shards.
- Coordination cost scaling worse-than-linear means: don't chase a bigger flat wave — chase more isolated shards.

**Bottom line:** the 64-agent story and its adversarial-review + worktree-sharding mechanism are real and directly portable. Kelley's counter-narrative is the important caveat: passing tests isn't proof of correctness at this scale, so for delicate codebases, raise reviewer count modestly (2–3, not more), demand tool-grounded verdicts, and spend marginal effort on worktree/module isolation rather than flat parallelism increases.

## Sources
- Primary: `bun.com/blog/bun-in-rust` (Jarred Sumner, 2026-07-08)
- `andrewkelley.me/post/my-thoughts-bun-rust-rewrite.html` (Andrew Kelley rebuttal)
- `newsletter.pragmaticengineer.com/p/the-pulse-what-can-we-learn-from-07f` (Gergely Orosz interview w/ Sumner)
- `simonwillison.net/2026/Jul/8/rewriting-bun-in-rust/`
- `theregister.com/devops/2026/07/14/zig-creator-calls-buns-claude-rust-rewrite-unreviewed-slop/5270743`
- `theregister.com/devops/2026/05/14/anthropics-bun-rust-rewrite-merged-at-speed-of-ai/5240381`
- `arxiv.org/abs/2604.19049` — Agarwal, "Refute-or-Promote: An Adversarial Stage-Gated Multi-Agent Review Methodology for High-Precision LLM-Assisted Defect Discovery" (Apr 2026)
- `arxiv.org/abs/2511.16708` — Rajan, "Multi-Agent Code Verification via Information Theory" (Noumenon Labs/Harvard, Oct–Nov 2025)
- `github.com/ng/adversarial-review` — Optimizer/Skeptic Claude Code plugin
- `szymonpaluch.com/blog/posts/multi-agent-consensus-verification` — documented consensus-failure case study
