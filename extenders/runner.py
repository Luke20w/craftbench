"""Process plumbing shared by all harnesses: run a CLI while time-stamping every stdout line, and a
polling snapshotter for harnesses that have no tool hooks (snapshots are then lined up with tool
calls by time instead of by call id)."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .nodes import SKIP_DIRS


def stream(cmd: list[str], cwd: Path, stdin: str | None, env: dict | None, timeout_s: int,
           transcript: Path) -> tuple[list[tuple[float, str]], int | None]:
    """Run cmd, return [(arrival time, stdout line)] and the exit code (None on timeout).
    Raw lines go to `transcript`, arrival times to `<transcript>.times`."""
    transcript.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env={**os.environ, **(env or {})})
    if stdin is not None:
        proc.stdin.write(stdin)
        proc.stdin.close()
    lines: list[tuple[float, str]] = []
    err: list[str] = []
    drain = threading.Thread(target=lambda: err.extend(proc.stderr), daemon=True)   # never let stderr fill up
    drain.start()
    timed_out = threading.Event()
    killer = threading.Timer(timeout_s, lambda: (timed_out.set(), proc.kill()))
    killer.start()
    try:
        for line in proc.stdout:
            lines.append((time.time(), line.rstrip("\n")))
    finally:
        killer.cancel()
    code = proc.wait()
    drain.join(timeout=5)
    transcript.write_text("\n".join(l for _, l in lines) + "\n")
    transcript.with_suffix(transcript.suffix + ".times").write_text("\n".join(f"{t:.3f}" for t, _ in lines) + "\n")
    (transcript.parent / "stderr.txt").write_text("".join(err))
    return lines, None if timed_out.is_set() else code


def tree_digest(root: Path) -> str:
    h = hashlib.md5()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and not set(rel.parts) & SKIP_DIRS:
            h.update(str(rel).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


class Poller:
    """Snapshot `root` into `snapdir/<n>` whenever its contents change; records each snapshot's time."""

    def __init__(self, root: Path, snapdir: Path, interval_s: float = 0.5):
        self.root, self.snapdir, self.interval = root, snapdir, interval_s
        self.taken: list[tuple[float, Path]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._last = None

    def __enter__(self):
        self.snapdir.mkdir(parents=True, exist_ok=True)
        self._last = tree_digest(self.root)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        self._check()          # catch the final state

    def _check(self):
        d = tree_digest(self.root)
        if d != self._last:
            self._last = d
            dest = self.snapdir / f"{len(self.taken) + 1:04d}"
            shutil.copytree(self.root, dest, ignore=lambda _, names: [n for n in names if n in SKIP_DIRS])
            self.taken.append((time.time(), dest))

    def _loop(self):
        while not self._stop.wait(self.interval):
            self._check()
