# Allocation Pilot v2 — Switchboard TIER 0 §1

Scope read by overlord: `/Users/westley/iCodeETL/switchboard/docs/reference/_source-strategy-doc.md` lines 67-295 (TIER 0 §1, "Class Roster Sync → Niche Email Campaigns by Class") + manager-mode SKILL.md Phase 2.1-2.6 and "Delegated drafting passes."

Per Phase 2.2's delegation authorization, one fresh sub-agent (`general-purpose`, no test framing given) was spawned to draft the consolidation grouping. Its full draft is reproduced below, followed by the overlord's own independent completeness sweep against the section text, then the adopted/corrected final leaf list.

---

## Sub-agent draft (verbatim)

### Leaf 1 — Calimatic Roster Sync Orchestration
Owns: "How It Works" step 1 (daily sync sequence: `GetClassesTypes` → per-type `GetClassesDetailsInfo` → per-class `GetStudentsListing`); the 4 named Calimatic endpoints (lines 79-82); "Sync Detail — Handling Multi-Class Students" (line 285).
Rubric: 1 integration (Calimatic API). 1 rule-cluster (fetch sequencing). No cross-cutting concern of its own.

### Leaf 2 — Tag Naming Convention / Formatting Utility
Owns: "Tag Naming Convention Rules" (lines 273-281, all 7 rules).
Rubric: the cross-cutting concern re-applied across every tag layer (1-8) — isolated as a shared utility consumed by Leaves 3-6. Zero external integrations.

### Leaf 3 — Core Enrollment-State Tags (Layers 1-4) + stale-tag removal
Owns: Layer 1 (active:), Layer 2 (history:), Layer 3 (course:), Layer 4 (type:/category:, sourced from `GetAllStudentEnrollments`'s typeNames/categoryNames); step 3 stale-active removal / never-remove-history rule.
Rubric: 4 rule-clusters, one failure domain (direct field mapping from the same roster record); 1 integration (GHL tag write).

### Leaf 4 — Interest/Topic Mapping (Layer 5)
Owns: Layer 5 entirely — `interest:` derivation via Supabase `topic_mapping` table, wildcard matching, multi-interest mapping, manual-maintenance note, permanence.
Rubric: different mechanism (pattern-match lookup vs. direct field mapping) — split from Leaf 3 for that reason. 2 integrations (Supabase + GHL).

### Leaf 5 — Temporal & Status Tags (Layers 6-7)
Owns: Layer 6 (semester:/year:, Jan-May/Jun-Aug/Sep-Dec), Layer 7 (status:, incl. `GetAllStudentUnenrollments` for churn, attendance/payment at-risk criteria).
Rubric: both derive from time/lifecycle state, distinct from Layer 3's static-field set. 2 integrations.

### Leaf 6 — Demographics (Layer 8) + incomplete-data fallback + backfill
Owns: Layer 8 entirely, the 4-step fallback waterfall, `demographics:unknown` + `demographics_incomplete` flag, backfill strategy.
Rubric: the literal "numbered exception/edge-case section" the rubric calls out; isolated so a fallback bug can't touch simpler layers. 2 integrations.

### Leaf 7 — Contact Resolution: Parent vs. Student
Owns: "Sync Detail — Parent vs. Student Contacts" — parent as primary GHL contact matched on parentPhone or `GetAllStudentEnrollments`'s contactEmail; student info as custom fields on parent; tags applied to parent.
Rubric: a matching bug here would silently misdirect every other leaf's tag output onto the wrong contact — the rubric's "wrong assumption in one silently corrupts another's output" case — so it must be isolated. 1 integration, 1 rule-cluster.

**Draft's own completeness sweep:** Campaign Examples table (217-229) excluded — pure usage examples of tags already produced elsewhere, no new derivation logic. Cross-Sell/Re-Enrollment Matrix + generalization table + sequencing (232-269) excluded and flagged open — spec uses conditional framing ("would be... triggered by... the Supabase diff layer") with no concrete trigger mechanism defined in-section; recommends a follow-up spec pass. Draft totals 7 leaves.

---

## Overlord's independent completeness sweep

Performed by hand against the held section text (lines 67-295), not delegated.

| # | Item | In draft? | Verdict |
|---|---|---|---|
| 1 | Problem framing (73-76) | No owner; treated as context | OK — motivational prose, not a testable requirement |
| 2 | `GetClassesDetailsInfo`, `GetClassesTypes`, `GetStudentsListing` (incl. locationId+classId param) | Leaf 1 | Covered |
| 3 | **`GetClassesByTypeCategory` (line 82)** | Listed under Leaf 1's "4 named endpoints" but never actually invoked by any described sync step, tag layer, or campaign logic in-section | **GAP.** Draft silently folded a dangling endpoint into Leaf 1's ownership list without any leaf actually consuming it, and without an explicit exclusion. Corrected: explicitly excluded (see below), not assigned. |
| 4 | Daily sync steps 1-3 (86-89) | Step 1 → Leaf 1; step 2 (tag in GHL) → Leaves 3-6 collectively; step 3 (stale-active removal, never-remove-history) → Leaf 3 | Covered |
| 5 | Layers 1-4 | Leaf 3 | Covered |
| 6 | `GetAllStudentEnrollments` as source for typeNames/categoryNames (Layer 4) and contactEmail (line 289) | Leaf 3 / Leaf 7 respectively | Covered — draft correctly caught this endpoint isn't in the main bullet list |
| 7 | Layer 5 + topic_mapping table | Leaf 4 | Covered |
| 8 | Layer 6-7, incl. `GetAllStudentUnenrollments` for churn, at-risk criteria (attendance<70% or payment overdue) | Leaf 5 | Covered |
| 9 | Layer 8 + 4-step fallback + backfill + demographics_incomplete flag | Leaf 6 | Covered |
| 10 | Broad campaign inclusion example under Layer 8 (line 209, `age-group OR demographics:unknown AND course`) | Implicitly Leaf 6's territory | OK — usage guidance embedded in the Layer 8 section it owns, no new derivation logic |
| 11 | Campaign Targeting Examples table (217-229) | Excluded by draft, reasoned | Confirmed reasonable exclusion |
| 12 | Cross-Sell/Re-Enrollment Matrix + generalization table + exclusion-filter logic + sequencing (232-269), incl. undefined "Supabase diff layer" trigger | Excluded by draft, reasoned, flagged as needing a follow-up spec pass | Confirmed reasonable exclusion — the trigger mechanism genuinely isn't specified in this section |
| 13 | "The Key Insight" paragraph (283) | No owner; framing | OK — restates the section's value prop, not a new requirement |
| 14 | Multi-Class Students detail (285) | Leaf 1, cross-referenced to Leaf 3 | Covered |
| 15 | Parent vs. Student Contacts detail (287-291) | Leaf 7 | Covered |
| 16 | **Tag Naming Rule 7 (line 281): "a single enrollment generates tags across multiple layers simultaneously"** | Filed under Leaf 2 (a "pure logic, zero external integrations" naming-format utility) | **GAP.** This is not a naming/format rule — it's a cross-cutting *orchestration* invariant spanning Leaf 1 (must invoke every applicable layer-producer per roster record) and Leaves 3-6 (must jointly cover all 8 layers for one enrollment). A formatting-only utility with no integrations cannot itself guarantee this. Misassigned by the draft; needs explicit ownership + a composition-style assertion, not silent inclusion in a naming-convention leaf. |
| 17 | **Tag Naming Rule 6 (line 280): "tags without a lifecycle prefix (course:, type:, status:, etc.) are maintained based on current enrollment state"** | Implicitly under Leaf 2; not restated as in-scope behavior for Leaf 3 (course:/type:/category:) beyond initial derivation | **Partial GAP.** Leaf 3's description only claims the *active:*-removal / never-remove-history behavior explicitly. It never claims responsibility for updating or removing `course:`/`type:`/`category:` tags as enrollment state changes, which Rule 6 implies is required. Leaf 5 already covers this for `status:` via its own "change detection" language, so this gap is specifically Leaf 3's uncovered maintenance semantics. |

**Tally:** 14 of 17 distinct items were correctly and unambiguously covered by the sub-agent's draft (including two good catches: the two off-list Calimatic endpoints buried in prose, and the correct exclusion-with-reason for both the Campaign Examples table and the underspecified Cross-Sell Matrix). 3 gaps found: one fully missing explicit ownership/exclusion (`GetClassesByTypeCategory`), one cross-cutting invariant misassigned to a leaf with no integration surface to actually enforce it (Rule 7), and one partially-uncovered maintenance semantic (Rule 6 vs. Leaf 3's stated scope).

---

## Final leaf list (adopted, with corrections)

1. **Calimatic Roster Sync Orchestration** — as drafted (endpoints `GetClassesTypes`, `GetClassesDetailsInfo`, `GetStudentsListing`; daily sync sequencing; multi-class accumulation). *Added:* explicitly responsible for invoking every applicable tag-layer producer (Leaves 3-6) for each roster record, satisfying Rule 7's "single enrollment → all applicable layers" invariant — this leaf's test needs a composition assertion (per manager-mode's mockist rule) proving it actually calls out to all layer producers, not just fetches data.
2. **Tag Naming Convention / Formatting Utility** — as drafted, scoped strictly to Rules 1-5 (casing, separators, date format, active:/history: prefix semantics, interest: permanence) — pure formatting/lifecycle-prefix logic only. Rule 7 (multi-layer-per-enrollment) reassigned to Leaf 1's ownership per above; Rule 6 (state-maintenance) reassigned in effect to Leaf 3 (below).
3. **Core Enrollment-State Tags (Layers 1-4) + stale-tag removal** — as drafted, *plus* explicit ownership of Rule 6's maintenance semantics for `course:`/`type:`/`category:` tags (update/remove as enrollment state changes, not add-once).
4. **Interest/Topic Mapping (Layer 5)** — as drafted, unchanged.
5. **Temporal & Status Tags (Layers 6-7)** — as drafted, unchanged.
6. **Demographics (Layer 8) + incomplete-data fallback + backfill** — as drafted, unchanged.
7. **Contact Resolution: Parent vs. Student** — as drafted, unchanged.

**Explicitly excluded (with reasons):**
- Campaign Targeting Examples table (217-229) — pure usage examples of already-produced tags; no new derivation logic to build.
- Cross-Sell/Re-Enrollment Matrix + sequencing (232-269) — the only concrete trigger mechanism named ("Supabase diff layer") is not itself specified anywhere in this section; not buildable as written, needs a follow-up spec pass.
- `GetClassesByTypeCategory` endpoint (line 82) — named as available ("for cross-class targeting within a program") but never invoked by any described sync step, tag layer, or campaign logic in this section; not assigned to any leaf pending a future targeting feature that actually specifies its use.

**Total: 7 leaves**, unchanged in count from the draft — the corrections were re-scoping/re-assigning ownership language, not adding or removing leaves. Well under the 16-leaf cap.

---

## Sweep tally

- Items in section: 17 distinct requirements/invariants/open items identified by the overlord's own read.
- Correctly covered by sub-agent's draft: 14.
- Gaps caught by overlord's sweep: 3 — (a) `GetClassesByTypeCategory` silently included with no consuming behavior and no exclusion, (b) Tag Naming Rule 7 misassigned to a no-integration formatting leaf that can't enforce it, (c) Tag Naming Rule 6's tag-maintenance semantics not restated as in-scope for Leaf 3 beyond active:-tag removal.
- Items the draft got outright wrong (as opposed to merely incomplete): 0 — no factual misreadings, just scope/ownership gaps on cross-cutting items.
