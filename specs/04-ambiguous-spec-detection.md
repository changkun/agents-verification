# Experiment 04 — Ambiguous-Spec Detection via Partial Agreement Maps

## Thesis under test

From the blog: *"Output structured views showing where agents converge versus diverge. Transforms consensus from binary outcome into a gradient map indicating exactly where human attention is needed."*

Practical claim: if you give N agents an **ambiguous specification** and ask them to make concrete design decisions, the *decisions they disagree on* are exactly the ones a human author left under-specified. Disagreement is not noise — it's a structured map of where the spec needs more work.

This is arguably the most immediately useful finding in the whole thesis. It turns multi-agent systems from a reliability problem into a **specification-quality diagnostic**.

## Task design

Each trial shows N agents a short specification and asks them to commit to a fixed set of **design decisions**. The decisions are structured as a checklist filled in by each agent independently — no code, just choices.

### Example: "Build a rate limiter"

Agents must commit to:
- **Algorithm**: {fixed-window, sliding-window, token-bucket, leaky-bucket}
- **Storage**: {in-memory, Redis, SQL, file}
- **Key scope**: {per-IP, per-user, per-API-key, global}
- **Rejection behavior**: {drop, queue, 429-response, custom}
- **Persistence across restarts**: {yes, no}
- **Numeric limits**: exact integer values for rate and burst

For unambiguous specs, most decisions have a "right" answer (or at least a dominant-answer convention). For ambiguous specs, several decisions are genuinely open.

### Spec bank (draft)

Paired specs — each pair covers the same domain, one unambiguous and one deliberately under-specified.

| Pair | Unambiguous version | Ambiguous version |
|------|---------------------|-------------------|
| P1 | "Token-bucket rate limiter, capacity 100, refill 10/sec, per-user, return 429 on reject, in-memory" | "Build a rate limiter" |
| P2 | "LRU cache, capacity 1000, per-thread, drop oldest on overflow, no persistence" | "Build a cache" |
| P3 | "Retry with exponential backoff: 100ms → 10s, max 5 attempts, retry on 5xx and timeout only" | "Retry failed requests" |
| P4 | "Parse RFC-3339 timestamps in UTC, error on ambiguous zones" | "Parse timestamps" |
| P5 | "Idempotency key: UUIDv4 in `Idempotency-Key` header, 24-hour window, rejects duplicates with 409" | "Make this endpoint idempotent" |

Target 8–10 pairs. Each pair has the same decision checklist.

### Ground truth

For each spec, we define the **ambiguity set** — which decisions are objectively under-specified in that spec text — separately from what agents actually produce. The thesis predicts that decisions in the ambiguity set will show high inter-agent disagreement, and decisions outside it will show low disagreement.

## Agent configuration

Same as Experiment 01/02. Agents get only the spec text and the decision checklist. They do *not* see each other's outputs.

## Independent variables

- **Group size**: N ∈ {3, 5, 7}
- **Composition**: {homogeneous-Claude, homogeneous-Codex, heterogeneous}
- **Spec**: 8–10 pairs × 2 versions = 16–20 specs
- **Decisions per spec**: 5–8

Trials per (N, composition, spec): 3. Total: ~1,500 agent invocations.

## Aggregation rule

For each (trial, decision): build the distribution of answers across N agents. Per-decision disagreement score:

- **Entropy** of the answer distribution (normalized to [0,1])
- **Distinct-answer count** (for categorical)
- **Variance** (for numeric)

Trial-level agreement map: heatmap of [decisions × disagreement scores]. This is what we want to show human authors — literally the deliverable the blog proposes.

## Metrics

1. **Per-decision disagreement gap**: mean disagreement(ambiguous spec) − mean disagreement(unambiguous spec), per decision type. Expected sign: positive.
2. **Ambiguity classifier AUC**: treat "was this decision in the author-defined ambiguity set?" as a binary label, and per-decision disagreement score as the predictor. Compute ROC AUC.
3. **Precision @ top-K disagreement**: of the K decisions with highest disagreement, what fraction were in the ambiguity set?
4. **Ensemble-size effect**: does AUC improve as N grows, saturate, or degrade?

The headline plot: ROC curve of disagreement-as-ambiguity-detector, with a separate curve per ensemble composition.

## Hypotheses

- **H1 (primary)**: Per-decision disagreement is **significantly higher** on ambiguous specs than on matched unambiguous specs, holding domain and decision type constant.
- **H2 (AUC threshold)**: Disagreement-as-ambiguity-detector achieves AUC ≥ 0.8 at N=5. If true, this is deployable as a diagnostic.
- **H3 (saturation)**: AUC improves from N=3 to N=5 but saturates by N=7 — matches the blog's claim that homogeneous correlated failures cap the benefit of scale.
- **H4 (heterogeneity sharpens signal)**: Heterogeneous ensembles produce higher AUC than homogeneous, because independent model families disagree *only* on genuinely ambiguous decisions, not on idiosyncratic quirks that correlate within a model family. The clearest pro-heterogeneity evidence in the whole suite, if it holds.
- **H5 (decisions hide in rankings)**: Even on unambiguous specs, some decision types (e.g. "exact numeric values") always show disagreement because the spec is fundamentally under-specified numerically. Raw disagreement is noisy; per-decision-type-normalized disagreement is what actually predicts ambiguity.

## Open questions / known risks

- **Spec pairing is subjective**: "unambiguous" is a fuzzy label. The experimenter's idea of ambiguity may not match the agents'. Mitigation: have a second human independently rate each decision slot, keep only decisions where both raters agree.
- **Numeric decisions always disagree**: "what capacity?" will produce scattered integers even on unambiguous specs. Handle numeric disagreement differently — e.g. coefficient of variation, not entropy.
- **Agent refusal**: some agents may refuse to commit to a choice and instead list options. The checklist format should force commitment; refusals count as "maximum disagreement" with themselves, which is... actually informative. Flag and report separately.
- **Output parsing**: structured output is important here. Use `claude --json-schema` and `codex --output-schema` to enforce the checklist shape.

## Deliverable

- `experiments/04_ambiguous_spec.py` — the runner.
- `experiments/specs/` — the 16–20 paired spec texts + per-spec decision checklists.
- `experiments/ambiguity_labels.yaml` — per-decision ambiguity labels (gitignored).
- `results/04_ambiguous_spec.json`.
- `analysis/04_plot.py` — ROC curve + example agreement-map heatmaps for one ambiguous and one unambiguous spec.

## Exit criteria

If H2 holds (AUC ≥ 0.8), this is the strongest practical result of the suite and worth a standalone writeup. If H1 holds but H2 doesn't reach 0.8, we have an effect but not a deployable tool — still publishable as a measurement of how much disagreement signal exists. If H1 fails, the partial-agreement-map idea needs substantial rework before we build anything on top of it.
