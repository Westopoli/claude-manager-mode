# CASH Onboarding Automation — Overlord Phase 2 Decomposition (dry run)

**Scope note:** this is a read-only Phase 2 exercise (SKILL.md §2.1–2.4). No code written, no
sub-agents spawned. Input is `Kowski-Ventures/docs/CASH_Project_Plan.md` only — treated as if it
were the entire spec, as an overlord sizing a brand-new build would see it. No implementation
files were read. Where the plan text itself names an implementation file (it frequently does — this
spec was written retrospectively against real code), that citation is used as-is for the dependency
map; it is not independent confirmation from the tree.

The plan carries its own amendment history (v3 → Phase 9 → Phase 10 → Phase 11 → Phase 12/§20).
§20 explicitly supersedes §4's review-gate design and large parts of §18/§19's "hold for review"
framing. Decomposition below targets the **current, superseding architecture** (§20: zero review
gates, independent branch guards, `issues_log` logging) while still covering the foundational
mechanics (§2, §3, §5, §6, §7, §8, §9, §16, §17) that remain valid building blocks under that
architecture.

---

## 2.1 Dependency map (manual scan, no `graphify_cmd`)

Grouping by which plan sections would write to which files, as named directly in the plan text:

| Plan section(s) | Concern | Files the plan text names |
|---|---|---|
| §2 (trigger/HMAC), §5 (idempotency) | Webhook signature verify, replay/dedup gate | (implied) signature-verify code node, idempotency Data Table gate |
| §3 (normalization), §3a (unlinked events) | Canonical field mapping, format validation, unlinked-event branch | `src/cash_flow/normalizeReasons.mjs`, `gateReasons.mjs` (named together with envelope files in §20 Stage A) |
| §20 Stage A (envelope/idempotency/normalize) | Groups the above four files explicitly as one pre-Dropbox/Sheets/Printer stage | `src/cash_flow/envelopeReasons.mjs`, `idempotencyReasons.mjs`, `normalizeReasons.mjs`, `gateReasons.mjs` |
| §8 (route lookup), §19 item 9, §20 Stage B | Route resolution (`case_title` → spreadsheet/sheet), auto-provision, duplicate-route pass-through | `src/cash_flow/caseSheetRoutes.mjs`, auto-provision branch in `scripts/build_cash_workflow.mjs` |
| §6, §20 Stage C | Dropbox folder/upload/share-link chain, folder-split detection, link-visibility fix, 401/5xx handling | `src/cash_flow/folderPathReasons.mjs`, `src/cash_flow/runtimeReasons.mjs` (Dropbox portion) |
| §8 (Sheets append/E:M write), §18/§19 step7_harden, §20 Stage D | PVC row write, header validation, duplicate/merged-header detection, `SHEET_*` write-failure codes | Sheets-write branch nodes, `runtimeReasons.mjs` (Sheets portion), header-validation node |
| §7 | Label + document print, document-print's genuine dependency on Dropbox's share link, `Code: Build Document Print Jobs` crash fix | print-job builder node(s) in `scripts/build_cash_workflow.mjs` |
| §20 Part B | Branch-independence restructure, Wait/approval/email detach, merge-node resize, `issues_log` consolidation — the plan's own retrospective calls this "too tightly interconnected... one file, one wiring graph, no clean parallel-safe seams" | `scripts/build_cash_workflow.mjs` (topology/wiring) |
| §20 "Decisions confirmed" (severity vocabulary) | One-line collapse: `review` behaves like `warn` | `classifyDelivery.mjs` |
| §17 | Apps Script container-bound plugin: setup, cursor-determines-destination-row transfer, validate/repair, merged-cell warning | `Kowski-Ventures/apps_script/Code.gs`, `scripts/deploy_apps_script.sh` |
| §16 | Day-1 one-time route/header seeding ("Stage 1" — never re-run in steady state) | a standalone provisioning script (not the runtime routing module) |
| §9 | Notification email | detached per §20, not active build work — folded into the orchestration leaf as a no-op/disconnect step |
| §10 | Error-handling policy (continue-on-error vs stop-on-error) | superseded by §20's independent-branch guards; folded into the orchestration leaf, not standalone |
| §14a, §15, §18 Part B (fragility audit doc) | Reference/documentation only — vendor scaling stress case, pre-launch client questions, human-editable-surfaces audit | docs, not leaf-owned code; cross-cuts every stage's codes so it belongs to the overlord as a synthesis artifact, not a single leaf |
| REVIEW_CODES / FIX_INSTRUCTIONS constants | Touched by nearly every stage above | a shared constants file — high collision risk if left to any one leaf |

**Constants file called out separately:** almost every stage-leaf below needs to add or reference
`REVIEW_CODES`/`FIX_INSTRUCTIONS`-style entries. Per this codebase's own stated convention
(constants/config files should hold no imports and stay collision-free), that file is treated as
**parent-owned / prep-step**, not assigned to any leaf — the overlord extends it directly before
briefs go out, avoiding nine leaves racing to edit the same file.

No two candidate slices below touch the same impl file within one wave — the max-safe count from
this map, before consolidation, would be higher (each Stage-A sub-file, each Stage-C sub-concern,
etc. could be its own leaf). 2.2 collapses that down.

---

## 2.2 Consolidation pass (four-axis rubric)

| Candidate | Rule-clusters | Exception branches | External integrations | Cross-cutting concerns | Verdict |
|---|---|---|---|---|---|
| Stage A (envelope+idempotency+normalize) | Signature/HMAC check, replay-window, dedup gate, ~15-field canonical mapping, format validation | Unlinked event (`crm_linked: false`) branch | 1 (idempotency Data Table) | 0 — nothing here is re-applied elsewhere | **One leaf.** Plan text itself groups these 4 files as one pre-Dropbox/Sheets/Printer stage (§20); a wrong assumption in HMAC verify or in field mapping can't silently corrupt Dropbox/Sheets output — same failure domain ("is this payload valid/usable at all"). |
| Routing (Stage B) | Route lookup, auto-provision, missing/invalid/inactive/duplicate branches | `CASE_ROUTE_DUPLICATE` agree-vs-disagree logic (§19 item 9) | 1 (Sheets/DataTable route lookup) | 0 | **One leaf**, kept separate from Sheets-write — routing decides *where*, the write leaf decides *what gets written*; §20's own table treats "no destination" as a routing-only concern independent of Dropbox/Label. |
| Dropbox chain (Stage C) | Folder create/reuse (409 handling), upload (mode:add not overwrite), shared-link create (409 + tagged-union visibility check), URL transform | Folder-split token search, 401/5xx handling | 1 (Dropbox API) | 1 — visibility/link-shape bugs recur across create+share (already bit this project twice per §19) | **One leaf.** Right at the "≤1 cross-cutting concern, ≤2-3 integrations" ceiling — kept intentionally narrow (Dropbox only) rather than folding in Printing, because Printing's only real coupling is a one-way data dependency (share link), not shared logic. |
| Sheets PVC write (Stage D-Sheets) | E:M append, row-6 header validation, duplicate-header warn, merged-header detection, `SHEET_*` write-failure codes | header/merge-detection edge cases (step7_harden's 3 live-only bugs were all here) | 1 (Google Sheets API) | 1 — header assumptions apply to both the write path and the validation path | **One leaf**, separate from Routing — routing's failure domain is "which sheet"; this leaf's is "did the write to that sheet succeed/validate," a materially different rule set (the plan's own Stage D table lists 4 distinct `SHEET_*` codes here, none shared with Stage B). |
| Printing (Stage D-Label/Doc) | Label field mapping, document-print job build, Dropbox-share-link dependency gate | `Code: Build Document Print Jobs` crash-on-missing-Dropbox-data fix | 1 (PrintNode) | 0 | **One leaf.** Small (§7 is explicitly "unchanged from v2... nothing in the payload doc affects printing mechanics"), but file-disjoint from Dropbox/Sheets and its only real risk (the crash bug) is self-contained to the print-job builder. |
| Orchestration/topology (§20 Part B) | Branch-independence guard wiring, Wait/approval/email detach, merge-node resize (4→3 inputs), `issues_log` two-insert consolidation | none new — this *is* the exception-branch-elimination work | 0 direct (touches n8n Data Table for issues_log, already covered under Stage A/B/C/D's own integrations) | **All of them** — this leaf's entire job is re-applying "skip cleanly + log" consistently across every other leaf's failure codes | **One leaf, deliberately not split further** — this matches the plan's own retrospective verdict almost verbatim: too tightly interconnected, one wiring graph, no parallel-safe seam. The dangerous cross-cutting axis from 2.2's rubric is maximally present here; splitting it is exactly what the rubric warns against. |
| Severity collapse (`classifyDelivery.mjs`) | One rule: `review` behaves like `warn` in the collapse function | none | 0 | 1 — technically cross-cutting (touches every REVIEW_CODE's runtime effect) but the plan itself calls it "pure unit-level, independent," sequenced as its own Phase 1 ahead of the orchestration work | **Kept as its own tiny leaf**, not folded into orchestration — different file (`classifyDelivery.mjs` vs `build_cash_workflow.mjs`), no shared footprint, and the plan explicitly sequences it as an independent, earlier, lower-risk change. Folding it into the orchestration leaf would make that leaf's already-maximal cross-cutting footprint worse for no file-safety benefit. |
| Apps Script plugin (§17) | Setup/role-binding, cursor-determines-destination-row transfer, column-matching-by-normalized-header, validate/repair, merged-cell warning | destination-status-column guard, unrecognized-status skip, blank-header fatal case | 1 (Apps Script / container-bound spreadsheet, a wholly separate runtime from n8n) | 0 relative to the n8n pipeline (no shared file, no shared runtime) | **One leaf**, entirely separate deliverable — different repo area (`Kowski-Ventures/apps_script/`), different language/runtime, its own multi-rule surface (setup, transfer, validate/repair) is large enough on its own to be one coherent leaf rather than a footnote on any pipeline leaf. |
| Day-1 initialization (§16) | Register active routes, ensure System-tab headers exist | none — explicitly "not part of the normal onboarding flow," run once | 1 (same Sheets/DataTable surface as Routing, but at provisioning time, not request time) | 0 | **One leaf**, kept separate from Routing despite the shared DataTable: different execution context (one-time offline script vs runtime lookup), different file, different failure domain (build-time seeding vs runtime resolution) — merging would conflate "populate the table" with "read the table," which is exactly the kind of same-word-different-job merge the rubric's failure-domain test exists to catch. |

Not made into leaves:
- **`REVIEW_CODES`/`FIX_INSTRUCTIONS` constants** — parent-owned prep-step (every leaf above touches it; one shared owner avoids a 9-way collision).
- **§9 (notification email), §10 (error-handling policy)** — both superseded/absorbed: §9 is detached-not-deleted under §20, §10's continue/stop-on-error policy is superseded by the orchestration leaf's independent-branch guards. Neither carries enough independent surface to be its own leaf.
- **§14a (vendor scaling), §15 (pre-launch questions), §18 Part B (fragility audit doc)** — reference/documentation only, explicitly informational, not build work; the audit doc in particular is a synthesis artifact spanning every other leaf's codes, better done by the overlord directly than assigned to one leaf.

---

## 2.3 Leaf-count guardrail

**9 leaves** after consolidation. Well under the 16 hard cap — no refusal, no re-scoping needed.

---

## 2.4 Fat-file check

Skipped per instructions — no implementation files exist/were read in this exercise.

---

## Leaf list

**Leaf 1 — Stage A: Envelope, Idempotency, Normalization**
- Covers: §2 (webhook trigger + HMAC signature verify), §5 (idempotency/dedup gate on `event_id`), §3 (canonical field mapping + format validation), §3a (unlinked-event branch)
- Expected files: `src/cash_flow/envelopeReasons.mjs`, `idempotencyReasons.mjs`, `normalizeReasons.mjs`, `gateReasons.mjs`
- Rationale: the plan itself names these four files together as one pre-Dropbox/Sheets/Printer stage; a wrong assumption anywhere in this stage can't silently corrupt Dropbox/Sheets/Printer output downstream — one failure domain ("is this payload valid and processable"), one integration (idempotency Data Table).

**Leaf 2 — Stage B: Routing (case_sheet_routes resolution)**
- Covers: §8's route-lookup portion, §19 item 9 (duplicate-route agree/disagree pass-through), §20 Stage B's five route codes
- Expected files: `src/cash_flow/caseSheetRoutes.mjs`, auto-provision branch logic
- Rationale: single failure domain (deciding *where* the Sheet write goes) and single integration (Sheets/DataTable route lookup); kept separate from the Sheets-write leaf because "which sheet" and "did the write succeed" are different rule sets per §20's own Stage B/D split.

**Leaf 3 — Stage C: Dropbox chain**
- Covers: §6 (folder create/reuse, PDF upload, shared-link create, URL transform), §19 Unit C (folder-split detection, link-visibility tagged-union fix), Unit D (401/5xx routing)
- Expected files: `src/cash_flow/folderPathReasons.mjs`, `src/cash_flow/runtimeReasons.mjs` (Dropbox portion)
- Rationale: one integration (Dropbox API), one recurring cross-cutting concern (link/visibility shape bugs have already bitten this exact surface twice per the plan's own history) — right at the rubric's consolidation ceiling, deliberately kept narrow rather than absorbing Printing, since Printing's only coupling is a one-way data dependency, not shared logic.

**Leaf 4 — Stage D: Sheets PVC write + header validation**
- Covers: §8's append/write portion (E:M columns, row-6 header), §18/§19 step7_harden (duplicate-header warn, merged-header detection), §20 Stage D's four `SHEET_*` codes
- Expected files: Sheets-write branch node(s), `runtimeReasons.mjs` (Sheets portion), header-validation logic
- Rationale: distinct failure domain from Routing (write/validate vs. resolve-destination) with its own dense rule cluster (step7_harden alone surfaced three separate live-only header bugs) and its own integration (Google Sheets API) — dense enough to earn its own leaf rather than folding into Routing.

**Leaf 5 — Stage D: Label + Document printing**
- Covers: §7 (label print, document print), the `Code: Build Document Print Jobs` crash-on-missing-Dropbox-data fix, document-print's genuine one-way dependency on Dropbox's share link
- Expected files: print-job builder node(s) in `scripts/build_cash_workflow.mjs`
- Rationale: small, self-contained surface (§7 is explicitly unchanged from the prior spec version), one integration (PrintNode), file-disjoint from Dropbox/Sheets — its only risk (the crash bug) doesn't require touching either of those leaves' files.

**Leaf 6 — Pipeline orchestration/topology + issues_log logging**
- Covers: §20 Part B in full — branch-independence guard wiring, Wait/approval/email detach (nodes disconnected not deleted), completion-merge resize (4→3 inputs), `issues_log` two-insert consolidation; also absorbs §9 (email detach) and §10 (superseded error-handling policy) as trivial sub-steps
- Expected files: `scripts/build_cash_workflow.mjs` (workflow wiring/topology)
- Rationale: kept as one leaf, not split, because the plan's own retrospective on this exact work reached the same conclusion — "too tightly interconnected... one file, one wiring graph, no clean parallel-safe seams." This is the cross-cutting axis the rubric warns is dangerous; splitting it is exactly the mistake 2.2 exists to prevent.

**Leaf 7 — Severity collapse (classifyDelivery.mjs)**
- Covers: §20's "Decisions confirmed" — `review` collapses to verdict `"proceed"` the same way `warn` already does
- Expected files: `classifyDelivery.mjs`
- Rationale: technically touches every REVIEW_CODE's runtime effect, but the plan explicitly calls it pure, unit-level, and independently sequenced ahead of the orchestration work; different file from Leaf 6 with zero shared footprint, so splitting it out costs nothing and keeps Leaf 6's already-maximal cross-cutting footprint from growing further.

**Leaf 8 — Apps Script plugin (Code.gs)**
- Covers: §17 in full — setup/role-binding via sheetId (not name) metadata, cursor-determines-destination-row transfer logic, normalized-header column matching, Validate/Repair, merged-cell warning, deploy tooling
- Expected files: `Kowski-Ventures/apps_script/Code.gs`, `scripts/deploy_apps_script.sh`
- Rationale: an entirely separate runtime and repo area from the n8n pipeline (no shared file, no shared execution context with any other leaf); its own rule surface (setup, transfer, validate/repair, three distinct edge-case guards) is large enough to be one coherent leaf on its own rather than a footnote elsewhere.

**Leaf 9 — Day-1 initialization (Stage 1 seeding)**
- Covers: §16 — one-time registration of active case routes + System-tab header verification, run exactly once at go-live, never in steady state
- Expected files: a standalone provisioning script (distinct from Leaf 2's runtime routing module)
- Rationale: shares a data surface with Routing (the same DataTable) but a different execution context and failure domain — build-time seeding vs. runtime resolution — so merging it with Leaf 2 would conflate "populate the table" with "read the table," the same same-word-different-job trap the rubric's failure-domain test is meant to catch.

---

**Total: 9 leaves.** Not made into leaves and why: `REVIEW_CODES`/`FIX_INSTRUCTIONS` constants (parent-owned prep-step, touched by ~7 of the 9 leaves above — one shared owner avoids collision); §9/§10 (absorbed into Leaf 6, too small/superseded to stand alone); §14a/§15/§18 Part B (reference and audit documentation, not build work — the audit doc especially is a cross-leaf synthesis artifact better owned by the overlord directly).
