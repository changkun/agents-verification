# Experiment 03 — Bug-Detection Consensus

Total cells: 4
Total invocations: 12

## Overall

| group | cells | maj_correct | precision@unan-yes | recall@unan-yes | fpr@unan-yes | disagreement |
|-------|------:|------------:|-------------------:|---------------:|-------------:|-------------:|
| all | 4 | 100% | 100% | 100% | 0% | 0% |

## By snippet category

| group | cells | maj_correct | precision@unan-yes | recall@unan-yes | fpr@unan-yes | disagreement |
|-------|------:|------------:|-------------------:|---------------:|-------------:|-------------:|
| ambiguous | 1 | 100% | — | — | 0% | 0% |
| clear | 1 | 100% | 100% | 100% | — | 0% |
| no-bug | 1 | 100% | — | — | 0% | 0% |
| subtle | 1 | 100% | 100% | 100% | — | 0% |

*H1: false-positive rate @ unanimous-yes should be near zero on no-bug-looks-buggy. H2: recall on subtle should not improve much with N. H3: disagreement_rate should be much higher on `ambiguous` than on the determinate categories.*

## By N × composition

| group | cells | maj_correct | precision@unan-yes | recall@unan-yes | fpr@unan-yes | disagreement |
|-------|------:|------------:|-------------------:|---------------:|-------------:|-------------:|
| N=3 homogeneous-claude | 4 | 100% | 100% | 100% | 0% | 0% |
