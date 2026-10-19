"""OpenCode (`opencode run --format json`). Flags from opencode.ai/docs/cli. Useful for open-weights
readers (e.g. a small model as a stand-in for limited working memory) via provider/model ids.
SCAFFOLD: `--format json` emits NDJSON events, but the docs do not specify how tool calls and results
appear. To finish: capture one run's stdout and fill in parse() (mirror claude_code.parse)."""

from __future__ import annotations

from pathlib import Path

from ..config import ExtenderSpec
from .base import Harness


class OpenCode(Harness):
    name = "opencode"
    binary = "opencode"

    def command(self, spec: ExtenderSpec, workdir: Path, out_dir: Path):
        argv = [self.binary, "run", "--format", "json", "--model", spec.model, "--dir", str(workdir),
                "--auto", *spec.extra_args]
        return argv, {}, False

    def parse(self, lines):
        raise NotImplementedError("opencode: JSON event schema not verified yet (see module docstring)")
