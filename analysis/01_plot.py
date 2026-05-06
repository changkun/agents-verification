"""Analysis for Experiment 01 — Verifiable Consensus.

Reads results/01_verifiable_consensus.jsonl and emits:
  - analysis/01_summary.md         markdown report of all six metrics
  - analysis/01_headline.png       correctness vs. agreement spread (the test of H2)
  - analysis/01_h1_liveness.png    unanimous rate vs N, by composition (H1)
  - analysis/01_h2_safety.png      P(correct | agreement-level), by composition (H2)
  - analysis/01_h3_composition.png unanimity-vs-correctness, by composition (H3)

Plots are skipped silently if matplotlib isn't importable; the markdown
summary always renders. Run with `--skip-plots` to write only the summary.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "results" / "01_verifiable_consensus" / "smoke.jsonl"


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def safe_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    try:
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        return None


# ---------- Metrics ----------


def cell_metrics(records: list[dict]) -> dict:
    """Compute the six per-cell-bucket metrics from the spec."""
    if not records:
        return {
            "n_cells": 0,
            "unanimous_rate": None,
            "majority_rate": None,
            "p_correct_unanimous": None,
            "p_correct_majority": None,
            "p_any_correct_fragmented": None,
            "disagreement_correlation": None,
        }
    total = len(records)
    unanimous = [r for r in records if r["unanimous"]]
    # Majority = any value held by >= ceil(N/2) agents.
    has_majority = []
    fragmented = []
    for r in records:
        n = r["n"]
        threshold = (n + 1) // 2
        if r["majority_count"] >= threshold:
            has_majority.append(r)
        # "no two agents agreed" — at least two valid answers and no value held
        # by 2+ agents. Failures (parse errors) are excluded from valid_count,
        # so a cell with 4 distinct valid answers + 1 failure still qualifies.
        if r["valid_count"] >= 2 and r["majority_count"] <= 1:
            fragmented.append(r)

    p_correct_unanimous = (
        sum(1 for r in unanimous if r["agreed_correct"]) / len(unanimous)
        if unanimous
        else None
    )
    p_correct_majority = (
        sum(
            1
            for r in has_majority
            if r["majority_value"] is not None and r["majority_value"] == r["ground_truth"]
        )
        / len(has_majority)
        if has_majority
        else None
    )
    p_any_correct_fragmented = (
        sum(1 for r in fragmented if r["any_correct"]) / len(fragmented)
        if fragmented
        else None
    )

    xs, ys = [], []
    for r in records:
        if r["majority_value"] is None or r["ground_truth"] is None:
            continue
        xs.append(r["n_distinct"])
        ys.append(abs(r["majority_value"] - r["ground_truth"]))
    corr = safe_correlation(xs, ys)

    return {
        "n_cells": total,
        "unanimous_rate": len(unanimous) / total,
        "majority_rate": len(has_majority) / total,
        "p_correct_unanimous": p_correct_unanimous,
        "p_correct_majority": p_correct_majority,
        "p_any_correct_fragmented": p_any_correct_fragmented,
        "disagreement_correlation": corr,
    }


def fmt(v: float | None, pct: bool = False, ndigits: int = 2) -> str:
    if v is None:
        return "—"
    if pct:
        return f"{v * 100:.0f}%"
    if isinstance(v, float):
        return f"{v:.{ndigits}f}"
    return str(v)


# ---------- Markdown summary ----------


def write_summary(records: list[dict], out_path: Path) -> None:
    lines: list[str] = []
    lines.append("# Experiment 01 — Verifiable Consensus")
    lines.append("")
    lines.append(f"Total invocations recorded: {sum(len(r['agents']) for r in records)}")
    lines.append(f"Total cells: {len(records)}")
    lines.append("")

    # Overall
    lines.append("## Overall")
    lines.append("")
    overall = cell_metrics(records)
    lines.append(_metrics_table([("all", overall)]))
    lines.append("")

    # By N
    lines.append("## By group size N (H1: liveness)")
    lines.append("")
    by_n = defaultdict(list)
    for r in records:
        by_n[r["n"]].append(r)
    rows = [(f"N={n}", cell_metrics(by_n[n])) for n in sorted(by_n)]
    lines.append(_metrics_table(rows))
    lines.append("")
    lines.append(
        "*H1 prediction: unanimous_rate decreases monotonically as N grows.*"
    )
    lines.append("")

    # By composition
    lines.append("## By composition (H3: heterogeneity)")
    lines.append("")
    by_comp = defaultdict(list)
    for r in records:
        by_comp[r["composition"]].append(r)
    rows = [(c, cell_metrics(by_comp[c])) for c in sorted(by_comp)]
    lines.append(_metrics_table(rows))
    lines.append("")
    lines.append(
        "*H3 prediction: heterogeneous ensembles have LOWER unanimous_rate but "
        "HIGHER p_correct_unanimous than homogeneous ensembles.*"
    )
    lines.append("")

    # By N x composition
    lines.append("## By N × composition")
    lines.append("")
    rows = []
    for n in sorted(by_n):
        for c in sorted(by_comp):
            sub = [r for r in records if r["n"] == n and r["composition"] == c]
            if sub:
                rows.append((f"N={n} {c}", cell_metrics(sub)))
    lines.append(_metrics_table(rows))
    lines.append("")

    # By question (H4)
    lines.append("## By question (H4: question structure)")
    lines.append("")
    by_q = defaultdict(list)
    for r in records:
        by_q[r["question_id"]].append(r)
    rows = [(q, cell_metrics(by_q[q])) for q in sorted(by_q)]
    lines.append(_metrics_table(rows))
    lines.append("")
    lines.append(
        "*H4 prediction: questions requiring interpretation produce more "
        "disagreement (lower unanimous_rate) than mechanically-tractable ones.*"
    )
    lines.append("")

    # H2: correctness conditional on agreement level
    lines.append("## H2: disagreement is signal")
    lines.append("")
    lines.append(
        "Compare: P(correct|unanimous) ≥ P(correct|majority) ≥ P(any|fragmented)?"
    )
    lines.append("")
    o = cell_metrics(records)
    lines.append(
        f"- P(correct | unanimous): **{fmt(o['p_correct_unanimous'], pct=True)}**"
    )
    lines.append(
        f"- P(correct | majority): **{fmt(o['p_correct_majority'], pct=True)}**"
    )
    lines.append(
        f"- P(any correct | fragmented): **{fmt(o['p_any_correct_fragmented'], pct=True)}**"
    )
    lines.append(
        f"- Pearson(distinct values, |majority−gt|): **{fmt(o['disagreement_correlation'])}**"
    )
    lines.append("")

    out_path.write_text("\n".join(lines))


def _metrics_table(rows: list[tuple[str, dict]]) -> str:
    header = (
        "| group | cells | unanimous | majority | P(✓\\|unan) "
        "| P(✓\\|maj) | P(any✓\\|frag) | corr(distinct,err) |"
    )
    sep = (
        "|-------|------:|----------:|---------:|-----------:"
        "|-----------:|----------------:|-------------------:|"
    )
    out = [header, sep]
    for name, m in rows:
        out.append(
            f"| {name} | {m['n_cells']} | "
            f"{fmt(m['unanimous_rate'], pct=True)} | "
            f"{fmt(m['majority_rate'], pct=True)} | "
            f"{fmt(m['p_correct_unanimous'], pct=True)} | "
            f"{fmt(m['p_correct_majority'], pct=True)} | "
            f"{fmt(m['p_any_correct_fragmented'], pct=True)} | "
            f"{fmt(m['disagreement_correlation'])} |"
        )
    return "\n".join(out)


# ---------- Plots ----------


def try_plots(records: list[dict], plot_dir: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    plot_dir.mkdir(parents=True, exist_ok=True)

    # Headline: correctness vs distinct-values bucket.
    buckets: dict[int, list[bool]] = defaultdict(list)
    for r in records:
        if r["ground_truth"] is None or r["majority_value"] is None:
            continue
        buckets[r["n_distinct"]].append(bool(r["agreed_correct"] or r["any_correct"]))
    xs = sorted(buckets)
    ys = [
        sum(buckets[k]) / len(buckets[k]) if buckets[k] else math.nan for k in xs
    ]
    sizes = [len(buckets[k]) for k in xs]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar([str(x) for x in xs], ys, color="#3a7ca5")
    for i, (x, y, s) in enumerate(zip(xs, ys, sizes)):
        ax.text(i, y + 0.02, f"n={s}", ha="center", fontsize=8, color="#333")
    ax.set_xlabel("Distinct values among agents in cell")
    ax.set_ylabel("P(correct answer present in cell)")
    ax.set_title("Headline: correctness vs. agreement spread")
    ax.set_ylim(0, 1.1)
    ax.axhline(0.5, color="gray", linestyle=":", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(plot_dir / "headline.png", dpi=140)
    plt.close(fig)

    # H1: unanimous rate vs N, by composition.
    by_n_comp: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for r in records:
        by_n_comp[(r["n"], r["composition"])].append(r)
    ns = sorted({k[0] for k in by_n_comp})
    comps = sorted({k[1] for k in by_n_comp})
    fig, ax = plt.subplots(figsize=(6, 4))
    for c in comps:
        ys = []
        for n in ns:
            cell = by_n_comp.get((n, c), [])
            ys.append(
                sum(1 for r in cell if r["unanimous"]) / len(cell)
                if cell
                else math.nan
            )
        ax.plot(ns, ys, marker="o", label=c)
    ax.set_xlabel("Group size N")
    ax.set_ylabel("Unanimous agreement rate")
    ax.set_title("H1: liveness vs N, by composition")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "h1_liveness.png", dpi=140)
    plt.close(fig)

    # H2: correctness given agreement level (overall + by composition).
    fig, ax = plt.subplots(figsize=(6, 4))
    levels = ["unanimous", "majority", "fragmented"]
    width = 0.25
    xs_pos = list(range(len(levels)))
    for i, c in enumerate(comps):
        sub = [r for r in records if r["composition"] == c]
        m = cell_metrics(sub)
        ys = [
            m["p_correct_unanimous"] or 0,
            m["p_correct_majority"] or 0,
            m["p_any_correct_fragmented"] or 0,
        ]
        offsets = [x + (i - (len(comps) - 1) / 2) * width for x in xs_pos]
        ax.bar(offsets, ys, width=width, label=c)
    ax.set_xticks(xs_pos)
    ax.set_xticklabels(levels)
    ax.set_ylabel("P(correct)")
    ax.set_title("H2: correctness given agreement level")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "h2_safety.png", dpi=140)
    plt.close(fig)

    # H3: composition trade-off — unanimous_rate vs P(correct | unanimous).
    fig, ax = plt.subplots(figsize=(6, 4))
    for c in comps:
        sub = [r for r in records if r["composition"] == c]
        m = cell_metrics(sub)
        ax.scatter(
            m["unanimous_rate"] or 0,
            m["p_correct_unanimous"] or 0,
            s=80,
            label=c,
        )
    ax.set_xlabel("Unanimous agreement rate")
    ax.set_ylabel("P(correct | unanimous)")
    ax.set_title("H3: heterogeneity is not a free lunch")
    ax.set_xlim(0, 1.05)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "h3_composition.png", dpi=140)
    plt.close(fig)

    return True


# ---------- Main ----------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument(
        "--summary",
        default=None,
        help="output markdown path (default: <input-basename>.summary.md)",
    )
    ap.add_argument(
        "--plot-dir",
        default=None,
        help="output dir for plots (default: <input-basename>.plots/)",
    )
    ap.add_argument("--skip-plots", action="store_true")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"input not found: {in_path}")
        return 1

    records = load(in_path)
    if not records:
        print(f"no records in {in_path}")
        return 1

    summary_path = (
        Path(args.summary)
        if args.summary
        else in_path.with_suffix(".summary.md")
    )
    plot_dir = (
        Path(args.plot_dir)
        if args.plot_dir
        else in_path.with_suffix(".plots")
    )

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    write_summary(records, summary_path)
    print(f"wrote {summary_path}")

    if args.skip_plots:
        return 0
    if try_plots(records, plot_dir):
        print(f"wrote plots in {plot_dir}")
    else:
        print("matplotlib not available; install agents-byzantine-tolerance[plot] for plots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
