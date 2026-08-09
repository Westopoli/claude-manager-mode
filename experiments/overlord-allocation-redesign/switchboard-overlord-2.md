# Overlord Phase 2 (decomposition/allocation) — dry run

**Scope:** TIER 0 §1 "Class Roster Sync → Niche Email Campaigns by Class" only, from
`/Users/westley/iCodeETL/switchboard/docs/reference/_source-strategy-doc.md` lines 67-295.
No implementation exists yet for this exercise (treated as a fresh spec) — 2.4 (fat-file check)
skipped per procedure. No `graphify_cmd` available — 2.1 done as a manual textual scan.

Independent run — did not coordinate with, or attempt to anticipate, any parallel agent doing
the same exercise.

---

## 2.1 Dependency map (manual scan)

Reading the section as a pipeline, distinct pieces of behavior described:

1. Orchestration order for pulling data from Calimatic (`GetClassesTypes` →
   `GetClassesDetailsInfo` → `GetStudentsListing`, plus `GetClassesByTypeCategory` for grouping).
2. Eight tag-derivation "layers," each a distinct format string built from Calimatic fields:
   Layer 1 (active section), Layer 2 (history), Layer 3 (course), Layer 4 (type/category),
   Layer 5 (interest — via a Supabase `topic_mapping` table lookup), Layer 6 (temporal —
   semester/year bucketing), Layer 7 (status — active/completed/churned/at-risk, requires
   `GetAllStudentUnenrollments` + attendance/payment change detection), Layer 8 (demographics —
   age/grade with a 4-step fallback chain + a backfill/change-detection strategy).
3. Stale-tag reconciliation: remove `active:` tags when a student drops out of a roster;
   **never** remove `history:` tags; a single enrollment record must fan out to *all* applicable
   layers simultaneously (rule #7 under "Tag Naming Convention Rules").
4. GHL-side contact handling: resolve parent-vs-student as the primary contact (matched on
   `parentPhone`/`contactEmail`), store student info as custom fields, then apply the computed
   tag set to that contact.
5. The "Campaign Examples" / "Cross-Sell Matrix" / weekly nurture-sequence tables — these are
   consumption-side GHL saved-search / workflow definitions, explicitly described in the doc as
   things a human configures in GHL UI ("These sequences would be GHL workflows triggered by the
   tag state changes"). **No ETL code owns these** — excluded from the leaf list, not a slice.
6. The `topic_mapping` table itself is manually-maintained reference data (course_pattern →
   interest_tag), not sync logic — treated as owned by whichever leaf reads it (Layer 5).

Proposed impl files, checked pairwise for collisions — none share a file within the wave:

- `src/sync/calimaticRosterSync.ts`
- `src/tags/coreTagBuilder.ts`
- `src/tags/interestMapper.ts`
- `src/tags/statusTagger.ts`
- `src/tags/demographicsTagger.ts`
- `src/sync/tagDiffReconciler.ts`
- `src/ghl/contactAndTagWriter.ts`

Dependency map is clean: 7 disjoint file-owning slices, no two touch the same file in this wave.

---

## 2.2 Consolidation pass (four-axis rubric)

Rubric per candidate, then the merge/split calls:

| Candidate | Rule-clusters | Exception branches | External integrations | Cross-cutting concerns |
|---|---|---|---|---|
| Sync orchestration | fan-out order (types→classes→students) | none | Calimatic API (1) | none — pure orchestration |
| Layers 1,2,3,4,6 (active/history/course/type-category/temporal) | 5 deterministic format-string rules | none (no missing-data branches) | none (all fields already on the record) | must *respect* (not implement) active/history semantics |
| Layer 5 (interest) | course→interest pattern-match table | unmapped course (silent no-tag) | Supabase `topic_mapping` (1) | none |
| Layer 7 (status) | 4 states (active/completed/churned/at-risk) | change-detection vs. prior sync state | Calimatic `GetAllStudentUnenrollments` (1) | none |
| Layer 8 (demographics) | age-group/grade derivation | 4-step fallback chain + backfill-on-new-data | none directly (reads existing record) | backfill/change-detection re-applied over time |
| Stale-tag reconciliation | add/remove decision per tag | never-remove-history exception; multi-layer fan-out per enrollment | none directly | **the** cross-cutting concern — spans all 8 layers |
| GHL contact + tag write | parent-vs-student resolution; multi-class non-clobber | duplicate-contact risk on bad match | GHL API (1) | none beyond "write to this one contact" |

Decisions:

- **Layers 1, 2, 3, 4, 6 → one leaf.** All five are synchronous, deterministic string derivations
  from fields already present on the enrollment/class record — no external calls, no branching on
  missing data. They share one failure domain (a wrong format string in one doesn't corrupt
  another's output). Splitting five near-identical formatting rules into five leaves is leaf-count
  churn with no safety benefit, per the rubric's "share one failure domain" test.
- **Layer 5 (interest) stays separate.** It's the only *tag-derivation* layer with an external
  lookup dependency (Supabase) and a distinct silent-failure mode (unmapped course → dropped
  interest tag, undetectable without dedicated attention). Mixing it into the core builder would
  bury a DB-dependent failure mode inside otherwise-pure logic.
- **Layer 7 (status) stays separate.** It's the only tag layer that requires change-detection
  against prior state plus a second Calimatic endpoint (`GetAllStudentUnenrollments`) and
  attendance/payment thresholds — a genuinely different failure domain (wrong churn detection)
  from static field-formatting.
- **Layer 8 (demographics) stays separate.** Its 4-step fallback chain + backfill state machine is
  its own exception-branch cluster; a bad age inference silently miscategorizes campaign targeting,
  a distinct risk from Layers 1-4/6's straightforward formatting.
- **Stale-tag reconciliation is its own leaf**, not folded into any tag-builder leaf. Per the
  rubric, this is exactly the "dangerous axis" case: a single concern (safe add/remove, esp.
  never-remove-history) that spans every one of the other tag leaves. Isolating it means the one
  place responsible for what-gets-removed is independently auditable; a bug here (accidentally
  stripping a `history:` tag) is the highest-severity bug class in the whole feature and must not
  be smearable across five other leaves' diffs.
- **GHL contact resolution and GHL tag-apply are merged into one leaf**, not split. Both touch a
  single external integration (GHL API) as two steps of one atomic "update this contact" operation
  (resolve-or-create parent, then apply/remove its tag set). Splitting them wouldn't separate
  failure domains — a bad match and a bad tag-write both surface identically as "wrong tags on
  wrong contact" — so keeping them together satisfies "≤2-3 external integrations, one failure
  domain" without inventing a seam the spec doesn't motivate.
- **Campaign-example tables / cross-sell matrix / nurture sequences are not a leaf.** The doc
  itself frames these as GHL-side saved searches and workflows a human sets up, not ETL output.

---

## Leaf list (7 leaves)

**Leaf 1 — Calimatic Roster Sync Orchestrator**
- Covers: "How It Works" steps 1-3 — daily call sequence `GetClassesTypes` →
  `GetClassesDetailsInfo` → `GetStudentsListing`, plus `GetClassesByTypeCategory` for
  type/category grouping.
- Owns: `src/sync/calimaticRosterSync.ts`
- Rationale: single external integration (Calimatic API only), one failure domain (call
  sequencing/pagination), no tag logic — it just produces the enrollment records everything else
  consumes.

**Leaf 2 — Core Deterministic Tag Builder (Layers 1, 2, 3, 4, 6)**
- Covers: active-section tags, history tags, course tags, type/category tags, and
  semester/year temporal tags — all derived directly from fields already on the Calimatic record.
- Owns: `src/tags/coreTagBuilder.ts`
- Rationale: five rule-clusters, zero external integrations, zero exception branches, one shared
  failure domain (string formatting) — textbook case for consolidation rather than a leaf-per-layer
  split.

**Leaf 3 — Interest Tag Mapper (Layer 5)**
- Covers: course→interest pattern matching via the Supabase `topic_mapping` table, including the
  multi-interest-per-course case (e.g. "Robotics with Python").
- Owns: `src/tags/interestMapper.ts` (+ ownership of the `topic_mapping` seed/schema if one is
  needed)
- Rationale: the only tag layer with an external DB lookup and a distinct silent-failure mode
  (unmapped course); kept separate from Leaf 2 so that failure mode isn't buried inside pure logic.

**Leaf 4 — Status Tag Builder (Layer 7)**
- Covers: `status:active/completed/churned/at-risk` derivation, requiring
  `GetAllStudentUnenrollments` plus attendance/payment-based change detection.
- Owns: `src/tags/statusTagger.ts`
- Rationale: distinct external endpoint and its own change-detection-against-prior-state logic —
  a different failure domain (wrong churn/at-risk classification) from static formatting layers.

**Leaf 5 — Demographics Tag Builder (Layer 8)**
- Covers: age-group/grade derivation with the 4-step fallback chain (dateOfBirth → gradeLevel →
  class startAge/endAge → `demographics:unknown`) and the backfill strategy that clears
  `demographics:unknown` when better data later arrives.
- Owns: `src/tags/demographicsTagger.ts`
- Rationale: its own exception-branch cluster (4-step fallback + backfill state machine) with a
  distinct silent-failure mode (bad age inference → wrong campaign targeting); kept separate from
  the other tag layers for the same reason as Leaf 3/4.

**Leaf 6 — Tag Diff / Stale-Removal Reconciler**
- Covers: removing stale `active:` tags when a student no longer appears in a roster, the
  never-remove-`history:` rule, and the "single enrollment fans out to multiple layers
  simultaneously" rule (Tag Naming Convention Rule #7).
- Owns: `src/sync/tagDiffReconciler.ts`
- Rationale: this is the one cross-cutting concern that spans every tag layer built in Leaves 2-5.
  Per the rubric, cross-cutting concerns are the dangerous axis and should be split out rather than
  left implicit in each tag-builder leaf — a bug here (e.g. stripping a `history:` tag) is the
  highest-severity failure mode in the feature and needs one auditable owner.

**Leaf 7 — GHL Contact & Tag Writer**
- Covers: parent-vs-student contact resolution (matched on `parentPhone`/`contactEmail`, student
  info stored as custom fields on the parent), multi-class students correctly accumulating tags
  from multiple sync passes without clobbering, and applying the final computed tag set to GHL.
- Owns: `src/ghl/contactAndTagWriter.ts`
- Rationale: single external integration (GHL API), two steps of one atomic "update this contact"
  operation — a bad match and a bad tag write both surface as "wrong tags on wrong contact," so
  they share a failure domain and don't need separate leaves.

---

## 2.3 Leaf-count guardrail

**7 leaves.** Well under the 16 hard cap — proceed, no action needed.

---

## 2.4 Fat-file check

Skipped — no implementation files exist yet for this spec (per task framing: treated as a fresh
spec, deliverable implementation intentionally not consulted).
