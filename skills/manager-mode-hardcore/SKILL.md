---
name: manager-mode-hardcore
description: Stricter sibling of /manager-mode for delicate, high-consequence codebases where an extra verification pass is worth the token cost — production data pipelines, payment/auth code, migrations, anything where a wrong admit is expensive to unwind. It retains the complete normal Manager Mode builder, sweep, and G1–G7 admission flow, then double-audits admitted leaves in batches of at most three and sends each pair of reports to a fresh adjudicating reviewer. Use when the user says things like "this is delicate, use hardcore mode", "I want a stricter cascade for this", "run manager-mode-hardcore", "this touches production data, double-check everything before it lands", or is working somewhere a silent bad admit would be costly to discover later. Do not use for ordinary feature work — use /manager-mode instead.
---

# /manager-mode-hardcore — post-admission double evidence audit

Hardcore is `/manager-mode` with one deliberately narrow replacement: its post-admission Phase 8 uses two independent auditors plus a fresh reviewer for each batch of at most three admitted leaves. It does **not** move review before admission and does not remove any normal safeguard.

Theory, brief template, and config schema use the same shared assets as `/manager-mode`. Resolve `SWARM_SHARED_DIR` with `/manager-mode`'s Shared asset resolver, then use `$SWARM_SHARED_DIR/references/playbook.md`, `brief-template.md`, and `config.md`. Nothing here duplicates those; Hardcore only changes the post-admission adversarial check and how many roles participate.

Read `/manager-mode` first and execute its Phases 0–7 unchanged: preflight, lite-discovery, per-leaf RED tests, Phase 3 invariant audit, 12/16 sizing limits, parent ownership, staging, parallel builder dispatch, snapshot/sweep, questions/proposals, bypass detection, G1–G7, file-match, umbrella pre/post checks, admit-or-revert, apex testing, reporting, and shard non-overlap. In particular, run the normal admission loop before any hardcore review batch.

## Phase 8 — Double audit, then adjudicate

For every wave/shard independently, read the normal admission record and select only `status: clean` rows whose `wave` and `shard` columns match the current wave/shard; do not infer membership from reused `leaf-NN` values. A legacy row without those columns is escalation-only. Order the selected leaves by ascending `leaf-NN` and group them into deterministic batches of at most three. `batch-01` contains the first one to three leaves, `batch-02` the next, and so on. A shard's audit records live at:

```
.swarm/audits/wave-<wave>/<shard-or-default>/batch-<NN>/
```

Each batch directory begins with `AUDIT-BRIEF.md`, written by the overlord. It records the ordered membership, declared implementation/test footprint, locked spec, relevant contract/umbrella paths, user ask, sweep and dismissal context, and the rule that parent-owned files, contracts, umbrella tests, and paths outside the footprint are escalation-only.

### 8.1 Two independent auditors

Spawn two fresh-context auditors for each batch in parallel, and dispatch batches in parallel. Neither auditor may see the other auditor's prompt, report, reasoning, or findings. Use `caveman:cavecrew-reviewer` where available; otherwise use a fresh `general-purpose` reviewer with the same adversarial instruction.

Both auditors receive only `AUDIT-BRIEF.md`, the locked artifacts it names, and the batch's admitted code/tests. They never edit files. Their posture and report requirements are identical:

```
Assume the batch's admission is wrong until executable evidence proves otherwise.
Review goal fidelity, test coverage, integration behavior, and code quality.
For every finding, provide a concrete test/probe command, observed output, and
source or locked-spec citation. A claim without all three is unverified.
Do not manufacture findings. Do not edit. Mark any needed repair outside the
declared batch implementation/test footprint as ESCALATION-ONLY.
```

Persist the reports as `auditor-1.md` and `auditor-2.md`. Fresh context and disk-only reports are mandatory: the second auditor must not inherit the first auditor's framing.

If either report is missing, malformed, or arrives after the configured wait/retry limit, do not spawn the reviewer and do not report the batch or final suite as successful. Persist `AUDIT-FAILURE.md` with the missing role, wait/retry evidence, and an escalation; include the batch as failed/escalated in the final post-mortem.

### 8.2 Fresh reviewer adjudication

Only after both reports exist, spawn a third fresh-context reviewer for that batch. Give it `AUDIT-BRIEF.md`, both reports, code/tests, locked spec, and runnable commands. It independently evaluates **every** auditor claim; it does not trust either auditor just because they agree.

For every claim, it records `CONFIRMED`, `DENIED`, `UNVERIFIED`, or `ESCALATION-ONLY`, plus its own source/spec citation, probe, observed output, and rationale. It may implement only confirmed repairs within the batch's declared implementation/test footprint. It may add or adjust that batch's leaf tests only to pin confirmed behavior. A required change to a parent-owned file, contract, umbrella, or out-of-footprint path halts that item for overlord/user escalation rather than widening scope.

For each confirmed repair the reviewer runs affected leaf tests first, then the configured umbrella/full suite. A failed verification uses the normal backup/revert discipline and is recorded as not accepted. The reviewer writes all verdicts, changed paths, escalations, and verification results to `REVIEW.md` in the batch directory.

### 8.3 Final reporting

The overlord aggregates `REVIEW.md` files into `.swarm/audits/wave-<wave>/<shard-or-default>/POST-MORTEM.md`. It includes batch membership, two-auditor and reviewer counts, each claim's verdict/evidence, confirmed fixes, denied findings, escalations, changed paths, affected-test outcomes, and final suite status. Update the normal Phase 7 report with those same counts and outcomes.

No audit record belongs in `post-review-log.md`; it remains the append-only normal-admission history. Shards remain file-disjoint and retain separate wave snapshots, sweeps, audit directories, and batch IDs. No phase may bypass the base skill's existing gates.
