# Experiment 02 — Byzantine Injection

Total cells: 2
Total invocations: 10

## Overall

| group | cells | honest_wins | byz_wins | no_consensus | byz_efficacy |
|-------|------:|------------:|---------:|-------------:|-------------:|
| all | 2 | 100% | 0% | 0% | 33% |

## By f/N (the headline curve)

| group | cells | honest_wins | byz_wins | no_consensus | byz_efficacy |
|-------|------:|------------:|---------:|-------------:|-------------:|
| N=5 f=1 (f/N=0.20) | 1 | 100% | 0% | 0% | 100% |
| N=5 f=2 (f/N=0.40) | 1 | 100% | 0% | 0% | 0% |

Threshold (smallest f/N with honest-majority < 50%): **not crossed**

## By strategy (H1 vs H2)

| group | cells | honest_wins | byz_wins | no_consensus | byz_efficacy |
|-------|------:|------------:|---------:|-------------:|-------------:|
| strong | 2 | 100% | 0% | 0% | 33% |

*H2 prediction: subtle misdirection contaminates at lower f/N than strong-lie.*

## By composition (H3)

| group | cells | honest_wins | byz_wins | no_consensus | byz_efficacy |
|-------|------:|------------:|---------:|-------------:|-------------:|
| homogeneous-claude | 2 | 100% | 0% | 0% | 33% |

*H3 prediction: heterogeneous tolerates higher f/N before contamination.*

## Injection efficacy (sanity)

Fraction of designated Byzantine agents that actually emitted the injected false value (strong-lie strategy only). If this is near zero, the experiment isn't testing what it claims to test.

- Strong-lie efficacy: **33%**
