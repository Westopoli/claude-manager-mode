# Test design — boundaries and scale

Read this if you are a **shard-test-writer** (Phase 2.6) or a **test-auditor**
(Phase 3.4). The overlord does not read it, and leaves never see it.

Acceptance criteria describe the happy middle. Left alone, tests written from them
certify the happy middle and nothing else — the two failure classes below both live
outside it, and both have already shipped past this cascade's existing gates.

## Contents

- [The boundary sweep (CORRECT)](#the-boundary-sweep-correct) — the 7 axes to walk
- [The cardinality ladder (ZOM)](#the-cardinality-ladder-zom) — where scale enters
- [BOUNDARIES.md](#boundariesmd) — what you write, and what you escalate
- [Scale assertions](#scale-assertions) — ratio bands and the method that survives parallel spawn
- [Anti-gaming rules](#anti-gaming-rules) — how a scale test gets faked
- [Gotchas](#gotchas) — two real misses from this project
- [Deliberately out of scope](#deliberately-out-of-scope)

---

## The boundary sweep (CORRECT)

Walk these seven axes against every contract symbol in your shard. They are a
recall aid, not a quota — most symbols will have findings on two or three axes and
nothing on the rest.

| Axis | Ask |
|---|---|
| **C**onformance | Does the value match the expected format/shape? Malformed, partially-formed, wrong encoding? |
| **O**rdering | Is the set ordered or unordered as required? What happens when it arrives in the other order? |
| **R**ange | Is the value within min/max? Test min−1, min, max, max+1 — and whether the comparison is `<` or `≤`. |
| **R**eference | Does the code depend on external state it doesn't control? What if that state is absent or stale? |
| **E**xistence | Null, zero, empty string, empty collection, missing key, absent file. |
| **C**ardinality | Zero / one / many — see the ladder below. |
| **T**ime | Ordering in time, timeouts, concurrency, things that expire, timezone and DST edges. |

Range and Existence produce the most findings in this codebase's domain, and Range
is where the recorded miss in [Gotchas](#gotchas) happened.

## The cardinality ladder (ZOM)

Zero → One → Many, in that order. Zero and One are ordinary boundary cases. **Many
is where scale enters** — the same axis, just carried far enough that the algorithm's
growth rate becomes observable.

That is the whole reason scale is handled here rather than as a separate feature:
a quadratic algorithm is not a different kind of bug from an off-by-one, it is the
same axis walked further.

Pick `Many` from the spec's **Scale & Boundary Profile**, not from taste. If that
section says `unbounded-unknown`, assert growth only and no absolute numbers.

## BOUNDARIES.md

Before your tests count as done, write
`.swarm/audits/wave-<wave>/<shard-or-default>/BOUNDARIES.md`. One row per boundary
found:

```markdown
| symbol | axis | boundary | spec says | disposition |
|---|---|---|---|---|
| `reorder_alert` | Range | `stock == threshold` | L44: "below threshold" | test written, cites L44 |
| `reorder_alert` | Existence | `stock is None` | — | question Q2 |
| `build_index`  | Cardinality | N = 50_000 | L61: linear-ish | scale test written |
```

**The disposition rule.** If the spec pins the expected behavior, write the test and
cite the spec line. If the spec is silent, do **not** guess — publish
`.swarm/questions/leaf-NN-Q<n>.md` and let the overlord batch it to the user. A
guessed boundary is a design decision made by a subagent, which is exactly what
splitting test authorship away from implementation exists to prevent. Guessing it
quietly reintroduces the failure mode one layer up.

The auditor reads this file to check that the sweep actually ran, rather than
inferring it from the tests that happen to exist.

## Scale assertions

Required on any leaf whose brief carries `scale_assertions: true`.

**Assert on a ratio, never a duration.** Leaves spawn up to 16-wide in parallel, so
wall-clock is contended and any timing threshold flakes both ways — false RED that
stalls a wave, false GREEN that admits a quadratic. Count operations instead: a
counter is exact, so the bands below hold at N in the thousands rather than needing
millions.

The counting mechanism already exists. Multi-file leaves already carry a
monkeypatch/spy interaction assertion (brief-template.md's mockist rule). A spy is a
call counter — reuse it at two input sizes.

```python
def _ops(n):
    """Ops for a FRESH n-sized input. Fresh matters — see anti-gaming."""
    probe = []
    monkeypatch.setattr(mod, "_compare", _counting(probe, mod._compare))
    subject(make_input(n))
    return len(probe)

def test_index_build_does_not_degrade_quadratically():
    # spec: specs/search.md::Scale & Boundary Profile::AC-7
    assert _ops(4_000) / _ops(2_000) < 3.0     # linear-ish band
```

**The bands.** `r = ops(2N) / ops(N)`, sized at the geometric midpoints between
adjacent complexity classes:

| `growth_claim` | assert | admits | rejects |
|---|---|---|---|
| `sublinear` | `r < 1.5` | O(1)=1.0, O(log n)≈1.10 | O(n)=2.0 |
| `linear-ish` | `r < 3.0` | O(n)=2.0, O(n log n)≈2.20 | O(n²)=4.0 |
| `quadratic-ok` | `r < 6.0` | O(n²)=4.0 | O(n³)=8.0 |

**`linear-ish` deliberately merges O(n) and O(n log n).** Under doubling they sit at
2.00 and 2.20 — 10% apart, which no measurement separates reliably. A test claiming
to tell them apart is asserting noise. These bands detect a *class jump*, which is
the bug that actually ships; they do not classify.

**Measure at the two largest N.** Use at least three sizes (e.g. 1k / 2k / 4k) but
compute the ratio from the top two. Small inputs are dominated by fixed setup cost,
which drags the ratio toward 1.0 and hides real quadratic growth.

## Anti-gaming rules

A scale test that violates any of these can pass while the implementation is still
quadratic:

- **Fresh input per size.** Reusing or extending one dataset lets a memoizing
  implementation answer the second call from cache. Build each N independently.
- **Ratios, never absolute counts.** `assert ops < 5000` pins an implementation
  detail — it breaks on a harmless refactor and says nothing about growth.
- **No test-shaped special cases.** If the implementation can recognize the test's
  exact N or input shape, the test proves nothing. Vary the content, not just the size.
- **Count work, not calls to your own wrapper.** Spy on the operation that actually
  scales (comparisons, row fetches, allocations), not on the entry point, which is
  called once regardless.

## Gotchas

Both of these are real misses from this project, not hypotheticals. Concrete cases
transfer better than general rules, so start here when auditing.

**Range, `<` vs `≤`.** A leaf's brief said a low-stock alert fires below
`threshold`. With `threshold=1`, the test never covered `stock=0`. Neither the
test-writer nor the fresh auditor caught it; only the builder did, incidentally,
while making RED go GREEN — luck, not a gate. Whenever a spec states a comparison in
prose, test the boundary value itself, and state which side it falls on.

**A test that passes for the wrong reason.** A discriminating test for coupon
ordering landed on an exact floating-point tie: `102.5 * 0.93` sits precisely where
`amt*(1-rate)` rounds to `95.32` but the algebraically identical `amt - amt*rate`
rounds to `95.33`. A wrong-order implementation would have passed. The fix was not a
better assertion — it was checking a grid of other input combinations to confirm the
test discriminated generally rather than at one lucky point. When a test is meant to
distinguish two candidate implementations, verify it still distinguishes them away
from the single value you picked.

## Deliberately out of scope

Named here so their absence reads as a decision rather than an oversight:

- **Peak-memory assertions.** Sound in principle, but there is no calibrated
  allocation baseline for this cascade yet, so a threshold would be invented.
- **Wall-clock budgets at leaf level.** Structurally unavailable under parallel
  spawn. Absolute timing belongs to the apex test (Phase 7.1), which runs alone.
