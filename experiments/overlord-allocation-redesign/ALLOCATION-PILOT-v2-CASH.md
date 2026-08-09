# Allocation Pilot v2 — CASH Onboarding Automation

Pilot of the actual delegate-then-audit shape specified in manager-mode SKILL.md Phase 2.2:
overlord reads the plan, delegates the consolidation *draft* to one fresh sub-agent, then
runs the completeness sweep itself, independently, against the full plan text it holds.

Source doc: `/Users/westley/iCodeETL/leandrc49/Kowski-Ventures/docs/CASH_Project_Plan.md` (611 lines, read in full by both the overlord and the sub-agent).
Rubric source: `/Users/westley/Projects/claude-swarm/skills/manager-mode/SKILL.md`, Phase 2.2 + "Delegated drafting passes."

---

## Step 2 — Sub-agent's draft (verbatim, general-purpose, fresh context, plan-file-only access)

### Leaf list (8 leaves)

**Leaf 1 — Envelope: webhook trigger, signature verification, idempotency gate**
Owns: §0/A1, A2; §2 (HMAC verify, ordering rule, replay window explicitly deferred); §5 (idempotency gate); §20's `reject-auth`/`reject-drop` hard gates (out of scope of review-removal migration).
Rationale: one rule-cluster, one exception branch, no external integration beyond the inbound webhook, single failure domain.

**Leaf 2 — Normalization, field mapping, unlinked events**
Owns: §3 (canonical shape, field mapping, format validation); §3a (unlinked events).
Rationale: single rule-cluster class + one exception branch, no external integration.

**Leaf 3 — Dropbox archive chain**
Owns: §0/A3, A6; §6 (folder/upload/share-link chain); §19 Unit C-leaf-C1/C2; §19 Unit D (open — live verification inconclusive).
Rationale: one integration (Dropbox), several exception branches sharing one failure domain.

**Leaf 4 — Sheets PVC routing + append**
Owns: §0/A7; §4's technical route/PVC-header validation; §8 (append-only write); §19 step7_harden; §19 Item 9 (open — not live-fire verified); §20's `IF: Sheets Ready?` guard.
Rationale: one integration (Sheets), rule-clusters share one failure domain.

**Leaf 5 — Day-1 initialization (Stage 1 provisioning)**
Owns: Overarching-Goal pre-provisioning invariant; §16 in full.
Rationale: distinct lifecycle boundary (one-time bulk vs. per-event runtime) from Leaf 4, despite sharing the same table — flagged as the decomposition's highest-risk seam (MONEY INC incident, §18, was caused by exactly this table drifting).

**Leaf 6 — Physical printing (label + document)**
Owns: §0/A5; §7; the Dropbox→Document-print data dependency; the Phase-0 `Code: Build Document Print Jobs` crash-fix prerequisite.
Rationale: one integration (PrintNode), one explicit narrow cross-leaf data dependency (not a broad cross-cutting concern).

**Leaf 7 — Verdict/severity/logging architecture + review-elimination**
Owns: §0/A4, A8 (superseded); §4 Tier table (superseded, historical); §9; §10 (error-handling pattern); §18 in full; §19 Units A/B, Items 10/11, known gap, operational finding; §20 in full (client direction, Part A aggregation, Part B migration, removal, "not yet done" list).
Rationale: the spec's own declared cross-cutting concern — §20 itself states the restructure is too interconnected to decompose further ("one file, one wiring graph, no clean parallel-safe seams"); kept as one leaf on the doc's own authority, consistent with the rubric's "amendment after a real incident = hidden coupling already found" signal.

**Leaf 8 — Apps Script Plugin (Code.gs)**
Owns: §17 in full.
Rationale: single file, zero overlap with the n8n workflow, high rule/exception count but one failure domain — already un-splittable.

### Sub-agent's own completeness sweep

Covered essentially every numbered/tabular section (§0–§20) plus A1–A9, with explicit one-line exclusions for §11–§15 (sequencing/lifecycle/cost/vendor-scaling/pre-go-live-confirmation sections — reference-only or non-ownable by the doc's own words) and §18 Part B / §19 known-gap / live-verified-evidence rows (historical record, no remaining build content).

### Sub-agent's self-flagged ambiguities (5 items)

1. Stale-review sweep (§4) — likely a permanent no-op under §20's design, but never explicitly retired in the text.
2. §19 Item 5 (PDF-archive-on-review-path) — treated as moot under §20 but not explicitly cross-referenced as superseded.
3. §19 Item 6 (resume-link idempotency) — same reasoning, same gap.
4. §19 operational finding (deploy doesn't reactivate Wait-webhook registration) — written pre-§20 full-detach; unclear if still relevant.
5. Leaf 4/Leaf 5 boundary — shared `case_sheet_routes` table, flagged as highest-risk seam.

---

## Step 4 — Overlord's independent completeness sweep

Run by hand against the full plan text held in the overlord's own context (not delegated). Every distinct requirement/invariant/open item stated anywhere in the doc, checked against the sub-agent's draft.

| # | Item | Where stated | Sub-agent's draft | Sweep verdict |
|---|---|---|---|---|
| 1 | Never create/read/delete sheets, append-only | Overarching Goal (prose, top) | Leaf 4 | Confirmed covered |
| 2 | Original/System tab separation, pre-provisioning, manual recovery | Overarching Goal | Leaf 5 + Leaf 8 | Confirmed covered |
| 3 | **Tests validate via workflow logs + manifest tracking, never by querying sheets back** | Overarching Goal, "Consequence for Testing and Deployment" bullet 1 (prose, stated once) | **Not owned by any leaf; not listed in sub-agent's sweep table at all** | **GAP.** This is exactly the failure mode the rubric's completeness-sweep note warns about — "framing sections stated once near the top... nothing else forces a second look." It's a real constraint (a leaf/tester could otherwise "fix" a flaky verification by reading sheet values back, which the spec explicitly forbids). Resolution below. |
| 4 | Pre-flight: destination sheets must exist before workflow runs, or appends fail | Overarching Goal, testing-consequence bullet 2 | Implicit in Leaf 5 (§16 restates this) | Covered (via §16 restatement) |
| 5 | A1–A9 | §0 table | All 9 mapped to leaves | Confirmed covered |
| 6 | Six actions summary | §1 | Distributed 3/4/6/7 | Confirmed covered |
| 7 | Signature verify, ordering rule, replay window deferred | §2 | Leaf 1 (replay window explicitly excluded) | Confirmed covered |
| 8 | Canonical mapping + format validation | §3 | Leaf 2 | Confirmed covered |
| 9 | Unlinked events | §3a | Leaf 2 | Confirmed covered |
| 10 | Tier table (superseded) + stale-review sweep | §4 | Leaf 7; stale-review sweep flagged ambiguous | Confirmed — ambiguity correctly surfaced, not silently dropped |
| 11 | Idempotency mechanics | §5 | Leaf 1 | Confirmed covered |
| 12 | Dropbox chain | §6 | Leaf 3 | Confirmed covered |
| 13 | Printing | §7 | Leaf 6 | Confirmed covered |
| 14 | Sheets append | §8 | Leaf 4 | Confirmed covered |
| 15 | Notification email | §9 | Leaf 7 | Confirmed covered |
| 16 | Error-handling policy | §10 | Cross-cutting pattern under Leaf 7, applied in 1/3/6 | Confirmed covered |
| 17 | §11–§15 (sequencing, JSON lifecycle, scaffold log, cost model, vendor scaling, pre-go-live confirmations) | §11–§15 | Explicitly excluded, one-sentence reasons each | Confirmed — legitimate exclusions, doc's own words support them |
| 18 | Day-1 init | §16 | Leaf 5 | Confirmed covered |
| 19 | Apps Script plugin (all sub-items) | §17 | Leaf 8 | Confirmed covered |
| 20 | MONEY INC incident + root-cause pattern, Part A/B | §18 | Leaf 7 | Confirmed covered |
| 21 | Route-drift script (built, never run, blocked on credential) | §18 stretch idea | Leaf 7 | Confirmed covered |
| 22 | Units A/B, C1/C2, D, step7_harden | §19 | Leaf 7 (A/B), Leaf 3 (C1/C2/D), Leaf 4 (step7_harden) | Confirmed covered |
| 23 | §19 Item 8 (severity flip, shipped, not yet live-verified) | §19 | **Owned by Leaf 4 in prose ("Leaf 4... Item 8" not actually named — checked: Leaf 4's paragraph does NOT mention Item 8 at all; Item 8 is PVC-stage review→warn, distinct from Item 9)** | **Minor gap: Item 8 is never assigned to any leaf, in prose or in the sweep table.** It's a `constants.mjs` severity-value change (`PVC_REQUIRED_MISSING`/`PVC_HEADER_MISMATCH` review→warn) — same file/mechanism as Leaf 7's severity-collapse work (§20 Part B), so it should sit with Leaf 7, not Leaf 4. Resolution below. |
| 24 | §19 Item 9 (duplicate-route pass-through, shipped, not yet live-fire verified) | §19 | Leaf 4 (stated in prose) | Covered in prose, but **missing its own row in the sub-agent's sweep table** — procedural gap, not an ownership gap (see note below) |
| 25 | §19 Item 10 (issues_log DataTable + `deliverable` column open) | §19 | Leaf 7 | Confirmed covered |
| 26 | §19 Item 11 (non-halting flip) | §19 | Leaf 7 | Confirmed covered |
| 27 | §19 known gap (DROPBOX_FOLDER_SPLIT token-loss) | §19 | Excluded — "not a bug," doc's own words | Confirmed — legitimate exclusion |
| 28 | §19 operational finding (deploy doesn't reactivate Wait-webhook registration) | §19 | Flagged ambiguous (possibly moot post-§20) | Confirmed — correctly surfaced, not silently dropped |
| 29 | §20 client direction, Part A matrix, Part B migration, removal, sequencing | §20 | Leaf 7 | Confirmed covered |
| 30 | §20 "shipped differs from plan" deltas (`IF: Sheets Ready?`, dual issues_log inserts, `Mark complete` crash instance, `deliverable` column not done) | §20 | Leaf 4 (guard) + Leaf 7 (rest) | Confirmed covered |
| 31 | §20 "not yet done" (19-code battery, deliverable column, unified DELIVERY_SUMMARY) | §20 | Leaf 7, explicitly open | Confirmed covered |

### Sweep tally

- **31 distinct items checked.**
- **1 real gap**: item 3 — the Overarching Goal's testing-methodology invariant ("verify via logs + manifest, never by re-querying sheets") had no owner and no exclusion anywhere in the draft or its sweep table. Caught by the overlord's independent sweep, exactly the scenario Phase 2.2 exists to guard against (prose stated once near the top, not in a numbered/tabular section).
- **1 minor gap**: item 23 — §19 Item 8 (severity flip PVC_REQUIRED_MISSING/PVC_HEADER_MISMATCH review→warn) is never assigned to any leaf, in prose or table, despite being an explicitly "not yet live-verified" open item the same class as Item 9 (which *was* assigned).
- **1 procedural (non-ownership) gap**: item 24 — Item 9 is correctly owned by Leaf 4 in the leaf-list prose, but has no corresponding row in the sub-agent's own sweep table, so the sweep table alone is not a complete audit trail of the draft's coverage.
- **28 items confirmed correctly covered** (either cleanly owned or legitimately/explicitly excluded, including all 5 ambiguities the sub-agent itself surfaced rather than silently resolving).

---

## Step 5 — Final leaf list (overlord adoption + corrections)

Adopting the sub-agent's 8-leaf structure — its rubric application (rule-clusters / exception branches / integrations / cross-cutting concerns) is sound and its own self-flagged ambiguities were handled correctly (surfaced, not silently guessed). Two corrections applied:

1. **§19 Item 8 → assigned to Leaf 7** (not left unowned). It's a one-line `constants.mjs` severity-value change, same file and same mechanism family as Leaf 7's §20 Part B severity-collapse work — belongs there, not with Leaf 4's routing/append logic.
2. **Overarching-Goal testing-methodology invariant → explicitly excluded from the leaf list**, with reason recorded (not silently dropped): this is a test-harness/verification-approach constraint ("assert via logs + manifest, never by reading sheet values back"), not workflow-implementation surface. It doesn't belong to any of the 8 build leaves; it should instead be a standing constraint on whatever test-writing step (shard-test-writer, per SKILL.md 2.6) later authors tests against Leaf 4/5's output. Recorded here so it isn't lost, per the rubric's "explicitly excluded with a one-sentence reason" requirement — the sub-agent's draft failed to do this and I'm correcting it now, not deferring it further.

Final leaf list (8 leaves, all names/scopes as the sub-agent drafted them except the Item 8 reassignment):

1. **Envelope** — webhook trigger, signature verification, idempotency gate (§0/A1-A2, §2, §5, §20 reject-auth/reject-drop)
2. **Normalization** — canonical field mapping, format validation, unlinked events (§3, §3a)
3. **Dropbox archive chain** — folder/upload/share-link, Units C1/C2/D (§0/A3+A6, §6, §19)
4. **Sheets PVC routing + append** — route lookup, header validation, append, step7_harden, Item 9, `IF: Sheets Ready?` guard (§0/A7, §4 technical validation, §8, §19)
5. **Day-1 initialization** — Stage 1 provisioning, one-time route/tab setup (Overarching Goal pre-provisioning invariant, §16)
6. **Physical printing** — label + document, PrintNode, Dropbox data-dependency, Phase-0 crash-fix (§0/A5, §7)
7. **Verdict/severity/logging + review-elimination** — declared cross-cutting concern; A4/A8, §4 Tier table (superseded), §9, §10 pattern, §18, §19 Units A/B + Items 8 + 10 + 11 + known gap + operational finding, §20 in full
8. **Apps Script Plugin** — Code.gs, all of §17

**Excluded, not assigned to any leaf** (recorded per rubric requirement, not a gap):
- Overarching Goal's test-verification-methodology invariant (logs+manifest, never re-query sheets) — belongs to the test-authoring step, not an implementation leaf.
- §11–§15 — sequencing guidance, unchanged-from-v2 lifecycle/cost sections, vendor-scaling reference-only math, pre-go-live client-confirmation checklist — none are build-implementable leaf content, all say so in their own text.
- §18 Part B (fragility-audit doc) and §19's live-verified-evidence/known-gap entries — historical record, no remaining build content.

---

## Tally: what the overlord's sweep caught vs. missed

- Sub-agent draft: 8 leaves, thorough rubric application, correctly surfaced 5 ambiguities instead of guessing.
- Overlord's independent sweep checked 31 distinct items against the draft.
- **1 real gap caught**: an unowned/unexcluded framing-section invariant (testing-verification methodology), stated once in prose near the top — exactly the pattern the rubric's completeness-sweep step exists to catch, and exactly the kind of thing a fresh sub-agent without the overlord's full-context read is likeliest to drop.
- **1 minor ownership gap caught**: §19 Item 8 never assigned to any leaf.
- **1 procedural gap caught**: §19 Item 9 owned in prose but absent from the sub-agent's own sweep table (a documentation-completeness issue in the audit artifact itself, not a coverage failure).
- 28 of 31 items independently confirmed as correctly handled by the draft (owned or legitimately excluded).
