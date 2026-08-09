# CASH Overlord Allocation — Independent Pass 2

Read-only Phase 2 decomposition exercise. Source: `Kowski-Ventures/docs/CASH_Project_Plan.md` only —
no other files under `leandrc49/` were read (no `src/cash_flow/`, no `.swarm/`, no git history), per
the exercise's constraint that this is treated as a fresh spec with no implementation yet.

---

## 2.1 Dependency map (manual — no `graphify_cmd`)

The plan repeatedly names concrete files inside its own prose (§19's Stage A–D tables, §17, §20's
Status section), so the map below uses those names rather than guessed ones.

Rough file-touch groups, by spec section:

| Spec area | Files the plan itself names |
|---|---|
| §2 signature verify, §5 idempotency, §3/§3a normalize + unlinked | `envelopeReasons.mjs`, `idempotencyReasons.mjs`, `normalizeReasons.mjs`, `gateReasons.mjs` |
| §8 route resolution, §16 Day-1 init, Stage B duplicate/auto-provision | `caseSheetRoutes.mjs`, auto-provision branch (in the orchestrator file), Day-1 registration step |
| §6 Dropbox chain, Stage C codes | `folderPathReasons.mjs`, `runtimeReasons.mjs` (dropbox side) |
| §8 Sheets write contract, Stage D sheets codes | Sheets-write branch logic, PVC header validate/append |
| §7 printing | PrintNode job-build nodes ("Code: Build Document Print Jobs", label job) |
| §9 email, §18/§20 severity collapse + logging + Wait/approval detach + terminal-node aggregation | `classifyDelivery.mjs`, the orchestrator wiring file (all node construction/wiring lives here per §20's own status note), issues_log inserts |
| §17 Apps Script plugin | `Kowski-Ventures/apps_script/Code.gs`, `scripts/deploy_apps_script.sh` — entirely separate system (Google Apps Script, not n8n) |

**Fat-file collision found by the map, not guessed:** §20's own "Status as of 2026-08-06" paragraph
states the orchestration restructure (branch-independence guards, Wait/approval/email detach, merge
resize, issues_log consolidation) was done as "a single cohesive change... too tightly interconnected
— one file, one wiring graph, no clean parallel-safe seams" — i.e. the spec document itself already
flags that this file cannot be split across leaves. Every other action-leaf's logic also ultimately
gets wired into that same orchestrator file (node construction for Dropbox/Sheets/Print calls, the
auto-provision branch, etc.), so if every leaf tried to both write its own pure logic module *and*
wire its own nodes into the orchestrator, they'd collide on that one file.

**Resolution:** split "pure decision logic" from "orchestrator wiring." Leaves 1–5 each own only their
own reason/logic `.mjs` module(s) (no orchestrator edits, no shared file). Leaf 6 owns 100% of the
orchestrator wiring file plus `classifyDelivery.mjs`'s severity-collapse line plus the issues_log
inserts, and is **sequenced after** leaves 1–5 land (it wires their finished exports into Code nodes —
a real dependency, not just a file-non-overlap courtesy). This keeps every leaf's `impl_files` disjoint
within the wave while respecting the plan's own explicit warning about that file.

---

## 2.2 Consolidation pass

Scored against the four axes (rule-clusters, exception branches, external integrations, cross-cutting
concerns) directly off spec text.

### Leaf 1 — Ingest gate: signature, idempotency, normalization, unlinked events
- **Covers:** §2 (webhook signature verify, HMAC-SHA256, raw-body/length-check ordering), §5
  (idempotency Data Table gate on `event_id`), §3 (canonical field mapping + format validation),
  §3a (unlinked-event routing on `crm_linked: false`), and §19 Stage A's code table
  (`TIMESTAMP_STALE`, `EVENT_ID_MISSING`, `MISSING_BLOCK`, `COMPANY_NAME_MISSING`,
  `DOWNLOAD_URL_MISSING`, `CONTRACT_ID_MISSING`, `UNLINKED`).
- **Files:** `envelopeReasons.mjs`, `idempotencyReasons.mjs`, `normalizeReasons.mjs`, `gateReasons.mjs`.
- **Rationale:** one leaf. All four rule-clusters share a single failure domain — "is this payload
  even usable before we try to route it" — and per §19's own table, none of Stage A's codes touch
  Dropbox/Sheets/Label data at all, confirming they're one self-contained gate. One external
  integration (the idempotency Data Table). No cross-cutting concern spans this leaf and anything else.

### Leaf 2 — Route resolution + Day-1 provisioning
- **Covers:** §8's route-lookup mechanics (`case_sheet_routes` → spreadsheet_id/sheet_name), §16
  (Day-1 Stage 1 one-time route registration + System-tab header readiness), and §19 Stage B's code
  table (`CASE_ROUTE_INVALID`, `CASE_ROUTE_MISSING`, `CASE_ROUTE_INACTIVE`, `CASE_ROUTE_DUPLICATE`,
  `PROVISION_FAILED`, including the duplicate-agreement pass-through logic from §19 Item 9).
  Deliberately does **not** include the actual PVC row write (that's Leaf 4) — this leaf only answers
  "which spreadsheet/tab does this case_title resolve to."
- **Files:** `caseSheetRoutes.mjs`, Day-1 registration script/step.
- **Rationale:** one leaf, kept separate from Leaf 4 (Sheets write) even though both touch Google
  Sheets, because this is a distinct failure domain — a wrong route decision here (picking the wrong
  spreadsheet, or the duplicate-vs-real-ambiguity call) is a routing-correctness bug, not a
  write-mechanics bug, and a bug in one can't silently corrupt the other's output as long as they're
  separate files. Day-1 init merges in rather than getting its own leaf because it exists purely to
  seed the same Data Table this leaf reads from — one external integration, one coherent unit.

### Leaf 3 — Dropbox chain
- **Covers:** §6 (create-folder-or-reuse-on-409, per-client `client_id` keying, upload with
  `mode: "add"`, shared-link create-or-reuse-on-409, `dl=0`→`dl=1` transform), and §19 Stage C's code
  table (`EMPTY_COMPANY_NAME`, `COMPANY_NAME_TOO_LONG`, `DROPBOX_LINK_NOT_PUBLIC`,
  `DROPBOX_FOLDER_SPLIT`, `DROPBOX_*_FAILED`).
- **Files:** `folderPathReasons.mjs`, `runtimeReasons.mjs` (Dropbox-facing functions only).
- **Rationale:** one leaf. Single external integration (Dropbox API), single failure domain (archive
  delivery), and the three Stage-C codes are explicitly called out in §19 as "the most wasteful under
  current behavior" precisely because they're all downstream of the same completed Dropbox work —
  they belong together, not split by code.

### Leaf 4 — Sheets PVC write
- **Covers:** §8's write contract (E:M-only append, row-6 header, 9-field shape, `Sheets Ready?`
  route-status guard) and §19 Stage D's Sheets-specific codes (`SHEET_VALIDATION_REJECTED`,
  `SHEET_RATE_LIMITED`, `SHEET_WRITE_FAILED`, `SHEET_POST_APPEND_FAILED`), plus the header/merged-cell
  detection behavior implied by the PVC append contract.
- **Files:** Sheets-write branch logic (header validate, row-build, append, post-append error
  classification).
- **Rationale:** kept separate from Leaf 2 (routing) and Leaf 3 (Dropbox) — different external
  integration surface (Sheets *write* API, vs Sheets *read-only route lookup* in Leaf 2, vs Dropbox in
  Leaf 3) and §19 Stage D's own framing confirms it: "only Sheets — Dropbox already ran... genuinely
  unaffected already." That's the spec declaring these are independent failure domains.

### Leaf 5 — Printing (label + document)
- **Covers:** §7 (PrintNode label + document jobs, on-hand printers) and the Phase-0 prerequisite fix
  the plan calls out by name — "Code: Build Document Print Jobs" must not crash when Dropbox hasn't
  run — since printing correctness under the new no-review design depends on that guard existing.
- **Files:** label/document PrintNode job-construction logic (a `printJobs`-style pure module, kept
  separate from the orchestrator wiring for the same fat-file reason as leaves 1–4).
- **Rationale:** one leaf. Two integrations at most (PrintNode, plus a one-directional *read* of
  Dropbox's finished `direct_url` — a data dependency, not a shared rule-cluster or shared file). §20's
  own Stage-D table calls the four fanout branches "already independent of each other" once dispatched
  — printing's dependency on Dropbox's output is real but asymmetric (consumes a value, doesn't touch
  Dropbox's code), so it doesn't force a merge.

### Leaf 6 — Orchestration: severity collapse, branch independence, Wait/approval detach, issues_log
- **Covers:** §9 (notification email, now detached), §18 Part A (runtime reason capture,
  `Classify PVC Header Read Error`, `REVIEW_CODES`/`FIX_INSTRUCTIONS` extension), §20 wholesale (the
  review/approval elimination: `classifyDelivery.mjs`'s `review`→proceed collapse, the
  `IF: Sheets Ready?` guard, Wait-node + both Gmail nodes detached from the live graph, the
  `Merge: Wait for 4→3 Proceed Actions` resize, the consolidated `issues_log` inserts keyed off the
  single `Runtime Review Verdict` terminal node per the `VERDICT_NODES` ordering convention).
- **Files:** `classifyDelivery.mjs` (the one-line severity-collapse rule) + the orchestrator wiring
  file in full.
- **Rationale — this is the deliberate exception to "split by rule-cluster," not an oversight:** the
  cross-cutting-concern axis is the dangerous one here on purpose. Logging (issues_log) reapplies
  across every stage (A/B/C/D), the terminal-node aggregation invariant (`VERDICT_NODES` ordering, one
  terminal node, no 5th added) spans the whole graph, and the severity-collapse is a single rule
  applied uniformly everywhere. The plan's own §20 status note already tried and rejected splitting
  this: "too tightly interconnected... no clean parallel-safe seams," done as one cohesive change by
  design. Consolidating here isn't skipping the rubric — it's exactly what the rubric says to do when
  ≤1 cross-cutting concern claim would be false; this leaf **is** that one cross-cutting concern's
  owner, and every other leaf explicitly excludes orchestrator edits so this is its only writer.
  Sequenced after leaves 1–5 (see 2.1) since it wires their exports in.

### Leaf 7 — Apps Script client-side plugin
- **Covers:** §17 in full (CASH Tools menu, cursor-determines-destination-row transfer semantics,
  sheetId-based rename-safety, dynamic header-name column matching, Setup/Validate/Repair, per-client
  deploy via `scripts/deploy_apps_script.sh`).
- **Files:** `Kowski-Ventures/apps_script/Code.gs`, `scripts/deploy_apps_script.sh`.
- **Rationale:** obviously separate — different runtime entirely (container-bound Google Apps Script,
  not n8n), different repo location, zero file overlap with any other leaf, zero shared external
  integration with the n8n side (it talks to `SpreadsheetApp`/document properties, not the Sheets *API*
  the n8n leaves call). No axis pulls it toward any other leaf.

---

## 2.3 Task-size guardrail

**7 leaves total** (6 n8n-workflow leaves + 1 Apps Script leaf), well under the 16-leaf refusal
threshold — no action needed. Leaf 6 is sequenced after leaves 1–5 due to the real wiring dependency
identified in 2.1, not a same-wave file collision; leaves 1–5 and leaf 7 have no ordering constraint
between them and could run fully in parallel.

## 2.4 Fat-file check

Skipped per instructions — no implementation files exist yet in this exercise's frame.

---

## Leaf list (summary)

| Leaf | Spec section(s) | File(s) | One-sentence rationale |
|---|---|---|---|
| 1 | §2, §3, §3a, §5, §19 Stage A | `envelopeReasons.mjs`, `idempotencyReasons.mjs`, `normalizeReasons.mjs`, `gateReasons.mjs` | One ingest failure domain — Stage A's own code table confirms none of these codes touch downstream deliverable data. |
| 2 | §8 (routing only), §16, §19 Stage B | `caseSheetRoutes.mjs`, Day-1 registration step | Route-correctness is a distinct failure domain from Sheets write-mechanics; Day-1 init just seeds the same table this leaf reads. |
| 3 | §6, §19 Stage C | `folderPathReasons.mjs`, `runtimeReasons.mjs` (Dropbox side) | Single external integration (Dropbox), single archive-delivery failure domain, Stage C codes are all downstream of the same completed Dropbox work. |
| 4 | §8 (write contract), §19 Stage D Sheets codes | Sheets-write branch logic | §19 itself frames Sheets-write failures as affecting "only Sheets... genuinely unaffected already" by Dropbox/routing. |
| 5 | §7 | PrintNode job-construction logic | PrintNode is its own integration; dependency on Dropbox's `direct_url` is a one-way data read, not a shared file/rule-cluster. |
| 6 | §9, §18 Part A, §20 (all) | `classifyDelivery.mjs`, orchestrator wiring file | The plan's own text says this restructure resists splitting ("one wiring graph, no clean parallel-safe seams") — this leaf is the deliberate single owner of that cross-cutting concern. |
| 7 | §17 | `Kowski-Ventures/apps_script/Code.gs`, `scripts/deploy_apps_script.sh` | Entirely separate runtime/repo/integration surface; zero axis overlap with the n8n leaves. |

**Total leaf count: 7.**
