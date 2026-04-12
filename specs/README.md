# Experiment Specs

Each spec describes one self-contained experiment: what it measures, how it's set up, ground truth (if any), and the hypotheses being tested.

Experiments build on each other in this order:

1. **[01-verifiable-consensus.md](01-verifiable-consensus.md)** — baseline. Can N headless coding agents agree on an answer that has objective ground truth? Measures both *liveness* (did they agree?) and *safety* (were they right?), which the blog argues are separable failure modes.

2. **[02-byzantine-injection.md](02-byzantine-injection.md)** — the actual Byzantine case. Seed 1 of N agents with a false premise and measure whether the honest majority wins. Sweeps the honest/Byzantine ratio to find the tolerance curve.

Later experiments (spec-ambiguity detection, partial-agreement maps as a code-review tool) depend on what we learn from these two.
