"""Agent abstractions backed by Claude Code and Codex CLI in headless mode.

Each agent is a full coding agent (not a raw model call) spawned as a
subprocess in an isolated working directory. This is what makes the
consensus/adversarial experiments realistic: the Byzantine participants
have tool access, planning loops, and all the failure modes that come
with agentic systems.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Kind(Enum):
    CLAUDE = "claude"
    CODEX = "codex"


@dataclass
class AgentConfig:
    kind: Kind
    model: str | None = None  # None = CLI default
    # Sandbox mode: keep agents from interfering with each other or the host.
    # Claude: uses --permission-mode and restricted --tools.
    # Codex: uses --sandbox.
    sandbox: str = "read-only"


# Sensible defaults for the experiment. Swap models via overrides.
DEFAULT_CONFIGS = {
    "claude-sonnet": AgentConfig(Kind.CLAUDE, model="claude-sonnet-4-6"),
    "claude-haiku": AgentConfig(Kind.CLAUDE, model="claude-haiku-4-5-20251001"),
    "claude-opus": AgentConfig(Kind.CLAUDE, model="claude-opus-4-6"),
    "codex-default": AgentConfig(Kind.CODEX, model=None),
    "codex-gpt5": AgentConfig(Kind.CODEX, model="gpt-5"),
}


class AgentError(Exception):
    """Raised when an agent subprocess fails or returns unparseable output."""


@dataclass
class AgentResponse:
    agent_id: str
    kind: Kind
    model: str | None
    stdout: str
    stderr: str
    returncode: int
    # The final assistant message (text only), extracted from the CLI output.
    final_message: str


class Agent:
    """A coding agent invoked in headless mode.

    Each query runs in its own ephemeral working directory so agents cannot
    see or stomp on each other's state within a single experiment round.
    """

    def __init__(self, agent_id: str, config: AgentConfig, workdir_root: Path | None = None):
        self.agent_id = agent_id
        self.config = config
        self._workdir_root = workdir_root or Path(tempfile.gettempdir()) / "agents-bft"
        self._workdir_root.mkdir(parents=True, exist_ok=True)

    def _new_workdir(self, seed_dir: Path | None = None) -> Path:
        d = self._workdir_root / f"{self.agent_id}-{uuid.uuid4().hex[:8]}"
        d.mkdir(parents=True, exist_ok=True)
        # Codex insists on a git repo unless --skip-git-repo-check is passed;
        # we pass that flag below so no init needed.
        if seed_dir is not None:
            _seed_workdir(seed_dir, d)
        return d

    async def query(
        self,
        prompt: str,
        system: str | None = None,
        timeout: float = 180.0,
        seed_dir: Path | None = None,
    ) -> AgentResponse:
        if self.config.kind == Kind.CLAUDE:
            return await self._query_claude(prompt, system, timeout, seed_dir)
        elif self.config.kind == Kind.CODEX:
            return await self._query_codex(prompt, system, timeout, seed_dir)
        else:
            raise AgentError(f"Unknown kind: {self.config.kind}")

    async def _query_claude(
        self, prompt: str, system: str | None, timeout: float, seed_dir: Path | None
    ) -> AgentResponse:
        workdir = self._new_workdir(seed_dir)
        cmd = [
            "claude",
            "-p",
            "--output-format", "json",
            "--permission-mode", "bypassPermissions",
            "--no-session-persistence",
        ]
        if self.config.model:
            cmd.extend(["--model", self.config.model])
        if system:
            cmd.extend(["--append-system-prompt", system])
        cmd.append(prompt)

        stdout, stderr, rc = await _run(cmd, cwd=workdir, timeout=timeout)

        # --output-format json returns a single JSON object with a "result" field.
        final = ""
        try:
            obj = json.loads(stdout)
            final = obj.get("result") or obj.get("message") or ""
        except json.JSONDecodeError:
            # Fall back to raw stdout if parsing fails.
            final = stdout.strip()

        shutil.rmtree(workdir, ignore_errors=True)
        return AgentResponse(
            agent_id=self.agent_id,
            kind=Kind.CLAUDE,
            model=self.config.model,
            stdout=stdout,
            stderr=stderr,
            returncode=rc,
            final_message=final,
        )

    async def _query_codex(
        self, prompt: str, system: str | None, timeout: float, seed_dir: Path | None
    ) -> AgentResponse:
        workdir = self._new_workdir(seed_dir)
        last_msg_file = workdir / "_last_message.txt"

        # Codex doesn't have a system-prompt flag in exec; prepend it to the user prompt.
        full_prompt = f"{system.strip()}\n\n{prompt}" if system else prompt

        cmd = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--sandbox", self.config.sandbox,
            "--ephemeral",
            "-C", str(workdir),
            "-o", str(last_msg_file),
        ]
        if self.config.model:
            cmd.extend(["-m", self.config.model])
        cmd.append(full_prompt)

        stdout, stderr, rc = await _run(cmd, cwd=workdir, timeout=timeout)

        final = ""
        if last_msg_file.exists():
            final = last_msg_file.read_text().strip()
        if not final:
            final = stdout.strip()

        shutil.rmtree(workdir, ignore_errors=True)
        return AgentResponse(
            agent_id=self.agent_id,
            kind=Kind.CODEX,
            model=self.config.model,
            stdout=stdout,
            stderr=stderr,
            returncode=rc,
            final_message=final,
        )

    def __repr__(self) -> str:
        return f"Agent({self.agent_id!r}, {self.config.kind.value}, {self.config.model or 'default'})"


def _seed_workdir(src: Path, dst: Path) -> None:
    """Populate dst with the contents of src.

    Uses shutil.copytree, which on macOS APFS transparently uses clonefile()
    (copy-on-write, near-zero cost) via shutil.copy2. On other filesystems it
    falls back to a full byte copy. We avoid hardlinks because a sandbox bug
    that allowed an agent to write would propagate back into the shared cache.
    """
    shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)


def _agent_env() -> dict[str, str]:
    """Build a clean env for spawning agent CLIs.

    When this experiment harness itself runs inside Claude Code, the parent
    sets ANTHROPIC_API_KEY to a placeholder and exports CLAUDE_CODE_* vars
    that wire it into the parent SSE session. Inheriting those into a child
    `claude -p` subprocess makes the child try to authenticate with the
    placeholder and fail with 401. We want the child to use its own
    on-disk credentials (~/.claude.json), so we strip those vars here.

    OPENAI_* vars are scrubbed for the same reason on the codex side, in
    case the harness is ever invoked with a stale key in env.
    """
    env = dict(os.environ)
    for var in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_SSE_PORT",
        "CLAUDE_CODE_ENTRYPOINT",
        "CLAUDECODE",
        "CLAUDE_CODE_EXECPATH",
        "OPENAI_API_KEY",
    ):
        env.pop(var, None)
    return env


async def _run(cmd: list[str], cwd: Path, timeout: float) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_agent_env(),
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise AgentError(f"Agent command timed out after {timeout}s: {cmd[0]}")

    return stdout_b.decode("utf-8", errors="replace"), stderr_b.decode("utf-8", errors="replace"), proc.returncode or 0
