"""Panel configuration (panel.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

DEFAULT_PANEL = Path(__file__).resolve().parent / "panel.toml"


@dataclass(frozen=True)
class ExtenderSpec:
    id: str
    harness: str                        # key in harnesses.REGISTRY
    model: str
    enabled: bool = True
    reader: str = "free"                # "free" or "window:<lines>" (max lines per read)
    weight: float = 1.0                 # weight in the panel average
    sample_rate: float = 1.0            # fraction of rollouts this extender scores (expensive auditors < 1)
    seeds: int = 1                      # repeat runs per change request; scores are median-aggregated
    budget_usd: float = 0.8             # per-run spend ceiling (harnesses without one fall back to timeout)
    max_turns: int = 80
    timeout_s: int = 1800
    price_in_per_mtok: float | None = None    # for harnesses that report tokens but not dollars
    price_out_per_mtok: float | None = None
    extra_args: tuple[str, ...] = ()
    env: dict = field(default_factory=dict)
    notes: str = ""

    @property
    def window(self) -> int | None:
        return int(self.reader.split(":", 1)[1]) if self.reader.startswith("window:") else None


@dataclass(frozen=True)
class Panel:
    extenders: tuple[ExtenderSpec, ...]
    prompt_template: str
    total_budget_usd: float = 20.0
    max_parallel: int = 4
    fail_charge: str = "ceiling"        # never-passing tests: "ceiling" (2x group median) or "own" (run's full reading)
    stable_regression: float = 0.98    # a test only counts as passing while >= this share of old tests pass

    @property
    def active(self) -> list[ExtenderSpec]:
        return [e for e in self.extenders if e.enabled]


def load(path: Path | str = DEFAULT_PANEL) -> Panel:
    raw = tomllib.loads(Path(path).read_text())
    defaults = raw.get("defaults", {})
    known = {f.name for f in fields(ExtenderSpec)}
    specs = []
    for e in raw.get("extender", []):
        merged = {**{k: v for k, v in defaults.items() if k in known}, **e}
        unknown = set(merged) - known
        if unknown:
            raise ValueError(f"extender {e.get('id')!r}: unknown keys {sorted(unknown)}")
        merged["extra_args"] = tuple(merged.get("extra_args", ()))
        specs.append(ExtenderSpec(**merged))
    ids = [s.id for s in specs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate extender ids")
    p = raw.get("panel", {})
    return Panel(extenders=tuple(specs), prompt_template=p["prompt_template"],
                 total_budget_usd=p.get("total_budget_usd", 20.0), max_parallel=p.get("max_parallel", 4),
                 fail_charge=p.get("fail_charge", "ceiling"), stable_regression=p.get("stable_regression", 0.98))
