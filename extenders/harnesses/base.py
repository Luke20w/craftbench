"""Harness adapter interface."""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from bisect import bisect_right
from pathlib import Path

from ..config import ExtenderSpec
from ..events import RunRecord, Snapshot, ToolCall
from ..runner import Poller, stream


class Harness(ABC):
    name: str
    binary: str
    supports_window = False         # can enforce a "window:<N>" reader
    snapshot_mode = "poll"          # "hook" (exact, per tool call) or "poll" (by time)
    verified = False                # transcript parser checked against real output

    def available(self) -> tuple[bool, str]:
        """Is the CLI installed (and, where checkable, authenticated)?"""
        path = shutil.which(self.binary)
        return (True, path) if path else (False, f"`{self.binary}` not on PATH")

    def validate(self, spec: ExtenderSpec) -> None:
        if spec.window and not self.supports_window:
            raise ValueError(f"{spec.id}: harness {self.name} cannot enforce reader {spec.reader!r}")

    @abstractmethod
    def command(self, spec: ExtenderSpec, workdir: Path, out_dir: Path) -> tuple[list[str], dict, bool]:
        """(argv, extra env, prompt_via_stdin)."""

    @abstractmethod
    def parse(self, lines: list[tuple[float, str]]) -> tuple[list[ToolCall], dict]:
        """Tool calls in order, plus meta: cost_usd, stop_reason, turns, tokens."""

    def run(self, spec: ExtenderSpec, prompt: str, workdir: Path, out_dir: Path, seed: int) -> RunRecord:
        self.validate(spec)
        argv, env, via_stdin = self.command(spec, workdir, out_dir)
        if not via_stdin:
            argv = [*argv, prompt]
        transcript = out_dir / "transcript.jsonl"
        snapdir = out_dir / "snaps"
        if self.snapshot_mode == "poll":
            with Poller(workdir, snapdir) as poller:
                lines, _ = stream(argv, workdir, prompt if via_stdin else None, {**spec.env, **env}, spec.timeout_s, transcript)
            calls, meta = self.parse(lines)
            snaps = self._align_by_time(calls, poller.taken)
        else:
            lines, _ = stream(argv, workdir, prompt if via_stdin else None, {**spec.env, **env}, spec.timeout_s, transcript)
            calls, meta = self.parse(lines)
            snaps = self.hook_snapshots(calls, snapdir)
        return RunRecord(extender_id=spec.id, harness=self.name, model=spec.model, seed=seed, workdir=workdir,
                         transcript=transcript, calls=calls, snapshots=snaps, cost_usd=meta.get("cost_usd"),
                         stop_reason=meta.get("stop_reason"), turns=meta.get("turns"), extra=meta)

    def hook_snapshots(self, calls: list[ToolCall], snapdir: Path) -> list[Snapshot]:
        raise NotImplementedError

    @staticmethod
    def _align_by_time(calls: list[ToolCall], taken: list[tuple[float, Path]]) -> list[Snapshot]:
        times = [c.t if c.t is not None else 0.0 for c in calls]
        return [Snapshot(dir=d, after_calls=bisect_right(times, t)) for t, d in taken]

    @staticmethod
    def cost_from_tokens(spec: ExtenderSpec, tokens_in: int, tokens_out: int) -> float | None:
        if spec.price_in_per_mtok is None or spec.price_out_per_mtok is None:
            return None
        return tokens_in / 1e6 * spec.price_in_per_mtok + tokens_out / 1e6 * spec.price_out_per_mtok
