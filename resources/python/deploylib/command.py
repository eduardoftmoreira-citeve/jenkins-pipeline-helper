from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Mapping, Optional, Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    pass


class CommandRunner:
    """Run commands without a shell so branch and config values cannot become shell code."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def _environment(self, env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
        process_env = os.environ.copy()
        if env:
            process_env.update({str(key): str(value) for key, value in env.items()})
        return process_env

    def run(
        self,
        args: Sequence[str],
        *,
        input_text: Optional[str] = None,
        env: Optional[Mapping[str, str]] = None,
        check: bool = True,
    ) -> CommandResult:
        result = subprocess.run(
            list(args),
            input=input_text,
            text=True,
            capture_output=True,
            env=self._environment(env),
            check=False,
        )
        outcome = CommandResult(result.returncode, result.stdout, result.stderr)
        if check and outcome.returncode != 0:
            command = " ".join([str(args[0]), "…"])
            detail = outcome.stderr.strip() or outcome.stdout.strip() or "no output"
            raise CommandError(f"Command failed ({command}): {detail}")
        return outcome

    def run_to_file(self, args: Sequence[str], destination: Path, *, check: bool = True) -> CommandResult:
        """Stream command stdout into a file without holding a database backup in memory."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            result = subprocess.run(
                list(args),
                stdout=output,
                stderr=subprocess.PIPE,
                env=self._environment(None),
                check=False,
            )
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        outcome = CommandResult(result.returncode, "", stderr)
        if check and outcome.returncode != 0:
            command = " ".join([str(args[0]), "…"])
            detail = outcome.stderr.strip() or "no output"
            raise CommandError(f"Command failed ({command}): {detail}")
        return outcome
