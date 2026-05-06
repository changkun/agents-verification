# Experiment 06 — Cascading Hallucination

Total cells: 4

## End-to-end correctness

| condition | visibility | cells | end_to_end |
|-----------|-----------|------:|-----------:|
| clean | every-stage | 1 | 100% |
| clean | first-only | 1 | 100% |
| seeded-subtle | every-stage | 1 | 0% |
| seeded-subtle | first-only | 1 | 0% |

*H2 prediction: every-stage visibility recovers ≥30pp over first-only in seeded conditions.*

## Per-stage correctness

| stage | cells | correct |
|-------|------:|--------:|
| mean | 4 | 50% |
| sum | 4 | 100% |

## Propagation vs correction (seeded conditions only)

When the prior stage's input was the seeded (false) value, did this stage produce the correct output anyway (correction) or a wrong one (propagation)?

| visibility | seeded inputs | propagated wrong | corrected | correction_rate |
|------------|--------------:|-----------------:|----------:|---------------:|
| every-stage | 1 | 1 | 0 | 0% |
| first-only | 1 | 1 | 0 | 0% |
