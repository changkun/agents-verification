# Experiment 01 — Verifiable Consensus

Total invocations recorded: 6
Total cells: 2

## Overall

| group | cells | unanimous | majority | P(✓\|unan) | P(✓\|maj) | P(any✓\|frag) | corr(distinct,err) |
|-------|------:|----------:|---------:|-----------:|-----------:|----------------:|-------------------:|
| all | 2 | 100% | 100% | 100% | 100% | — | — |

## By group size N (H1: liveness)

| group | cells | unanimous | majority | P(✓\|unan) | P(✓\|maj) | P(any✓\|frag) | corr(distinct,err) |
|-------|------:|----------:|---------:|-----------:|-----------:|----------------:|-------------------:|
| N=3 | 2 | 100% | 100% | 100% | 100% | — | — |

*H1 prediction: unanimous_rate decreases monotonically as N grows.*

## By composition (H3: heterogeneity)

| group | cells | unanimous | majority | P(✓\|unan) | P(✓\|maj) | P(any✓\|frag) | corr(distinct,err) |
|-------|------:|----------:|---------:|-----------:|-----------:|----------------:|-------------------:|
| homogeneous-claude | 2 | 100% | 100% | 100% | 100% | — | — |

*H3 prediction: heterogeneous ensembles have LOWER unanimous_rate but HIGHER p_correct_unanimous than homogeneous ensembles.*

## By N × composition

| group | cells | unanimous | majority | P(✓\|unan) | P(✓\|maj) | P(any✓\|frag) | corr(distinct,err) |
|-------|------:|----------:|---------:|-----------:|-----------:|----------------:|-------------------:|
| N=3 homogeneous-claude | 2 | 100% | 100% | 100% | 100% | — | — |

## By question (H4: question structure)

| group | cells | unanimous | majority | P(✓\|unan) | P(✓\|maj) | P(any✓\|frag) | corr(distinct,err) |
|-------|------:|----------:|---------:|-----------:|-----------:|----------------:|-------------------:|
| Q01 | 1 | 100% | 100% | 100% | 100% | — | — |
| Q02 | 1 | 100% | 100% | 100% | 100% | — | — |

*H4 prediction: questions requiring interpretation produce more disagreement (lower unanimous_rate) than mechanically-tractable ones.*

## H2: disagreement is signal

Compare: P(correct|unanimous) ≥ P(correct|majority) ≥ P(any|fragmented)?

- P(correct | unanimous): **100%**
- P(correct | majority): **100%**
- P(any correct | fragmented): **—**
- Pearson(distinct values, |majority−gt|): **—**
