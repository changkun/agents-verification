"""Analysis for Experiment 03 — Bug-Detection Consensus.

Reads results/03_bug_detection/*.jsonl and emits markdown summary + plots:
  - precision/recall/false-positive at each consensus threshold by category
  - ambiguity-detection bar chart (disagreement on ambiguous snippets vs others)
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "results" / "03_bug_detection" / "smoke.jsonl"


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def fmt(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.0f}%" if pct else f"{v:.2f}"


def category_metrics(records: list[dict]) -> dict:
    if not records:
        return {"n": 0}
    n = len(records)
    has_bug_gt = sum(1 for r in records if r["ground_truth"]["has_bug"])
    no_bug_gt = n - has_bug_gt
    unanimous_yes = sum(1 for r in records if r["unanimous_yes_aligned"])
    unanimous_no = sum(1 for r in records if r["unanimous_no"])
    correct_majority = sum(1 for r in records if r["correct_presence_majority"])

    # Precision @ unanimous-yes: of cells where agents unanimously said
    # "bug, on these lines", how many were actually buggy.
    precision_unan = (
        sum(
            1
            for r in records
            if r["unanimous_yes_aligned"] and r["ground_truth"]["has_bug"]
        )
        / unanimous_yes
        if unanimous_yes
        else None
    )
    # Recall @ unanimous-yes: of buggy cells, how many got unanimous-yes.
    recall_unan = (
        sum(
            1
            for r in records
            if r["unanimous_yes_aligned"] and r["ground_truth"]["has_bug"]
        )
        / has_bug_gt
        if has_bug_gt
        else None
    )
    # False-positive @ unanimous-yes: of non-buggy cells, how many got
    # unanimous-yes (i.e. the consensus mistakenly flagged a bug).
    fpr_unan = (
        sum(
            1
            for r in records
            if r["unanimous_yes_aligned"] and not r["ground_truth"]["has_bug"]
        )
        / no_bug_gt
        if no_bug_gt
        else None
    )

    # Disagreement rate: fraction of cells where agents disagreed on either
    # presence or location. This is the metric H3 cares about.
    disagreement = sum(
        1
        for r in records
        if (not r["presence_agree"]) or r["line_cluster_count"] > 1
    ) / n

    return {
        "n": n,
        "majority_correct": correct_majority / n,
        "precision_unanimous_yes": precision_unan,
        "recall_unanimous_yes": recall_unan,
        "fpr_unanimous_yes": fpr_unan,
        "disagreement_rate": disagreement,
        "has_bug_gt": has_bug_gt,
        "no_bug_gt": no_bug_gt,
    }


def write_summary(records: list[dict], out_path: Path) -> None:
    lines: list[str] = ["# Experiment 03 — Bug-Detection Consensus", ""]
    lines.append(f"Total cells: {len(records)}")
    lines.append(f"Total invocations: {sum(len(r['agents']) for r in records)}")
    lines.append("")

    lines.append("## Overall")
    lines.append("")
    lines.append(_table([("all", category_metrics(records))]))
    lines.append("")

    lines.append("## By snippet category")
    lines.append("")
    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    rows = [(c, category_metrics(by_cat[c])) for c in sorted(by_cat)]
    lines.append(_table(rows))
    lines.append("")
    lines.append(
        "*H1: false-positive rate @ unanimous-yes should be near zero on "
        "no-bug-looks-buggy. H2: recall on subtle should not improve much "
        "with N. H3: disagreement_rate should be much higher on `ambiguous` "
        "than on the determinate categories.*"
    )
    lines.append("")

    lines.append("## By N × composition")
    lines.append("")
    by_nc = defaultdict(list)
    for r in records:
        by_nc[(r["n"], r["composition"])].append(r)
    rows = [(f"N={n} {c}", category_metrics(by_nc[(n, c)])) for (n, c) in sorted(by_nc)]
    lines.append(_table(rows))
    lines.append("")

    out_path.write_text("\n".join(lines))


def _table(rows: list[tuple[str, dict]]) -> str:
    header = (
        "| group | cells | maj_correct | precision@unan-yes | recall@unan-yes "
        "| fpr@unan-yes | disagreement |"
    )
    sep = "|-------|------:|------------:|-------------------:|---------------:|-------------:|-------------:|"
    out = [header, sep]
    for name, m in rows:
        out.append(
            f"| {name} | {m['n']} | {fmt(m.get('majority_correct'), pct=True)} | "
            f"{fmt(m.get('precision_unanimous_yes'), pct=True)} | "
            f"{fmt(m.get('recall_unanimous_yes'), pct=True)} | "
            f"{fmt(m.get('fpr_unanimous_yes'), pct=True)} | "
            f"{fmt(m.get('disagreement_rate'), pct=True)} |"
        )
    return "\n".join(out)


def try_plots(records: list[dict], plot_dir: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    plot_dir.mkdir(parents=True, exist_ok=True)

    # H3 plot: disagreement by category.
    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    cats = sorted(by_cat)
    ys = [category_metrics(by_cat[c])["disagreement_rate"] for c in cats]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(cats, ys, color="#3a7ca5")
    ax.set_ylabel("Disagreement rate")
    ax.set_title("H3: disagreement should spike on `ambiguous`")
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(plot_dir / "h3_ambiguity.png", dpi=140)
    plt.close(fig)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--summary", default=None)
    ap.add_argument("--plot-dir", default=None)
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
    summary_path = Path(args.summary) if args.summary else in_path.with_suffix(".summary.md")
    plot_dir = Path(args.plot_dir) if args.plot_dir else in_path.with_suffix(".plots")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    write_summary(records, summary_path)
    print(f"wrote {summary_path}")
    if not args.skip_plots and try_plots(records, plot_dir):
        print(f"wrote plots in {plot_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
