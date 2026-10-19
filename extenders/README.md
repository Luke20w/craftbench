# extenders

A **panel** of frozen coding agents makes the hidden changes, so no single model's reading habits
define "good code". Harnesses: Claude Code (Haiku, Sonnet, Opus), Codex, Antigravity, OpenCode.
Only Claude Code is verified so far.

```
python -m extenders check      # which extenders are installed and authenticated
python -m extenders plan       # commands the panel would run (no model calls)
python -m extenders selftest   # replay recorded scale-test runs (data not included in this repo)
```

- Panel members and cost settings: `panel.toml`
- Add a harness: subclass `harnesses.base.Harness`, implement `command()` and `parse()`, register it
- Not yet validated: Sonnet / Opus as extenders, the windowed reader, any non-Claude harness
- Experimental and not wired into `craftbench` yet: the panel scores each rollout relative to its group's
  median, unlike craftbench's per-rollout reward
