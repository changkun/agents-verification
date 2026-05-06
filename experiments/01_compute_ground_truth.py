"""Compute ground-truth answers for Experiment 01 — Verifiable Consensus.

Pipeline:
  1. Read experiments/questions.example.yaml (or --in <path>).
  2. Clone target_repo into _repo_cache/<repo-name>/ if missing,
     fetch + checkout the pinned ref, resolve to a SHA.
  3. For each question, call its compute_<id> function on the clone.
  4. Write experiments/questions.yaml (or --out <path>) with sha + ground_truth populated.

The compute functions are pure-Python regex passes against gofmt-normalised
Go source. They are deliberately simple and auditable; run with --verbose to
print each match so the experimenter can hand-check the answers before kicking
off the (expensive) consensus runs.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = REPO_ROOT / "_repo_cache"

sys.path.insert(0, str(REPO_ROOT))
from agents_byzantine_tolerance.repo_cache import ensure_repo  # noqa: E402


# ---------- Go source utilities ----------


def strip_go(src: str) -> str:
    """Replace string literal contents and comment contents with spaces.

    Preserves line numbers, brace structure, and most tokens, so regex passes
    don't false-match on text inside strings or comments.
    """
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            out.append("  ")
            i += 2
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if c == "`":
            out.append(c)
            i += 1
            while i < n and src[i] != "`":
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append(src[i])
                i += 1
            continue
        if c == '"':
            out.append(c)
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append("\n" if src[i] == "\n" else " ")
                    i += 1
            if i < n:
                out.append(src[i])
                i += 1
            continue
        if c == "'":
            out.append(c)
            i += 1
            while i < n and src[i] != "'":
                if src[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append(" ")
                    i += 1
            if i < n:
                out.append(src[i])
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def keep_only_comments(src: str) -> str:
    """Inverse of strip_go: keep comment text, blank everything else."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            out.append(c)
            out.append(src[i + 1])
            i += 2
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append(src[i])
                i += 1
            if i < n:
                out.append(src[i])
                out.append(src[i + 1])
                i += 2
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out.append(src[i])
                i += 1
            continue
        if c == "`":
            i += 1
            while i < n and src[i] != "`":
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            if i < n:
                i += 1
            continue
        if c == '"':
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append("\n" if src[i] == "\n" else " ")
                    i += 1
            if i < n:
                i += 1
            continue
        if c == "'":
            i += 1
            while i < n and src[i] != "'":
                if src[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append(" ")
                    i += 1
            if i < n:
                i += 1
            continue
        out.append("\n" if c == "\n" else " ")
        i += 1
    return "".join(out)


def go_files(root: Path, *, include_tests: bool = False) -> list[Path]:
    out = []
    for f in sorted(root.rglob("*.go")):
        if not include_tests and f.name.endswith("_test.go"):
            continue
        out.append(f)
    return out


# ---------- Compute functions ----------


def q01_exported_funcs_first_param_parser(repo: Path, verbose: bool) -> int:
    pat = re.compile(r"^func\s+([A-Z]\w*)\s*\([^,)]*\*Parser[\s,)]", re.MULTILINE)
    count = 0
    for f in sorted((repo / "syntax").glob("*.go")):
        if f.name.endswith("_test.go"):
            continue
        text = strip_go(f.read_text(errors="replace"))
        for m in pat.finditer(text):
            count += 1
            if verbose:
                print(f"  Q01 hit: {f.relative_to(repo)} func {m.group(1)}")
    return count


def _collect_type_names(src: str) -> set[str]:
    names: set[str] = set()
    for m in re.finditer(r"^type\s+([A-Z]\w*)(?:\[[^\]]*\])?\s+\S", src, re.MULTILINE):
        names.add(m.group(1))
    for m in re.finditer(
        r"^type\s+([A-Z]\w*)(?:\[[^\]]*\])?\s*=\s*\S", src, re.MULTILINE
    ):
        names.add(m.group(1))
    in_block = False
    for line in src.split("\n"):
        if re.match(r"^type\s*\(\s*$", line):
            in_block = True
            continue
        if in_block:
            if re.match(r"^\)\s*$", line):
                in_block = False
                continue
            # Members are indented exactly one tab in gofmt output.
            m = re.match(r"^\t([A-Z]\w*)(?:\[[^\]]*\])?\s+\S", line)
            if m:
                names.add(m.group(1))
            else:
                m = re.match(r"^\t([A-Z]\w*)(?:\[[^\]]*\])?\s*=\s*\S", line)
                if m:
                    names.add(m.group(1))
    return names


def q02_exported_types_in_printer_go(repo: Path, verbose: bool) -> int:
    src = strip_go((repo / "syntax" / "printer.go").read_text(errors="replace"))
    names = _collect_type_names(src)
    if verbose:
        for n in sorted(names):
            print(f"  Q02 hit: type {n}")
    return len(names)


def q03_main_go_files_under_cmd(repo: Path, verbose: bool) -> int:
    pat = re.compile(r"^func\s+main\s*\(\s*\)\s*\{", re.MULTILINE)
    count = 0
    for f in sorted((repo / "cmd").rglob("*.go")):
        if f.name.endswith("_test.go"):
            continue
        text = strip_go(f.read_text(errors="replace"))
        if pat.search(text):
            count += 1
            if verbose:
                print(f"  Q03 hit: {f.relative_to(repo)}")
    return count


def q04_test_files_with_t_parallel(repo: Path, verbose: bool) -> int:
    count = 0
    for f in sorted((repo / "syntax").glob("*_test.go")):
        text = f.read_text(errors="replace")
        if "t.Parallel()" in text:
            count += 1
            if verbose:
                print(f"  Q04 hit: {f.relative_to(repo)}")
    return count


def q05_loc_lexer_go(repo: Path, verbose: bool) -> int:
    src = (repo / "syntax" / "lexer.go").read_text(errors="replace")
    in_block = False
    count = 0
    for raw in src.split("\n"):
        s = raw.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if not s:
            continue
        if s.startswith("//"):
            continue
        if s.startswith("/*"):
            if "*/" not in s[2:]:
                in_block = True
            continue
        count += 1
    if verbose:
        print(f"  Q05 lexer.go SLOC: {count}")
    return count


def q06_todo_comment_count(repo: Path, verbose: bool) -> int:
    count = 0
    for f in go_files(repo, include_tests=True):
        text = keep_only_comments(f.read_text(errors="replace"))
        for lineno, line in enumerate(text.split("\n"), 1):
            if "TODO" in line:
                count += 1
                if verbose:
                    print(f"  Q06 hit: {f.relative_to(repo)}:{lineno}")
    return count


def q07_methods_on_runner(repo: Path, verbose: bool) -> int:
    pat = re.compile(r"^func\s*\(\s*(?:\w+\s+)?\*?Runner\s*\)\s+(\w+)", re.MULTILINE)
    count = 0
    for f in sorted((repo / "interp").glob("*.go")):
        if f.name.endswith("_test.go"):
            continue
        text = strip_go(f.read_text(errors="replace"))
        for m in pat.finditer(text):
            count += 1
            if verbose:
                print(f"  Q07 hit: {f.relative_to(repo)} (*Runner).{m.group(1)}")
    return count


def q08_direct_requires_in_go_mod(repo: Path, verbose: bool) -> int:
    text = (repo / "go.mod").read_text(errors="replace")
    direct: set[str] = set()
    in_require = False
    for line in text.split("\n"):
        s = line.strip()
        if not in_require:
            m = re.match(r"^require\s+(\S+)\s+\S+\s*(//.*)?$", s)
            if m:
                if not (m.group(2) and "indirect" in m.group(2)):
                    direct.add(m.group(1))
                continue
            if re.match(r"^require\s*\(\s*$", s):
                in_require = True
                continue
        else:
            if s == ")":
                in_require = False
                continue
            if not s or s.startswith("//"):
                continue
            m = re.match(r"^(\S+)\s+\S+\s*(//.*)?$", s)
            if m:
                if not (m.group(2) and "indirect" in m.group(2)):
                    direct.add(m.group(1))
    if verbose:
        for d in sorted(direct):
            print(f"  Q08 hit: require {d}")
    return len(direct)


def q09_errors_new_calls_in_syntax(repo: Path, verbose: bool) -> int:
    pat = re.compile(r"\berrors\.New\(")
    count = 0
    for f in sorted((repo / "syntax").glob("*.go")):
        if f.name.endswith("_test.go"):
            continue
        text = strip_go(f.read_text(errors="replace"))
        hits = pat.findall(text)
        if hits:
            count += len(hits)
            if verbose:
                print(f"  Q09 hit: {f.relative_to(repo)} x{len(hits)}")
    return count


def q10_exported_consts_in_tokens_go(repo: Path, verbose: bool) -> int:
    src = strip_go((repo / "syntax" / "tokens.go").read_text(errors="replace"))
    names: set[str] = set()
    for m in re.finditer(r"^const\s+([A-Z]\w*)\b", src, re.MULTILINE):
        names.add(m.group(1))
    in_block = False
    for line in src.split("\n"):
        if re.match(r"^const\s*\(\s*$", line):
            in_block = True
            continue
        if in_block:
            if re.match(r"^\)\s*$", line):
                in_block = False
                continue
            m = re.match(r"^\t([A-Z]\w*)\b", line)
            if m:
                names.add(m.group(1))
    if verbose:
        for n in sorted(names):
            print(f"  Q10 hit: const {n}")
    return len(names)


def q11_panic_calls_in_syntax(repo: Path, verbose: bool) -> int:
    pat = re.compile(r"\bpanic\(")
    count = 0
    for f in sorted((repo / "syntax").glob("*.go")):
        if f.name.endswith("_test.go"):
            continue
        text = strip_go(f.read_text(errors="replace"))
        hits = pat.findall(text)
        if hits:
            count += len(hits)
            if verbose:
                print(f"  Q11 hit: {f.relative_to(repo)} x{len(hits)}")
    return count


def q12_subtests_in_syntax_tests(repo: Path, verbose: bool) -> int:
    pat_func = re.compile(
        r"^func\s+(Test\w+)\s*\(\s*\w+\s*\*testing\.T\s*\)\s*\{", re.MULTILINE
    )
    pat_run = re.compile(r"\bt\.Run\(")
    count = 0
    for f in sorted((repo / "syntax").glob("*_test.go")):
        text = strip_go(f.read_text(errors="replace"))
        for m in pat_func.finditer(text):
            start = m.end() - 1
            depth = 0
            i = start
            while i < len(text):
                c = text[i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            body = text[start : i + 1]
            if pat_run.search(body):
                count += 1
                if verbose:
                    print(f"  Q12 hit: {f.relative_to(repo)} {m.group(1)}")
    return count


COMPUTE: dict[str, Callable[[Path, bool], int]] = {
    "q01_exported_funcs_first_param_parser": q01_exported_funcs_first_param_parser,
    "q02_exported_types_in_printer_go": q02_exported_types_in_printer_go,
    "q03_main_go_files_under_cmd": q03_main_go_files_under_cmd,
    "q04_test_files_with_t_parallel": q04_test_files_with_t_parallel,
    "q05_loc_lexer_go": q05_loc_lexer_go,
    "q06_todo_comment_count": q06_todo_comment_count,
    "q07_methods_on_runner": q07_methods_on_runner,
    "q08_direct_requires_in_go_mod": q08_direct_requires_in_go_mod,
    "q09_errors_new_calls_in_syntax": q09_errors_new_calls_in_syntax,
    "q10_exported_consts_in_tokens_go": q10_exported_consts_in_tokens_go,
    "q11_panic_calls_in_syntax": q11_panic_calls_in_syntax,
    "q12_subtests_in_syntax_tests": q12_subtests_in_syntax_tests,
}


# ---------- Main ----------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--in",
        dest="src",
        default=str(REPO_ROOT / "experiments" / "questions.example.yaml"),
    )
    ap.add_argument(
        "--out",
        dest="dst",
        default=str(REPO_ROOT / "experiments" / "questions.yaml"),
    )
    ap.add_argument("--verbose", action="store_true", help="dump per-question matches")
    args = ap.parse_args()

    src_path = Path(args.src)
    dst_path = Path(args.dst)
    bank = yaml.safe_load(src_path.read_text())

    target = bank["target_repo"]
    print(f"[repo] resolving {target['url']}@{target['ref']}")
    cache, sha = ensure_repo(target["url"], target["ref"], CACHE_ROOT)
    print(f"[repo] {target['ref']} -> {sha}")
    target["sha"] = sha

    if bank.get("agent_cwd_subpath"):
        compute_root = cache / bank["agent_cwd_subpath"]
    else:
        compute_root = cache

    print(f"[gt] computing ground truth against {compute_root}")
    failures = 0
    for q in bank["questions"]:
        fn_name = q["compute"]
        fn = COMPUTE.get(fn_name)
        if fn is None:
            print(f"  {q['id']}: NO COMPUTE FUNCTION ({fn_name})")
            failures += 1
            continue
        try:
            answer = fn(compute_root, args.verbose)
        except Exception as exc:  # noqa: BLE001
            print(f"  {q['id']}: ERROR {exc!r}")
            q["ground_truth"] = None
            failures += 1
            continue
        q["ground_truth"] = int(answer)
        print(f"  {q['id']}: {answer}")

    dst_path.write_text(yaml.safe_dump(bank, sort_keys=False, width=80))
    print(f"[gt] wrote {dst_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
