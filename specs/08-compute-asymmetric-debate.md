# Experiment 08 — Compute-Asymmetric Debate

## Thesis under test

Brown-Cohen, Irving, Piliouras (2023), *Scalable AI Safety via Doubly-Efficient
Debate* ([arXiv:2311.14125](https://arxiv.org/abs/2311.14125)), prove that
debate soundness holds even when the dishonest player has *exponentially* more
compute than the honest one. This is the headline differentiator from Irving
et al. (2018) and the LLM analog of the BFT-style claim "Byzantine node has
unbounded resources, system still tolerates it."

Specs 02 and 07 hold compute roughly equal — 02 across honest and Byzantine
voters, 07 across Proposer and Critic. Neither tests the asymmetric regime
that the 2023 result actually licenses, and that maps to the realistic
deployment threat: a well-resourced attacker (more tokens, retries, stronger
model) against a cheap honest defender. This spec gives the Byzantine player
{1×, 5×, 10×, 50×} the honest player's inference budget along three orthogonal
axes and measures whether debate soundness stays flat. K-of-N voting at
matched total compute is the head-to-head baseline; the prediction is that
voting collapses while debate stays flat.

## Architecture

Reuse 07a's debate runner. Add per-role compute-budget knobs that operate
along three orthogonal axes (each ablated separately — they are not
combinable into a single "compute ratio"):

- **max_tokens** — multiply the dishonest player's `max_output_tokens` by R.
  Tests whether more rope to argue produces more convincing lies.
- **retries** — at the dishonest player's role, sample R candidate responses
  and submit the highest-scoring one (self-scoring prompt, separate cell).
  Tests best-of-N attack synthesis.
- **model_tier** — the dishonest player gets a stronger model (Haiku → Sonnet
  → Opus on the Claude side; equivalent ladder on Codex). Mixes capability
  and compute, but is the deployment-relevant axis.

## Independent variables

- **Compute axis**: {max_tokens, retries, model_tier} — three separate
  sweeps, not a cross.
- **Compute ratio R**: {1, 5, 10, 50} for max_tokens and retries; {Haiku,
  Sonnet, Opus} for model_tier.
- **Byzantine role**: {proposer, critic} — which side gets the boost.
- **Honesty**: {both honest (boost still applied to one side, no injection),
  p-byzantine, c-lazy}.
- **Snippet bank**: 07a's; trials per cell: 5.

## Comparison baseline

K-of-N voting at total compute = honest_budget + R × honest_budget. At R = 10
with the honest debater = 1 invocation, the matched voting baseline is N = 11
with one Byzantine voter (or N voters with a 10× model upgrade — both
variants worth running). Use spec 02's runner for the voting baseline.

## Metrics

1. **Soundness vs R**, per axis — primary.
2. **Critic-found-bug rate vs R** — does extra critic compute find more
   bugs, or just produce more verbose output?
3. **Byzantine-attack-success rate vs R** — when the Byzantine player has
   the boost, does it construct more convincing lies?
4. **Token cost per debate** at each R — denominator for efficiency claims.
5. **Soundness gap to voting baseline** at matched total compute.

Headline plot: **soundness vs R**, faceted by axis (max_tokens, retries,
model_tier) and honesty, with voting baseline as a horizontal line per facet.

## Hypotheses

- **H1 (debate flat across compute asymmetry).** Debate soundness is flat
  across R for max_tokens and retries when the honest player retains
  adversarial framing. *Note: H1 is now believed to be conditional on
  protocol — Brown-Cohen, Irving, Piliouras (2025) argue plain debate
  is vulnerable to obfuscation under compute asymmetry, and that their
  Prover-Estimator protocol is the structure the 2023 robustness result
  actually requires for LLMs. Spec 12 tests this directly. If 12 shows
  Prover-Estimator beats plain debate under obfuscation × asymmetry,
  rerun 08 under both protocols.*
- **H2 (voting collapses).** Voting soundness drops as R grows, because
  more compute on a Byzantine voter produces more confident wrong answers
  that drive consensus the wrong way.
- **H3 (capability beats budget).** model_tier asymmetry breaks debate
  before max_tokens does — quality of reasoning matters more than length.
  This narrows the 2023 paper's deployment story: debate defends against
  budget asymmetry, not against capability gaps.
- **H4 (lazy critic ceiling).** The C-lazy condition collapses regardless
  of R — lazy critic with 50× budget still doesn't attack. Reuses spec 07
  H6, now under compute pressure.

## Open questions / known risks

- **"Compute" is not a scalar.** The three axes don't compose into a single
  ratio. Report each separately; do not aggregate.
- **model_tier mixes capability and compute.** A stronger model isn't just
  "more compute"; it's also different training data, different RLHF.
  We're measuring the deployment-relevant question, not the theoretical
  one. State this explicitly in writeup.
- **retry-and-pick-best needs a self-scoring prompt** that can itself fail
  or be manipulated. Pilot the scoring prompt before the full sweep; if
  scoring is unreliable, drop the axis or use uniform random selection
  (which is a degenerate "more compute, no smarter" control).
- **Context-limit clamping at 50× max_tokens.** Coding agents may hit
  context limits before the budget is exhausted. Clamp and record actual
  used tokens; report effective ratio.

## Deliverable

- `experiments/08_compute_asymmetric.py` — runner. Takes
  `--axis {max_tokens,retries,model_tier} --ratio R --byz-role {p,c}`.
- `experiments/scoring_prompt.yaml` — self-scoring prompt for the retries
  axis.
- `results/08_compute_asymmetric/<tag>.jsonl`.
- `analysis/08_plot.py` — soundness vs R per axis, with voting baseline.

## Exit criteria

- **H1 + H2 hold** → debate is the architectural choice for compute-
  asymmetric deployment. Strong positive result; productize.
- **H3 isolated** → "stronger model wins"; debate is not an architectural
  defense against capability asymmetry. Redirection finding — the paper's
  deployment relevance is narrower than the theory suggests.
- **H1 fails on max_tokens axis** → debate is not robust to attacker scale.
  The BFT framing of the project's spec 07 narrative needs revision.

## Cross-references

- **vs 02**: 02 holds f/N at fixed compute; 08 adds the asymmetric-compute
  axis 02 holds fixed. Run at matched f/N for clean comparison.
- **vs 07**: 08 reuses 07a's runner; varies what 07 holds equal.
- **vs 09**: 09 varies protocol structure at fixed compute; 08 varies
  compute at fixed protocol. Two probes of the same theorem.
- **vs 11**: leaf format may interact with compute robustness; if 11
  finds strict-tuple changes the soundness baseline, rerun 08 at the new
  baseline.
- **vs 12**: 12 tests whether the protocol structure (plain vs.
  Prover-Estimator) is what makes the 2023 compute-robustness result
  transfer to LLMs. 08's H1 is conditional on 12's outcome.
