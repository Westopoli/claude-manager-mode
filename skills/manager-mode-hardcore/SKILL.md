---
name: manager-mode-hardcore
description: Stricter sibling of /manager-mode for delicate, high-consequence codebases where an extra verification pass is worth the token cost — production data pipelines, payment/auth code, migrations, anything where a wrong admit is expensive to unwind. Every leaf's diff goes through a builder → auditor → resolver pipeline (three separate sub-agents, three separate contexts) BEFORE it touches real code, not just at wave-end. Use when the user says things like "this is delicate, use hardcore mode", "I want a stricter cascade for this", "run manager-mode-hardcore", "this touches production data, double-check everything before it lands", or is working somewhere a silent bad admit would be costly to discover later. Do not use for ordinary feature work — the extra agent-per-leaf cost isn't worth it there; use /manager-mode instead.
---

# /manager-mode-hardcore — per-leaf adversarial gate before any code lands

Same cascade as `/manager-mode`, one structural difference: **every leaf's diff is adversarially audited and resolved before it is admitted**, not just once at the end of the wave. Base `/manager-mode`'s Phase 8 catches problems after a whole wave has already landed in real code; hardcore catches them per-leaf, before they land at all. This costs roughly 3x the sub-agent calls per leaf (builder, auditor, resolver instead of just builder) — spend it where a bad admit is expensive, not everywhere.

Theory, brief template, config schema: same shared assets as `/manager-mode` — `~/.claude/skills/swarm-shared/references/playbook.md`, `brief-template.md`, `config.md`. Nothing here duplicates those; hardcore only changes when the adversarial check runs and how many roles participate.

If you haven't read `/manager-mode`'s `SKILL.md`, read it first — this file only spells out the delta.

---

## Phases at a glance

```
Phase 0  Preflight                — identical to /manager-mode Phase 0
Phase 1  Lite-discovery           — identical to /manager-mode Phase 1
Phase 2  Decompose                — identical to /manager-mode Phase 2
Phase 3  Audit briefs             — identical to /manager-mode Phase 3
Phase 4  Per-leaf 3-agent gate    — builder → auditor → resolver, per leaf, before admission (REPLACES base Phase 4+6)
Phase 5  Wait + aggregate sweep   — identical to /manager-mode Phase 5, run after all leaves resolved
Phase 7  Final report             — identical to /manager-mode Phase 7, adjusted for 3 roles/leaf
Phase 8  Wave-level adversarial audit — identical to /manager-mode Phase 8, runs on top, unchanged
```

There is no separate "Phase 6" here — base `/manager-mode`'s admission loop (file-match, G1–G7, umbrella pre/post, admit-or-revert) is *absorbed into* Phase 4's per-leaf pipeline below, gated behind the resolver's decision instead of running unconditionally the moment a leaf reports green.

Phase 8 still runs at the end. Hardcore does not remove the wave-level skeptic pass — it adds a per-leaf one underneath it. This is strictly more verification than base `/manager-mode`, never less.

---

## Phases 0–3 — identical to base `/manager-mode`

Preflight, lite-discovery, decompose, and brief-audit work exactly as documented in `/manager-mode`'s `SKILL.md`. No changes. Follow those phases as written, including the task-size guardrail (≤12/warn 13–16/refuse >16) and the shard-based parallelism section, if the spec is large enough to need it.

---

## Phase 4 — Per-leaf 3-agent gate

For every brief, in ascending NN order (or across shards in parallel, if sharding — see base skill's shard section): spawn three sub-agents in sequence, each in its **own fresh context**. Nothing carries over between them except what's explicitly written to disk — that isolation is the entire point. An auditor that inherits the builder's reasoning can be talked into agreeing with it; a resolver that inherits the auditor's framing can rubber-stamp it. Fresh context per role is what keeps each check honest.

### 4.1 Builder

Same role as base `/manager-mode` Phase 4's leaf agent, same prompt shape, same subagent-type selection rule (`caveman:cavecrew-builder` default, `general-purpose` fallback per the brief's tool footprint — see base Phase 4.2). No behavior change: reads its brief, writes impl against the pre-written failing test, stages output at `.swarm/pending/leaf-NN/`, reports green-in-isolation.

If the builder reports red after multiple attempts, escalate to the user exactly as base Phase 4.3 describes — do not proceed to the auditor with a leaf that isn't green.

### 4.2 Auditor

Spawn a **new** sub-agent (fresh context — do not reuse or continue the builder's) once the builder has staged output and reported green. Give it:

- The brief at `<briefs_dir>/leaf-NN.md` (for spec_lines + contract_imports — the auditor needs to know what the leaf was supposed to do).
- The staged diff at `.swarm/pending/leaf-NN/` — **diff only.** Do not pass along the builder's own summary, reasoning, or assumption log. If the builder left comments in the code explaining its choices, that's fine (it's part of the diff), but don't additionally hand the auditor a paraphrase of "here's what the builder said it did."

Use `caveman:cavecrew-reviewer` (fall back to `general-purpose` with an explicit "assume it's wrong" instruction), with this framing — the same three rules base `/manager-mode`'s Phase 8 auditor now follows, applied per-leaf instead of per-wave:

```
You are auditing leaf-NN of a hardcore TDD cascade, before it is admitted
into real code. Default posture: assume the staged diff is wrong until
you've checked hard enough to be confident otherwise. The builder's test
passing only proves the code matches its own test — it proves nothing
about correctness beyond that narrow slice.

Your mandate is to actively TRY TO REFUTE this diff, not to confirm it
looks fine. Go in looking for the strongest reason this leaf should NOT be
admitted. This matters because agreement-seeking review is a documented
failure mode: in one published case, 80+ independent review agents —
including dedicated adversarial reviewers — unanimously endorsed a
vulnerability that didn't exist, because each one checked "does this look
plausible" instead of "can I prove this wrong." Confirmation is a
conclusion you earn by genuinely trying and failing to find a problem, not
a default.

You have the brief (spec_lines, contract_imports — what this leaf was
supposed to do) and the staged diff. Nothing else. Evaluate the diff as if
it arrived with no explanation: a comment claiming "this is safe because X"
is not evidence, only the code's actual behavior is.

Look for:
  - actual bugs / wrong behavior, including ones the leaf's own test
    doesn't exercise
  - deviation from what the brief's spec_lines / contract_imports actually
    require
  - inefficiency, code slop, missing error handling at real boundaries —
    same bar as a real code review
  - anything that technically passes the test but wouldn't survive
    scrutiny in a codebase where a wrong admit is expensive to unwind

Every finding, at any severity (🔴 bug, 🟡 risk, 🔵 nit, ❓ question), MUST
cite the concrete evidence behind it — a quote from the diff, the brief's
spec_lines, or an actual command/test output if you can run one. "This
looks wrong" is not a finding. "Line N does X, which contradicts spec_lines
<range>'s requirement that Y" is. If you can't point to specific evidence,
you haven't finished checking — keep looking, or report it as an
unverified ❓ question rather than a settled finding.

If you genuinely find nothing after trying, say so in one line — don't
manufacture findings to fill space. But "nothing found" must follow an
actual attempt to refute, not a skim.
```

Write the auditor's findings to `.swarm/pending/leaf-NN/AUDIT.md` (findings + cited evidence, same severity-tag format as base Phase 8). If the auditor reports zero findings, write that file anyway with the one-line clean verdict — the resolver needs a file to read either way.

### 4.3 Resolver

Spawn a **third** sub-agent (fresh context, not continued from the auditor). This is the step that decides whether code actually changes. Give it:

- `.swarm/pending/leaf-NN/AUDIT.md` — the auditor's findings and cited evidence.
- The staged diff at `.swarm/pending/leaf-NN/` (the resolver needs to see the actual code the auditor is describing, to judge whether the citation is accurate — it should not take the auditor's word blind, same principle as the auditor not taking the builder's word blind).
- The brief, for the same reason the auditor needed it.

The resolver's job is narrow and specific — **not** "is this diff good," but "does the auditor's cited evidence actually support what it's claiming":

```
You are the resolver for leaf-NN of a hardcore TDD cascade. An auditor
already reviewed this diff and produced findings in AUDIT.md, each with
cited evidence. Your only job: for each 🔴/🟡 finding, check whether the
cited evidence actually substantiates the claim. You are not re-reviewing
the diff from scratch, and you are not deciding whether the code is good —
you are checking the auditor's homework.

For each 🔴/🟡 finding:
  - Read the cited evidence (the quoted line, the spec_lines reference,
    the command output).
  - Check it against the actual diff and brief.
  - Does the evidence say what the auditor claims it says? Does the cited
    spec_lines range actually require what the auditor says it requires?
  - If you can run a command to verify (e.g. the cited test actually fails
    the way claimed), do so.

Verdict per finding: EVIDENCE SUPPORTS CLAIM, or EVIDENCE DOES NOT SUPPORT
CLAIM (with your own reasoning for why not — you're not rubber-stamping
either direction, a lazy "seems fine" is exactly the failure mode this
whole pipeline exists to prevent).

🔵 nits and ❓ questions don't block admission on their own — note them for
the report but they don't need a supports/does-not-support verdict.

Final decision:
  - If ANY 🔴/🟡 finding's evidence SUPPORTS the claim: this leaf is NOT
    admitted. Say so clearly, list which finding(s) blocked it.
  - If every 🔴/🟡 finding's evidence DOES NOT support its claim (or there
    were no 🔴/🟡 findings at all): this leaf proceeds to the normal
    admission gates. Say so clearly.

Write your verdict to .swarm/pending/leaf-NN/RESOLUTION.md.
```

### 4.4 Act on the resolver's verdict

- **Resolver says NOT admitted:** do not run the base admission gates. Leave the leaf's diff at `.swarm/pending/leaf-NN/` for the record (don't delete it — it's the evidence trail), append a row to `post-review-log.md` with `status: blocked-by-audit` and a pointer to `AUDIT.md` + `RESOLUTION.md`, and continue the loop with the next leaf. This is not a revert (nothing was ever admitted to revert) — it's a leaf that never got past the gate. Surface it to the user in the Phase 7 report same as a reverted leaf.
- **Resolver says proceed:** run base `/manager-mode`'s Phase 6 admission gates exactly as documented (6.0 bypass detection through 6.9a/6.9b) — file-match, G1–G7, umbrella pre/post, admit-or-revert. The resolver clearing a leaf is not the same as admitting it; the objective gates still have to pass. This is the same "resolver isn't a rubber stamp for admission" principle in reverse — a clean audit doesn't skip the mechanical checks, it just means the leaf is *eligible* for them.

### 4.5 Wait for all leaves to resolve

Do not advance to Phase 5 until every leaf in the wave has gone through builder → auditor → resolver → (blocked or admission-gated). A leaf stuck red after multiple builder attempts, or repeatedly blocked by the auditor/resolver pair after re-spawns, escalates to the user — same as base Phase 4.3, just with two more places a leaf can get stuck.

---

## Phase 5 — Wait + aggregate sweep

Identical to base `/manager-mode` Phase 5. Runs once, after every leaf in the wave has been through Phase 4 (whether admitted, blocked-by-audit, or reverted by the objective gates). The wave-snapshot, assumption-sweep, and open-question/proposal triage all work exactly as documented there.

---

## Phase 7 — Final report

Same report shape as base Phase 7, with one addition to the per-leaf table: a `blocked-by-audit` status alongside `clean` and `REVERTED`, for leaves the resolver stopped before they ever reached the objective gates. Point at each blocked leaf's `AUDIT.md` + `RESOLUTION.md` in the follow-up direction section, same as base Phase 7.3 points reverted leaves at their `## Post-review regression` block.

---

## Phase 8 — Wave-level adversarial audit

Identical to base `/manager-mode` Phase 8, unchanged, run against everything admitted this wave. Hardcore's per-leaf gate in Phase 4 catches problems before individual leaves land; Phase 8 still catches problems visible only once the whole wave is assembled (goal-fidelity drift across the whole spec, umbrella coverage gaps, cross-leaf integration issues) — the two passes check different things and neither substitutes for the other.

---

## What's different from `/manager-mode`, in one paragraph

Base `/manager-mode` admits a leaf the moment its own test goes green and the objective gates (G1–G7, umbrella regression check) pass, then runs one skeptical pass over the *whole wave* at the end. Hardcore inserts a second, adversarial, evidence-gated check **per leaf**, in its own isolated context, before the objective gates ever run — and a third, separate-context check on whether that adversarial check's own reasoning holds up — so a bad diff can be stopped before it's admitted at all, not just flagged after the fact. Same file-based, no-git architecture underneath; same brief format; same shared invariant script. The cost is real (3 sub-agent calls per leaf instead of 1, roughly), so reach for this skill specifically when the codebase is delicate enough that the extra token spend is clearly worth it, and use plain `/manager-mode` otherwise.
