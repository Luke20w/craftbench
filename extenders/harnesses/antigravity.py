"""Google Antigravity CLI (`agy -p --output-format stream-json`). Flags from antigravity.google/docs/cli/headless.
SCAFFOLD: the stream-json event schema is not documented in enough detail to parse tool calls, and we
have no credentials to capture a sample. To finish: run one extender with this command, save stdout,
and fill in parse() from the event names you see (mirror claude_code.parse)."""

from __future__ import annotations

from pathlib import Path

from ..config import ExtenderSpec
from .base import Harness


class Antigravity(Harness):
    name = "antigravity"
    binary = "agy"

    def command(self, spec: ExtenderSpec, workdir: Path, out_dir: Path):
        # Auth for headless use: GEMINI_API_KEY in the environment (spec.env) with modelProvider "gemini".
        # `-p` takes the prompt, so it goes last; the base class appends the prompt after it.
        argv = [self.binary, "--output-format", "stream-json", "--model", spec.model,
                "--dangerously-skip-permissions", "--print-timeout", f"{spec.timeout_s}s", *spec.extra_args, "-p"]
        return argv, {}, False

    def parse(self, lines):
        raise NotImplementedError("antigravity: stream-json tool-call schema not verified yet (see module docstring)")
