# Fixed finding-category vocabulary (do not invent new ones inline; propose additions in `notes`)

- spec-field-unasserted — a spec-named field/value/behavior has zero test assertion anywhere
- tautology — a test can pass regardless of correct implementation (vacuous, mocked-into-passing, wrong variable)
- umbrella-contradiction — a leaf/shard test contradicts the umbrella or another settled answer
- boundary-dropped — a CORRECT-axis boundary (cardinality, range, reference, existence, time, ordering, conformance) silently untested where the spec pins it
- scale-not-ratio — a scale/perf claim asserted as an absolute number instead of a growth ratio, or not asserted at all
- wrong-severity — the auditor's severity label doesn't match the actual blast radius (e.g. cosmetic marked blocking, or vice versa)
- composition-missing — no interaction/call assertion proving components are actually wired together (state-only check)
- mock-leak — a mock/stub absorbs the very behavior the test claims to verify
- cross-file-conflict — a leaf's spec-compliant work is impossible without a conflicting file only the parent may touch
- other — anything not fitting the above; explain in one sentence
