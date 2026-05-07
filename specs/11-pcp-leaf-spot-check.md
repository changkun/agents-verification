# Experiment 11 — Verifier as Spot-Check (PCP-Style Leaf Format)

## Thesis under test

Brown-Cohen, Irving, Piliouras (2023), *Scalable AI Safety via Doubly-Efficient
Debate* ([arXiv:2311.14125](https://arxiv.org/abs/2311.14125)), require the
verifier to read only a polylog-sized portion of the debate trace — the
"verifier-efficient" half of doubly-efficient. Brown-Cohen et al. (2026),
*Debate is Efficient with Your Time*
([arXiv:2602.08630](https://arxiv.org/abs/2602.08630)), formalize this as
**Debate Query Complexity (DQC)** — the minimum bits a judge must inspect
to verify a debate — and prove PSPACE/poly = O(log *n*) DQC.

Spec 07's H5 ("cost-of-attention is real") tests verifier efficiency
informally with freeform prose stakes. This spec tests it formally by
enforcing successively narrower leaf formats and measuring the
soundness/judge-cost Pareto *at fixed task complexity*. Spec 13 measures
the *scaling* of judge cost as *n* grows; spec 11 is the per-snippet
sibling. The empirical question is the Pareto frontier: at what
leaf-narrowness does soundness collapse? Freeform leaves let the Critic
argue anything but make the judge's job harder. Strict tuples make the
judge trivial but may make some attacks unstageable.

## Architecture

Reuse 07a's snippet bank and runner. Add a `leaf_format` knob with three
settings, in order of decreasing expressiveness:

- **freeform** — current 07a stake (prose; judge runs deterministic check
  against extracted fields).
- **strict-tuple** — `{input, expected, actual, violates}`. No prose
  allowed in the stake; the judge parses fields directly. Malformed
  stakes are rejected (counts as no-stake → Proposer wins by default).
- **minimal-tuple** — `{input, expected_property}`. Even narrower; the
  judge runs the input and checks the property. The output is one bit.

A judge that reads `freeform` consumes ~200–800 tokens of stake; a judge
that reads `minimal-tuple` consumes ~30–80. Reading-cost is the headline
efficiency metric.

## Independent variables

- **Leaf format**: {freeform, strict-tuple, minimal-tuple}.
- **Judge mode**: {deterministic, llm-judge}. The interaction is the
  point — strict formats should help the LLM judge most.
- **Honesty**: {both honest, p-byzantine, c-lazy}.
- **Snippet bank**: 07a; trials per cell: 5.

## Comparison baseline

07a freeform + deterministic judge.

## Metrics

1. **Soundness vs leaf format** — primary.
2. **Critic-stake-validity rate** — fraction of debates where the Critic
   produced a well-formed stake. Strict formats may push this down; the
   gap between this and soundness measures the architectural cost of
   the format constraint. *Track this explicitly; if it drops below
   ~50% on minimal-tuple, the format is the binding failure.*
3. **Judge-read tokens** — average tokens the judge actually consumes.
   Should drop sharply across the leaf-format axis. This is the
   verifier-efficiency claim under direct test.
4. **Soundness ÷ judge-read-tokens** — efficiency frontier.
5. **Critic-found-bug rate vs leaf format** — does narrower leaf prevent
   the Critic from staking real bugs?

Headline plot: **soundness vs judge-read-tokens** Pareto frontier, with
Critic-stake-validity overlaid as point-size, faceted by honesty.

## Hypotheses

- **H1 (free headroom for narrowing).** Soundness flat from freeform →
  strict-tuple, drops at minimal-tuple. There is headroom to tighten
  the leaf without cost, but only so much.
- **H2 (verifier-efficiency holds).** Judge-read tokens drop ≥ 5× from
  freeform to strict-tuple at no soundness cost. The doubly-efficient
  property is realizable in this regime.
- **H3 (some bugs unstatable as one property).** Critic-stake-validity
  drops sharply at minimal-tuple — race conditions, off-by-one in loop
  bodies, misuse of stdlib all resist single-property expression.
  Format strangulation, not architectural failure.
- **H4 (strict format defends against laziness).** Under c-lazy, strict
  formats *help* — they force structure that lazy critics otherwise
  skip. Small surprise; would mean strict format is deployable for
  lazy-critic robustness regardless of soundness gain.

## Open questions / known risks

- **Format enforcement is binary.** Strict-tuple parsing must reject
  malformed stakes. Track critic-stake-validity as the binding metric;
  do not let format failures inflate "Proposer wins" without flagging.
- **Coverage holes at minimal-tuple.** Some real bugs cannot be stated
  as `(input, expected_property)`. The minimal-tuple condition will
  reveal which snippet types it can't cover; report the unstatable
  fraction explicitly.
- **Token-counting boundary.** Judge-read tokens count the *stake* the
  judge consumes — not the script that runs the deterministic check.
  Be precise about what "the judge sees" means; otherwise the
  efficiency claim is on shaky measurement.
- **LLM judge × strict format interaction.** A strict-tuple stake gives
  an LLM judge less context to disagree with itself. This may inflate
  llm-judge soundness in a misleading way (the judge has nothing to
  argue with). Compare to deterministic judge soundness as the ceiling.

## Deliverable

- `experiments/11_pcp_leaf.py` — runner.
- `experiments/leaf_schemas.yaml` — three formats, with parser per
  format and unstatable-bug fallback policy.
- `results/11_pcp_leaf/<tag>.jsonl`.
- `analysis/11_plot.py` — soundness vs judge-read-tokens Pareto, with
  critic-stake-validity overlay and unstatable-fraction annotation.

## Exit criteria

- **H1 + H2 hold** → tighter leaves are the architectural improvement,
  not deeper protocols. Productize strict-tuple as the default in
  `latere-ai/debate`.
- **H3 holds strongly** → minimal-tuple kills coverage on real code
  bugs; the PCP analogy doesn't transfer cleanly to this task. Bound
  the productization claim to bug classes that admit single-property
  expression.
- **H4 holds** → strict format is a defense against lazy critics;
  deploy for that reason regardless of soundness gain.

## Cross-references

- **vs 07**: 11 redesigns the leaf 07's H5 only sanity-checks.
- **vs 08**: 08 + 11 together test the two efficiency halves of the
  doubly-efficient theorem (asymmetric-compute robustness +
  verifier polylog).
- **vs 09**: 11's strict-tuple may interact with recursion (some
  sub-claims may be unstatable as tuples). 11 pins the leaf format
  09 should recurse on; run 11 before 09's recursive variant.
- **vs 13**: 11 measures the soundness/cost Pareto at *fixed* *n*;
  13 measures how that cost scales with *n*. 11's recommended leaf
  format becomes 13's leaf input.
