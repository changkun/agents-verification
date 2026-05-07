# Experiment Specs

Each spec describes one self-contained experiment: what it measures, how it's set up, ground truth (if any), and the hypotheses being tested.

Thirteen experiments split into three architectures: **parallel consensus** (01–05), where N agents answer the same question independently; **sequential chains** (06), where agents process each other's output; and **adversarial dialectic** (07–13), where two agents debate under an external judge. Specs 08–11 extend 07 along the four axes opened up by Brown-Cohen, Irving, Piliouras (2023), [arXiv:2311.14125](https://arxiv.org/abs/2311.14125) — asymmetric compute (08), depth (09), stochasticity (10), verifier narrowness (11). Spec 12 instantiates the same authors' 2025 follow-up, [arXiv:2506.13609](https://arxiv.org/abs/2506.13609), testing Prover-Estimator debate against the obfuscated-arguments attack. Spec 13 instantiates the 2026 follow-up, [arXiv:2602.08630](https://arxiv.org/abs/2602.08630), measuring whether empirical Debate Query Complexity scales as the theoretical O(log *n*). A separate repo, [latere-ai/debate](https://github.com/latere-ai/debate), holds the tool that productizes architecture 07 and is gated on spec 07a's results.

## Status

| Spec | Implementation | Smoke run | Full run | Results |
|------|----------------|-----------|----------|---------|
| 01 — Verifiable consensus      | ✅ | ✅ 2026-05-06 | ⏳ | [`results/01_verifiable_consensus/`](../results/01_verifiable_consensus/) |
| 02 — Byzantine injection       | ✅ | ✅ 2026-05-06 | ⏳ | [`results/02_byzantine_injection/`](../results/02_byzantine_injection/) |
| 03 — Bug detection             | ✅ | ✅ 2026-05-06 | ⏳ | [`results/03_bug_detection/`](../results/03_bug_detection/) |
| 04 — Ambiguous-spec detection  | ✅ | ✅ 2026-05-06 | ⏳ | [`results/04_ambiguous_spec/`](../results/04_ambiguous_spec/) |
| 05 — Consensus-gated actions   | ✅ | ✅ 2026-05-06 | ⏳ | [`results/05_consensus_gate/`](../results/05_consensus_gate/) |
| 06 — Cascading hallucination   | ✅ | ✅ 2026-05-06 | ⏳ | [`results/06_cascading/`](../results/06_cascading/) |
| 07a — Debate (bug detection)   | ✅ | ✅ 2026-05-06 | ⏳ | [`results/07_debate/`](../results/07_debate/) |
| 07b — Debate (action gating)   | ⏳ | ⏳ | ⏳ | — |
| 07c — Debate (ambiguity)       | ⏳ | ⏳ | ⏳ | — |
| 08 — Compute-asymmetric debate | ⏳ | ⏳ | ⏳ | — |
| 09 — Debate depth / recursion  | ⏳ | ⏳ | ⏳ | — |
| 10 — Stochastic-system soundness | ⏳ | ⏳ | ⏳ | — |
| 11 — Verifier as spot-check (PCP) | ⏳ | ⏳ | ⏳ | — |
| 12 — Prover-Estimator vs obfuscation | ⏳ | ⏳ | ⏳ | — |
| 13 — DQC scaling                | ⏳ | ⏳ | ⏳ | — |

Smoke = end-to-end pipeline check on a tiny config. Full = the spec-prescribed
sweep. Smoke results are **not** sufficient evidence for any of the hypotheses
in the specs; they prove the runner works and produce a small sample for
inspection.

## Parallel-consensus experiments

1. **[01-verifiable-consensus.md](01-verifiable-consensus.md)** — baseline. Can N headless coding agents agree on an answer with objective ground truth? Measures both *liveness* (did they agree?) and *safety* (were they right?), which the blog argues are separable failure modes.

2. **[02-byzantine-injection.md](02-byzantine-injection.md)** — the adversarial case. Seed 1…⌊N/2⌋ agents with false premises and sweep the honest/Byzantine ratio. Does the classical `f < N/3` bound hold for stochastic agents? Does heterogeneity mitigate correlated failure?

3. **[03-bug-detection-consensus.md](03-bug-detection-consensus.md)** — *testing as distributed consensus* (blog approach #2). N agents independently review the same code snippet. Does unanimous agreement correlate with bugs actually being present? Does disagreement flag ambiguous code?

4. **[04-ambiguous-spec-detection.md](04-ambiguous-spec-detection.md)** — *partial agreement maps* (blog approach #3). Pair ambiguous vs. unambiguous specs; measure whether per-decision disagreement reliably identifies which decisions the author left under-specified. The most directly actionable finding if it works.

5. **[05-consensus-gated-actions.md](05-consensus-gated-actions.md)** — *consensus-gated autonomous actions* (blog approach #1). K-of-N approval gate over a mix of safe and destructive proposed actions. Does gating reduce destructive execution without unacceptably blocking safe actions? Sweep K to find the ROC frontier.

## Sequential-chain experiments

6. **[06-cascading-hallucination.md](06-cascading-hallucination.md)** — the other dominant multi-agent pattern. K-stage pipeline where each agent consumes the previous stage's output. Do errors propagate, amplify, or get corrected? Do chains with re-grounding against the source beat chains without? This is where parallel-consensus intuitions break down.

## Adversarial-dialectic experiments

7. **[07-adversarial-debate.md](07-adversarial-debate.md)** — Irving-2018-style debate. Proposer vs. critic across fixed rounds; judge inspects only the staked leaf. Tests the strong claim that soundness needs only one honest player plus a calibrated judge, not honest majority. Provides debate variants of 03 (bug detection), 04 (ambiguity), and 05 (action gating) for head-to-head against voting at equal compute.

8. **[08-compute-asymmetric-debate.md](08-compute-asymmetric-debate.md)** — the Byzantine player gets {1×, 5×, 10×, 50×} the honest player's compute (max-tokens, retry-and-pick-best, model tier). Tests the headline 2023-paper claim — soundness against a much-more-powerful adversary — and the realistic deployment threat that 02/07 don't cover.

9. **[09-debate-depth-recursion.md](09-debate-depth-recursion.md)** — sweep round count {2, 4, 8, 12} on the flat protocol and add a recursive sub-debate variant. Tests whether soundness scales with depth and whether structured recursion beats flat extension at matched compute. Determines the productization path: more rounds vs. structured recursion.

10. **[10-stochastic-system-soundness.md](10-stochastic-system-soundness.md)** — sweep temperature on both players. The smallest, sharpest spec: a necessary-condition check that the 2023 paper's stochastic-AI extension carries over to LLM sampling. A null result licenses the rest of the 07 line; a positive result forces temperature pinning into every prior conclusion.

11. **[11-pcp-leaf-spot-check.md](11-pcp-leaf-spot-check.md)** — enforce successively narrower leaf formats (freeform → strict-tuple → minimal-tuple). Tests the verifier-efficient half of the doubly-efficient property formally — at what leaf-narrowness does soundness collapse, and what's the soundness-vs-judge-read-tokens Pareto frontier?

12. **[12-prover-estimator-obfuscation.md](12-prover-estimator-obfuscation.md)** — Prover-Estimator debate (Brown-Cohen, Irving, Piliouras 2025) head-to-head against plain recursive debate under three attack regimes including a new *obfuscating-tree* injection. Also probes the paper's stability assumption empirically by measuring Estimator score variance across paraphrased sub-claims. Owns the recursive variant that spec 09 ceded.

13. **[13-dqc-scaling.md](13-dqc-scaling.md)** — empirical Debate Query Complexity scaling (Brown-Cohen et al. 2026). Budgeted judge sees only the first *k* tokens of the stake; sweep *k* to find the minimum that preserves soundness. Headline scalar: regression slope of log(k*) vs. log(*n*) — does LLM debate achieve the theoretical O(log *n*) asymptote, or does the curve break under adversaries and only Prover-Estimator restore it?

## Productization

The tool spec that builds on spec 07 lives in a separate repo: [latere-ai/debate](https://github.com/latere-ai/debate). It's gated on this repo's spec 07a returning positive (critic-found-bug rate ≥ 60%); do not build until then.

## Reading order

If you only read two specs: **04** (ambiguous-spec detection — most actionable) and **06** (cascading — where classical BFT intuitions invert). For the architectural alternative to voting, read **07**. 01 is the shared baseline that the others build on. The 08–13 batch is the modern-debate-theory follow-up: **10** is the prerequisite necessary-condition check; **08** is the BFT-flavored compute-asymmetry test; **12** tests the named attack class (obfuscation) and its named defense (Prover-Estimator); **13** is the only spec in the line with a theoretical scaling curve to compare against (DQC = O(log *n*)).

## Execution order (08–13 batch)

Recommended sequencing: **10 → 11 → 12 → 08 → 09 → 13**.

- **10 first.** It's a necessary-condition check (does soundness hold across temperature?). If it fails, every other spec in the batch needs a stochasticity control.
- **11 next.** Pins the leaf format. Both 12 (depth-cap leaf judge) and 13 (k-sweep target) consume 11's recommended format as input.
- **12 third.** Establishes whether Prover-Estimator beats plain debate. 08 and 13 both reference this baseline for their protocol IVs.
- **08 fourth.** Compute-asymmetry test, conditional on 12's protocol outcome (rerun under PE if 12 succeeds).
- **09 fifth.** Flat-K depth study; light-implementation, mostly an empirical reference for 12.
- **13 last.** Needs 11's leaf format and 12's protocol baseline as inputs. Highest-impact spec conceptually (only one with a theoretical scaling curve), but lands last because it composes the others' outputs.
