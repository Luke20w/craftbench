def prefix_lines(text: str, first: str, rest: str | None = None) -> str:
    """Prefix the first line of text with `first` and every later line with `rest` (default: `first`).
    Empty lines get the prefix without trailing spaces."""
    rest = first if rest is None else rest
    out = []
    for i, line in enumerate(text.split("\n")):
        prefix = first if i == 0 else rest
        out.append(prefix + line if line else prefix.rstrip())
    return "\n".join(out)
