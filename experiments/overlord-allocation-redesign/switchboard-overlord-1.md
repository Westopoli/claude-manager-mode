# Overlord Phase 2 Decomposition — Switchboard TIER 0 Item 1

**Scope**: `_source-strategy-doc.md`, "TIER 0: The #1 Use Case — Class-Targeted Email Campaigns" → "1. Class Roster Sync → Niche Email Campaigns by Class" only. All other sections of the doc (TIER 1+, other TIER 0 items) are explicitly out of scope for this exercise.

Read-only planning exercise. No code written, no sub-agents spawned, no tests run. Treated as a greenfield spec — no implementation files exist yet, so 2.4 (fat-file check) is skipped per the procedure.

---

## 2.1 Dependency map

No `graphify_cmd` available (excerpt-only, no repo access permitted for this exercise) — manual scan of the spec text for distinct impl surfaces, sized so no two slices would touch the same file:

- Calimatic API reads (GetClassesDetailsInfo, GetStudentsListing, GetClassesTypes, GetClassesByTypeCategory)
- Tag derivation from enrollment fields — Layers 1 (active section), 2 (history), 3 (course), 4 (type/category), 6 (temporal), 7 (status) — all pure functions over Calimatic field data
- Tag derivation via topic-mapping lookup — Layer 5 (interest), backed by a Supabase `topic_mapping` table
- Tag derivation for demographics — Layer 8, with an explicit 4-step fallback ladder and a backfill/change-detection path
- Tag lifecycle diff (add/remove logic): ephemeral `active:` add-and-remove-on-drop, permanent `history:`/`interest:` never-remove, `demographics:unknown` removal on backfill
- Parent-vs-student contact resolution (primary contact = parent, matched on phone/email; student data becomes custom fields; multi-class students accumulate tags across calls)
- GHL write integration (upsert contact, apply/remove tags, custom fields)
- Daily sync orchestration (per-campus → per-type → per-class → per-student looping, wiring the above together)

That's 8 file-disjoint candidate slices going into the consolidation pass.

## 2.2 Consolidation pass

Scored on rule-clusters / exception branches / external integrations / cross-cutting concerns, per leaf:

1. **Calimatic ingestion client** — 1 external integration (Calimatic REST API), minimal rule-clusters (endpoint calls + pagination), single failure domain (fetch/shape failures). Stays its own leaf: it's a clean I/O boundary that nothing else should share.

2. **Structural tag derivation (Layers 1, 2, 3, 4, 6, 7)** — 6 rule-clusters, but every one is the same shape ("template a tag string from enrollment fields") and shares one failure domain: a wrong field mapping produces a wrong tag, nothing more. No external integration, no cross-cutting concern of its own. Consolidated into one leaf — splitting 6 near-identical templating rules into 6 leaves would multiply cross-file coordination for zero isolation benefit, which is exactly what 2.2 says not to do ("not by rule count").

3. **Interest tag derivation (Layer 5, topic-mapping)** — same *shape* as leaf 2 (derive a tag) but crosses an external-integration boundary (Supabase `topic_mapping` read) and has its own maintenance failure domain (stale/missing mapping rows, wildcard course-pattern matching, many-to-many course→interest). Split out from leaf 2 because the rubric says split on the integration boundary first, not by rule count.

4. **Demographic tag derivation (Layer 8)** — has its own numbered 4-step fallback ladder (dateOfBirth → gradeLevel → class startAge/endAge → `demographics:unknown`) plus a distinct backfill/change-detection behavior — two separate exception-branch clusters the doc calls out as their own named subsections. Kept as its own leaf: exception-branch density here is materially higher than leaf 2's, and a bug here (wrong age bucket) can't leak into other tag layers, but conflating it with leaf 2 would blur that higher-risk fallback logic into the "trivial templating" leaf.

5. **Tag lifecycle diff engine** (active-tag add/remove-on-drop, history/interest permanence, demographics:unknown resolution-on-backfill) — this is the cross-cutting concern the rubric flags as the dangerous axis: it reaches across leaves 2, 3, and 4's outputs and enforces the permanence/ephemerality rules uniformly. Isolated into its own leaf specifically because a leaf that both derives tags *and* decides what to keep/discard is where compositional bugs (e.g., accidentally pruning a `history:` tag) would hide.

6. **Parent/student contact resolution** — distinct rule cluster (primary-contact-is-parent, match on phone/email, student fields → custom fields, multi-class tag accumulation) with its own failure domain: get this wrong and tags land on the wrong (or a duplicate) contact, independent of whether the tags themselves are correct. The doc gives it its own "Sync Detail" callout, which is the doc-amendment/dedicated-subsection signal the rubric treats as evidence of real coupling risk. Kept separate from both tag derivation and the GHL write leaf.

7. **GHL write integration** — 1 external integration (GHL API: upsert contact, apply/remove tags, custom fields), single failure domain (write/auth/rate-limit failures). Kept separate from Calimatic ingestion (leaf 1) because they're opposite-direction I/O boundaries with no shared rule logic; merging them would mean one leaf owns two unrelated external integrations, over the rubric's "≤2-3 external integrations" ceiling in spirit even though numerically under it — better to keep the read/write halves distinct.

8. **Daily sync orchestration** — the composition layer: per-campus/per-type/per-class/per-student looping that calls leaves 1–7 in sequence. Its own failure domain (partial-sync recovery, ordering, looping bugs) is different in kind from any individual piece it calls, so it isn't folded into any of them.

No leaf ended up owning more than one cross-cutting concern or more than one external integration; leaf 6 and leaf 8 each touch zero external integrations directly (they call into other leaves' clients rather than talking to third parties themselves).

## 2.3 Task-size guardrail

**8 leaves total** — under the 16-leaf hard cap, no refusal triggered, no need to split into sequential waves.

## 2.4 Fat-file check

Skipped — no implementation files exist yet for this spec (greenfield); nothing to estimate LOC against.

---

## Leaf List

| # | Leaf | Plan section(s) covered | Expected file(s) | Consolidation rationale |
|---|------|--------------------------|-------------------|--------------------------|
| 1 | Calimatic ingestion client | "Calimatic Endpoints" (GetClassesDetailsInfo, GetStudentsListing, GetClassesTypes, GetClassesByTypeCategory) | `src/calimatic/client.ts` (or equivalent) | Single external integration, single failure domain (fetch/shape) — clean I/O boundary, nothing else should share it. |
| 2 | Structural tag derivation (Layers 1/2/3/4/6/7) | "GHL Tagging Taxonomy" Layers 1 (active), 2 (history), 3 (course), 4 (type/category), 6 (temporal), 7 (status); "Tag Naming Convention Rules" | `src/tags/deriveStructuralTags.ts` | 6 rule-clusters but identical shape and one failure domain (field→tag templating); splitting by rule count would multiply files for no isolation gain. |
| 3 | Interest tag derivation (Layer 5, topic-mapping) | "Layer 5 — Interest/Topic", the `topic_mapping` table and its maintenance | `src/tags/deriveInterestTags.ts`, `src/supabase/topicMapping.ts` | Crosses an external-integration boundary (Supabase lookup) distinct from leaf 2's pure computation, with its own staleness/maintenance failure domain — split on the integration boundary per the rubric. |
| 4 | Demographic tag derivation (Layer 8) | "Layer 8 — Demographics", "Handling Incomplete Demographics" (4-step fallback), "Backfill strategy" | `src/tags/deriveDemographicTags.ts` | Two named exception-branch subsections (fallback ladder + backfill) with materially higher exception density than leaf 2 — isolating keeps that risk from blurring into the trivial-templating leaf. |
| 5 | Tag lifecycle diff engine | "Remove stale ACTIVE tags on each sync... Never remove HISTORY tags", demographics:unknown backfill removal, status transition detection | `src/sync/tagDiffEngine.ts` | The one true cross-cutting concern (permanence/ephemerality rules applied uniformly across leaves 2–4's outputs) — the rubric's named dangerous axis, isolated so add/remove logic can't hide inside a derivation leaf. |
| 6 | Parent/student contact resolution | "Sync Detail — Parent vs. Student Contacts", "Sync Detail — Handling Multi-Class Students" | `src/contacts/resolveParentContact.ts` | Distinct failure domain (wrong/duplicate contact matched) independent of tag correctness; doc gives it its own dedicated callout, signaling real coupling risk if merged elsewhere. |
| 7 | GHL write integration | Tag application to GHL contacts (implied by "Apply a structured... taxonomy to each student/parent contact", custom field writes) | `src/ghl/client.ts` | Second external integration, opposite I/O direction from leaf 1, own failure domain (write/auth/rate-limit) — kept distinct from the read-side client. |
| 8 | Daily sync orchestration | "How It Works" steps 1–3 (daily sync, per-type/per-class looping, tagging call sequence) | `src/sync/dailyClassRosterSync.ts` | Composition/looping failure domain (partial-sync recovery, ordering) differs in kind from any single piece it wires together; not folded into any dependency. |

**Total leaf count: 8** (guardrail limit is 16 — well under, no refusal, no multi-wave split needed).
