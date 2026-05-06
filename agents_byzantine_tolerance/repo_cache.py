"""Cloning and pinning of target repositories for experiments.

Each experiment seeds agent workdirs from a single cached clone. Pinning
to a SHA (rather than a branch tip) is essential — without pinning, ground
truth computed yesterday could disagree with answers computed today.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def repo_name_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1].removesuffix(".git")


def ensure_repo(url: str, ref: str, cache_root: Path) -> tuple[Path, str]:
    """Clone url into cache_root if needed, check out ref, return (path, sha).

    `ref` may be a tag, branch, or full SHA. The returned SHA is the resolved
    HEAD after checkout; record it in the experiment manifest so subsequent
    runs can verify the cache hasn't drifted.
    """
    cache_root.mkdir(parents=True, exist_ok=True)
    cache = cache_root / repo_name_from_url(url)
    if not (cache / ".git").exists():
        subprocess.run(["git", "clone", "--quiet", url, str(cache)], check=True)
    else:
        subprocess.run(
            ["git", "-C", str(cache), "fetch", "--quiet", "--tags"], check=True
        )
    subprocess.run(
        ["git", "-C", str(cache), "checkout", "--quiet", "--detach", ref], check=True
    )
    sha = subprocess.run(
        ["git", "-C", str(cache), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return cache, sha
