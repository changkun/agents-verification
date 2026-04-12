# Experiment 03 — Bug-Detection Consensus (Testing as Distributed Consensus)

## Thesis under test

From the blog: *"Rather than single-judge evaluation, multiple independent agents must agree on test pass/fail status. Agent disagreement indicates specification ambiguity rather than test failure."*

Concretely: if we show N agents the same piece of code and ask *"is there a bug?"*, does **agreement on the bug location** correlate with the bug actually being there? And does **disagreement** reliably flag cases where the code is either bug-free or the bug is ambiguous (i.e. an intentional design choice that looks buggy)?

Experiment 01 tested agreement-vs-correctness on questions with a single integer answer. This one tests it on a richer output space — bug presence *plus* localization — which is closer to a realistic code-review workflow.

## Task design

Each trial shows N agents:
1. A code snippet (5–50 lines).
2. A minimal spec describing what the code *should* do.
3. A single question: *"Does the code have a bug? If yes, on which line(s) and what kind? If no, explain why."*

Output format is constrained: agents must emit a JSON object with `{has_bug: bool, lines: [int], kind: str}`.

### Snippet bank (draft)

Mix of four categories, balanced:

| Category | Count | Example |
|----------|-------|---------|
| **Clear bug** | 10 | Off-by-one in array indexing; wrong operator; missing return |
| **Subtle bug** | 10 | Race condition in goroutine; integer overflow at boundary; TOCTOU |
| **No bug, looks buggy** | 10 | Intentional `<=` where `<` looks right; unused-looking variable that's set via reflection |
| **Ambiguous** | 5 | Behavior under edge case not specified — bug only if spec demands that behavior |

Source: curate from QuixBugs, Defects4J, or hand-craft to control difficulty. Pin to git.

### Ground truth

For each snippet: `{has_bug: bool, canonical_lines: [int], category: str}`. Hand-labeled by the experimenter; snippets where the label is contested don't enter the bank.

## Agent configuration

Identical to Experiment 01: homogeneous-Claude, homogeneous-Codex, heterogeneous. Agents run in isolated tempdirs with only the snippet file and spec accessible (no larger codebase context, to keep the signal clean).

## Independent variables

- **Group size**: N ∈ {3, 5, 7}
- **Composition**: {homogeneous-Claude, homogeneous-Codex, heterogeneous}
- **Snippet category**: {clear, subtle, no-bug, ambiguous}
- **Snippets**: 35 total

Trials per (N, composition, snippet): 3. Total: ~2,200 agent invocations.

## Aggregation rule

Three levels of agreement, scored per trial:

1. **Presence agreement**: do all N agree on `has_bug`?
2. **Location agreement**: among those who said "yes", do they agree on `lines`? (±1 line tolerance — real reviewers disagree on exact line)
3. **Kind agreement**: do their `kind` fields cluster? (fuzzy string match or embedding-based clustering, TBD)

Full consensus = all three levels agree.

## Metrics

For each snippet category:

1. **Precision @ unanimous "yes"**: P(bug actually present | all N agents say `has_bug=true` and agree on line).
2. **Recall @ unanimous "yes"**: P(unanimous-yes | bug actually present and in the "clear" or "subtle" category).
3. **False-positive rate @ unanimous "yes"**: P(unanimous-yes | no bug actually present) — crucial for "no bug, looks buggy" category.
4. **Ambiguity detection rate**: on snippets in the "ambiguous" category, does disagreement actually surface? Operationalized as: fraction of ambiguous snippets where no majority-bug-location emerges.

The headline plot: precision-recall curves for bug detection at each consensus threshold (1/N, ⌊N/2⌋+1, N). If the blog's thesis holds, precision should *monotonically increase* with consensus threshold — unanimous agents catch bugs more reliably than single agents.

## Hypotheses

- **H1 (consensus gates false positives)**: False-positive rate on "no bug, looks buggy" snippets drops sharply from N=1 to N=⌈N/2⌉. This is the most practically valuable finding: unanimous-negative is a strong signal.
- **H2 (subtle bugs stay subtle)**: Recall on "subtle" snippets does *not* improve much with N — if a bug requires specialized reasoning, more agents make the same mistake. Correlated failure in action.
- **H3 (ambiguity surfaces as disagreement)**: On "ambiguous" snippets, disagreement rate is measurably higher than on any determinate category. Validates the thesis that disagreement *is* the signal.
- **H4 (heterogeneity helps on subtle bugs specifically)**: Heterogeneous ensembles do better than homogeneous on "subtle" because different model families fail on different bugs. If H2 holds for homogeneous but not heterogeneous, we have the clearest evidence yet for the correlated-failure argument.

## Open questions / known risks

- **Agent tool use**: with `bypassPermissions` / `read-only` sandbox, agents *will* try to run the code. That may give them strictly more information than a human reviewer would get. We want this — it's the realistic case — but report it explicitly.
- **Output parsing**: agents often ignore strict JSON output instructions. Plan for a lenient parser with fallback regex and a "unparseable" category separate from disagreement.
- **Category labels leak**: don't include the category in the prompt. The agent sees code + spec only.
- **Snippet bank bias**: too-easy snippets push every metric toward 1.0; too-hard ones push them toward noise. First pilot on 5 snippets to calibrate difficulty before the full run.

## Deliverable

- `experiments/03_bug_detection.py` — the runner.
- `experiments/snippets/` — 35 directories, each with `code.{go,py}`, `spec.md`, and a sibling `ground_truth.yaml` (gitignored if we plan to publish the bank).
- `results/03_bug_detection.json`.
- `analysis/03_plot.py` — precision-recall curves and ambiguity-detection bar chart.

## Exit criteria

H3 is the critical test. If ambiguous snippets don't produce more disagreement than determinate ones, the "disagreement as signal" thesis fails on this task type — and we need to rethink before building consensus-gated systems on top of it.
