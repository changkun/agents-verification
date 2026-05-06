# Experiment 03 — Bug-Detection Consensus

Spec: [`specs/03-bug-detection-consensus.md`](../../specs/03-bug-detection-consensus.md)

## Run record

| Run    | Date       | Cells | Records | Cost | Reproducer |
|--------|------------|------:|--------:|------|------------|
| smoke  | 2026-05-06 | 4     | 12      | ~1 min wall | `python experiments/03_bug_detection.py --smoke` |

The spec calls for ~35 snippets across 4 categories (10/10/10/5) × 3 N × 3
compositions × 3 trials ≈ 2,200 invocations. The smoke bank has **one snippet
per category**; expand `experiments/snippets.yaml` before drawing conclusions.

## Smoke configuration

- **Snippets**: 4 (one per category)
  - S01 clear: off-by-one in `IndexLast(s)` → `s[len(s)]`
  - S02 subtle: int32 overflow in `Average(a,b) = (a+b)/2`
  - S03 no-bug-looks-buggy: `Clamp` returning `lo` when `lo>hi` (spec contract)
  - S04 ambiguous: `FormatList([]) -> ""` — empty-list rendering left under-specified
- **N**: 3
- **Composition**: homogeneous-claude
- **Trials**: 1 per cell

## Outcome

| Cell | gt has-bug | Agent presence | Agent lines | Correct? |
|------|:----------:|---------------:|------------:|:------:|
| S01 clear     | true  | [T, T, T] | [[8],[8],[8]] | ✅ |
| S02 subtle    | true  | [T, T, T] | [[5],[5],[5]] | ✅ |
| S03 no-bug    | false | [F, F, F] | [[],[],[]]    | ✅ |
| S04 ambiguous | false | [F, F, F] | [[],[],[]]    | ✅ |

**Headline (with strong caveats)**:

- **All 4 unanimous + correct** with N=3 homogeneous-claude. Encouraging
  signal that the consensus mechanism works on this task type, but four cells
  is far too few to test the spec's hypotheses.
- The **subtle int32-overflow** cell got unanimous-correct in the smoke run.
  H2 (subtle bugs stay subtle as N grows) predicts this would degrade only
  on more deceptive subtle bugs that exploit shared training-data priors.
  S02 is on the easier end of "subtle"; expand the bank with harder cases.
- **H3 not testable from this sample.** All agents said "no bug" on the
  ambiguous snippet — the same answer the implementation gives. To
  surface ambiguity-as-disagreement we need either more agents, a
  heterogeneous ensemble, or a more genuinely contested ambiguity
  (the empty-list rendering question is a soft ambiguity).

## Files

- [`smoke.jsonl`](smoke.jsonl) — raw records: parsed `{has_bug, lines, kind}`
  per agent + per-cell agreement metrics.
- [`smoke.summary.md`](smoke.summary.md) — precision/recall/FPR by category.
- [`smoke.plots/h3_ambiguity.png`](smoke.plots/h3_ambiguity.png) —
  disagreement rate by category. Currently flat at zero everywhere because
  the smoke ensemble unanimously agreed on every cell.

## How to extend

1. **Grow the bank.** The smoke bank has 4 snippets; the spec wants ~35.
   Add adversarial subtle bugs (TOCTOU, unchecked error returns, deceptive
   Boolean ordering) and harder ambiguities.
2. **Heterogeneous composition** is the most direct test of H4 (heterogeneity
   helps on subtle bugs):
   `python experiments/03_bug_detection.py --compositions heterogeneous --ns 5 --trials 3`
3. **Higher N + more trials**: noise floor estimation requires several
   trials per cell.
