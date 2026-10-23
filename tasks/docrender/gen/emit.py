"""Emit the same rendering rules (cells.py) as differently organized codebases.

    by_kind    one class per node kind, with a method per output format        (cheap to add a kind)
    by_format  one renderer class per output format, with a method per kind    (cheap to add a format)
    flat       one module: render() branches on kind, then on format           (no structure)
    layered    by_format plus registries, factories, middleware, one class per (kind, format) cell
    families   hand-written (families/): by_format, with the shared shape of the line-based markups pulled
               into a base class, so most formats are a handful of settings (defaults: Markdown's)
    families_explicit  the same abstraction, written to be read: every format lists every setting in one
               LineStyle (no inherited defaults), and its own-way shapes separately
"""
from __future__ import annotations

import re
import shutil
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent

CLASS = {"html": "Html", "markdown": "Markdown", "plain": "PlainText", "latex": "Latex", "mediawiki": "MediaWiki",
         "bbcode": "BBCode", "org": "Org", "slack": "Slack", "jira": "Jira", "dokuwiki": "DokuWiki",
         "creole": "Creole", "tiddlywiki": "TiddlyWiki", "asciidoc": "AsciiDoc", "textile": "Textile", "rst": "Rst"}


def camel(kind: str) -> str:
    return "".join(p.capitalize() for p in kind.split("_"))


def replace_call(src: str, name: str, fn) -> str:
    """Replace every NAME(arg) with fn(arg), matching parentheses."""
    out, i = [], 0
    pat = re.compile(r"\b" + name + r"\(")
    while (m := pat.search(src, i)):
        depth, j = 1, m.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(src[j], 0)
            j += 1
        out += [src[i:m.start()], fn(replace_call(src[m.end():j - 1], name, fn))]
        i = j
    return "".join(out) + src[i:]


def body(cell: str, node: str, esc, inl, blk, rend, indent: int) -> str:
    src = textwrap.dedent(cell).strip("\n")
    src = re.sub(r"\bN\b", node, src)
    for name, fn in (("ESC", esc), ("INL", inl), ("BLK", blk), ("R", rend)):
        src = replace_call(src, name, fn)
    return textwrap.indent(src, " " * indent)


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip("\n"))


TEXT_PY = '''
def prefix_lines(text: str, first: str, rest: str | None = None) -> str:
    """Prefix the first line of text with `first` and every later line with `rest` (default: `first`).
    Empty lines get the prefix without trailing spaces."""
    rest = first if rest is None else rest
    out = []
    for i, line in enumerate(text.split("\\n")):
        prefix = first if i == 0 else rest
        out.append(prefix + line if line else prefix.rstrip())
    return "\\n".join(out)
'''

ERRORS_PY = '''
class RenderError(Exception):
    """A document that can't be rendered: unknown format, unknown node type."""
'''

GENERIC_NODES_PY = '''
class Node:
    """A parsed JSON object: its fields become attributes, nested objects become Nodes."""

    def __init__(self, data: dict):
        for key, value in data.items():
            setattr(self, key, build(value))


def build(value):
    if isinstance(value, dict):
        return Node(value)
    if isinstance(value, list):
        return [build(v) for v in value]
    return value
'''

README = """
# docrender

Renders a document, given as a JSON tree on stdin, to a markup format on stdout.

    python docrender.py --to markdown < doc.json

On an unknown format or node type it prints `error: ...` to stderr and exits with status 2.

## Document format

A document is `{"type": "document", "children": [blocks]}`. Every node is an object with a `type`; all
fields shown are required.

Inline nodes:

| type | fields |
|---|---|
| `text` | `value`: string |
| `strong`, `emphasis` | `children`: inlines |
| `code` | `value`: string |
| `link` | `url`: string, `children`: inlines |
| `line_break` | |
| `subscript`, `superscript`, `highlight` | `children`: inlines |
| `kbd` (a key or key combination), `math` (TeX) | `value`: string |

Block nodes:

| type | fields |
|---|---|
| `paragraph` | `children`: inlines |
| `heading` | `level`: 1–6, `children`: inlines |
| `code_block` | `language`: string (may be empty), `code`: string |
| `quote` | `children`: blocks |
| `list` | `ordered`: bool, `items`: list of `{"children": inlines, "sublist": list node or null}` |
| `table` | `header`: list of cells, `rows`: list of rows (lists of cells); a cell is a list of inlines |
| `rule` | |
| `image` | `src`: string, `alt`: string |
| `figure` | `src`: string, `alt`: string, `caption`: inlines |

Blocks are separated by a blank line (a single newline in HTML); the output ends with a newline.
"""


def cli(imports: str, select: str) -> str:
    return f'''
"""Render a JSON document tree to a markup format: python docrender.py --to html < doc.json"""
import argparse
import json
import sys

{imports}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render a JSON document to a markup format.")
    parser.add_argument("--to", required=True, help="output format")
    args = parser.parse_args(argv)
    try:
{textwrap.indent(textwrap.dedent(select).strip(), " " * 8)}
    except (RenderError, json.JSONDecodeError) as e:
        print(f"error: {{e}}", file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# ------------------------------------------------------------------ by_format
def by_format(root: Path, formats: dict, kinds: list[str]) -> None:
    write(root, "docrender.py", cli(
        "from markup.errors import RenderError\nfrom markup.nodes import build\nfrom markup.renderers import RENDERERS",
        """
        renderer = RENDERERS.get(args.to)
        if renderer is None:
            raise RenderError(f"unknown format: {args.to}")
        output = renderer().render(build(json.load(sys.stdin)))
        """))
    write(root, "markup/__init__.py", "")
    write(root, "markup/errors.py", ERRORS_PY)
    write(root, "markup/text.py", TEXT_PY)
    write(root, "markup/nodes.py", GENERIC_NODES_PY)
    write(root, "markup/renderers/base.py", '''
    from ..errors import RenderError


    class Renderer:
        """Renders a node tree in one output format: one method per node type, named after it."""

        separator = "\\n\\n"

        def render(self, node) -> str:
            if node.type == "document":
                return self.blocks(node.children) + "\\n"
            method = getattr(self, node.type, None)
            if method is None:
                raise RenderError(f"unsupported node type: {node.type}")
            return method(node)

        def inlines(self, children) -> str:
            return "".join(self.render(child) for child in children)

        def blocks(self, children) -> str:
            return self.separator.join(self.render(child) for child in children)

        def esc(self, text: str) -> str:
            return text
    ''')
    for fmt, cells in formats.items():
        sub = dict(node="node", esc=lambda a: f"self.esc({a})", inl=lambda a: f"self.inlines({a})",
                   blk=lambda a: f"self.blocks({a})", rend=lambda a: f"self.render({a})")
        parts = [f"from ..text import prefix_lines\nfrom .base import Renderer\n\n\nclass {CLASS[fmt]}Renderer(Renderer):"]
        if cells["separator"] != "\n\n":
            parts.append(f"    separator = {cells['separator']!r}\n")
        parts.append("    def esc(self, text: str) -> str:\n" + body(cells["esc"], indent=8, **sub) + "\n")
        for k in kinds:
            parts.append(f"    def {k}(self, node) -> str:\n" + body(cells[k], indent=8, **sub) + "\n")
        (root / f"markup/renderers/{fmt}.py").write_text("\n".join(parts).rstrip() + "\n")
    imports = "\n".join(f"from .{fmt} import {CLASS[fmt]}Renderer" for fmt in formats)
    table = "\n".join(f'    "{fmt}": {CLASS[fmt]}Renderer,' for fmt in formats)
    (root / "markup/renderers/__init__.py").write_text(f"{imports}\n\nRENDERERS = {{\n{table}\n}}\n")


# ------------------------------------------------------------------ by_kind
def by_kind(root: Path, formats: dict, kinds: list[str]) -> None:
    write(root, "docrender.py", cli(
        "from markup.errors import RenderError\nfrom markup.formats import FORMATS\nfrom markup.nodes import build",
        """
        if args.to not in FORMATS:
            raise RenderError(f"unknown format: {args.to}")
        output = build(json.load(sys.stdin)).render(args.to)
        """))
    write(root, "markup/__init__.py", "")
    write(root, "markup/errors.py", ERRORS_PY)
    write(root, "markup/text.py", TEXT_PY)
    esc_funcs = "\n\n".join(f"def escape_{fmt}(text: str) -> str:\n" + body(c["esc"], "node", None, None, None, None, 4)
                            for fmt, c in formats.items())
    escapes = "\n".join(f'    "{fmt}": escape_{fmt},' for fmt in formats)
    seps = "\n".join(f'    "{fmt}": {c["separator"]!r},' for fmt, c in formats.items())
    (root / "markup/formats.py").write_text(f'''"""Output formats: how each escapes text and separates blocks. Nodes render themselves (see nodes/)."""


{esc_funcs}


ESCAPES = {{
{escapes}
}}

SEPARATORS = {{
{seps}
}}

FORMATS = list(ESCAPES)


def escape(text: str, fmt: str) -> str:
    return ESCAPES[fmt](text)


def inlines(children, fmt: str) -> str:
    return "".join(child.render(fmt) for child in children)


def blocks(children, fmt: str) -> str:
    return SEPARATORS[fmt].join(child.render(fmt) for child in children)
''')
    write(root, "markup/nodes/base.py", '''
    from ..errors import RenderError

    NODE_TYPES: dict[str, type] = {}


    def node_type(name: str):
        """Register a Node subclass as the class for JSON objects with this `type`."""
        def register(cls):
            cls.type = name
            NODE_TYPES[name] = cls
            return cls
        return register


    class Record:
        """A JSON object without a `type` (e.g. a list item): its fields become attributes."""

        def __init__(self, data: dict):
            for key, value in data.items():
                setattr(self, key, build(value))


    class Node(Record):
        """A document node. Subclasses render themselves with one `to_<format>` method per output format."""

        type = ""

        def __init__(self, data: dict):
            super().__init__({k: v for k, v in data.items() if k != "type"})

        def render(self, fmt: str) -> str:
            method = getattr(self, "to_" + fmt, None)
            if method is None:
                raise RenderError(f"{self.type} nodes can't be rendered as {fmt}")
            return method()


    def build(value):
        if isinstance(value, dict):
            if "type" not in value:
                return Record(value)
            cls = NODE_TYPES.get(value["type"])
            if cls is None:
                raise RenderError(f"unsupported node type: {value['type']}")
            return cls(value)
        if isinstance(value, list):
            return [build(v) for v in value]
        return value
    ''')
    write(root, "markup/nodes/document.py", '''
    from ..formats import blocks
    from .base import Node, node_type


    @node_type("document")
    class Document(Node):
        def render(self, fmt: str) -> str:
            return blocks(self.children, fmt) + "\\n"
    ''')
    for k in kinds:
        methods = []
        for fmt, cells in formats.items():
            sub = dict(node="self", esc=lambda a, f=fmt: f'escape({a}, "{f}")', inl=lambda a, f=fmt: f'inlines({a}, "{f}")',
                       blk=lambda a, f=fmt: f'blocks({a}, "{f}")', rend=lambda a, f=fmt: f'{a}.render("{f}")')
            methods.append(f"    def to_{fmt}(self) -> str:\n" + body(cells[k], indent=8, **sub) + "\n")
        src = "\n".join(methods)
        helpers = [h for h in ("blocks", "escape", "inlines") if re.search(rf"\b{h}\(", src)]
        head = f"from ..formats import {', '.join(helpers)}\n" if helpers else ""
        head += "from ..text import prefix_lines\n" if "prefix_lines(" in src else ""
        head += f"from .base import Node, node_type\n\n\n@node_type(\"{k}\")\nclass {camel(k)}(Node):\n"
        (root / f"markup/nodes/{k}.py").write_text((head + src).rstrip() + "\n")
    imports = "\n".join(f"from .{k} import {camel(k)}" for k in ["document", *kinds])
    names = ", ".join(f'"{n}"' for n in ["NODE_TYPES", "build", *(camel(k) for k in ["document", *kinds])])
    (root / "markup/nodes/__init__.py").write_text(f"from .base import NODE_TYPES, build\n{imports}\n\n__all__ = [{names}]\n")


# ------------------------------------------------------------------ flat
def flat(root: Path, formats: dict, kinds: list[str]) -> None:
    sub = dict(node="node", esc=lambda a: f"escape({a}, fmt)", inl=lambda a: f"render_inlines({a}, fmt)",
               blk=lambda a: f"render_blocks({a}, fmt)", rend=lambda a: f"render({a}, fmt)")
    esc = []
    for i, (fmt, c) in enumerate(formats.items()):
        esc.append(f"    {'if' if i == 0 else 'elif'} fmt == \"{fmt}\":\n" + body(c["esc"], indent=8, **sub))
    branches = []
    for k in kinds:
        inner = [f"    if node.type == \"{k}\":"]
        for i, (fmt, c) in enumerate(formats.items()):
            inner.append(f"        {'if' if i == 0 else 'elif'} fmt == \"{fmt}\":\n" + body(c[k], indent=12, **sub))
        branches.append("\n".join(inner))
    seps = ", ".join(f'"{fmt}": {c["separator"]!r}' for fmt, c in formats.items())
    src = f'''"""Render a JSON document tree to a markup format: python docrender.py --to html < doc.json"""
import argparse
import json
import sys

FORMATS = {list(formats)!r}
SEPARATORS = {{{seps}}}


class RenderError(Exception):
    """A document that can't be rendered: unknown format, unknown node type."""


class Node:
    """A parsed JSON object: its fields become attributes, nested objects become Nodes."""

    def __init__(self, data):
        for key, value in data.items():
            setattr(self, key, build(value))


def build(value):
    if isinstance(value, dict):
        return Node(value)
    if isinstance(value, list):
        return [build(v) for v in value]
    return value


def prefix_lines(text, first, rest=None):
    """Prefix the first line of text with `first` and every later line with `rest` (default: `first`).
    Empty lines get the prefix without trailing spaces."""
    rest = first if rest is None else rest
    out = []
    for i, line in enumerate(text.split("\\n")):
        prefix = first if i == 0 else rest
        out.append(prefix + line if line else prefix.rstrip())
    return "\\n".join(out)


def escape(text, fmt):
{chr(10).join(esc)}
    return text


def render_inlines(children, fmt):
    return "".join(render(child, fmt) for child in children)


def render_blocks(children, fmt):
    return SEPARATORS[fmt].join(render(child, fmt) for child in children)


def render(node, fmt):
    if node.type == "document":
        return render_blocks(node.children, fmt) + "\\n"
{chr(10).join(branches)}
    raise RenderError(f"unsupported node type: {{node.type}}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a JSON document to a markup format.")
    parser.add_argument("--to", required=True, help="output format")
    args = parser.parse_args(argv)
    try:
        if args.to not in FORMATS:
            raise RenderError(f"unknown format: {{args.to}}")
        output = render(build(json.load(sys.stdin)), args.to)
    except (RenderError, json.JSONDecodeError) as e:
        print(f"error: {{e}}", file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
    write(root, "docrender.py", src)


# ------------------------------------------------------------------ layered
def layered(root: Path, formats: dict, kinds: list[str]) -> None:
    write(root, "docrender.py", cli(
        "from markup.core.errors import RenderError\nfrom markup.core.nodes import build\n"
        "from markup.core.pipeline import RenderPipeline, RenderRequest\nfrom markup.formats import load_formats",
        """
        pipeline = RenderPipeline(load_formats())
        output = pipeline.run(RenderRequest(document=build(json.load(sys.stdin)), format_name=args.to)).output
        """))
    write(root, "markup/__init__.py", "")
    write(root, "markup/core/__init__.py", "")
    write(root, "markup/core/errors.py", ERRORS_PY)
    write(root, "markup/core/text.py", TEXT_PY)
    write(root, "markup/core/nodes.py", GENERIC_NODES_PY)
    write(root, "markup/core/interfaces.py", '''
    from __future__ import annotations

    from abc import ABC, abstractmethod
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from .context import RenderContext


    class FormatSpec(ABC):
        """Format-wide settings of one output format."""

        name: str = ""
        separator: str = "\\n\\n"

        @abstractmethod
        def escape(self, text: str) -> str:
            """Make plain text safe to place in this format."""


    class CellRenderer(ABC):
        """Renders one node kind in one output format."""

        kind: str = ""
        format_name: str = ""

        @abstractmethod
        def render(self, node, ctx: RenderContext) -> str:
            """Render `node`; use ctx to render children and escape text."""


    class Middleware(ABC):
        """Hook around every node render."""

        def before(self, node, ctx: RenderContext) -> None:
            return None

        def after(self, node, ctx: RenderContext, output: str) -> str:
            return output
    ''')
    write(root, "markup/core/registry.py", '''
    from __future__ import annotations

    from .errors import RenderError
    from .interfaces import CellRenderer, FormatSpec


    class Registry:
        """Every known format spec and (kind, format) cell renderer."""

        def __init__(self):
            self._formats: dict[str, FormatSpec] = {}
            self._cells: dict[tuple[str, str], CellRenderer] = {}

        def format(self, cls: type[FormatSpec]) -> type[FormatSpec]:
            self._formats[cls.name] = cls()
            return cls

        def cell(self, kind: str, format_name: str):
            def register(cls: type[CellRenderer]) -> type[CellRenderer]:
                cls.kind, cls.format_name = kind, format_name
                self._cells[(kind, format_name)] = cls()
                return cls
            return register

        def format_spec(self, name: str) -> FormatSpec:
            if name not in self._formats:
                raise RenderError(f"unknown format: {name}")
            return self._formats[name]

        def lookup(self, kind: str, format_name: str) -> CellRenderer:
            if (kind, format_name) not in self._cells:
                raise RenderError(f"unsupported node type: {kind}")
            return self._cells[(kind, format_name)]


    REGISTRY = Registry()
    ''')
    write(root, "markup/core/context.py", '''
    from __future__ import annotations

    from .interfaces import FormatSpec, Middleware
    from .registry import Registry


    class RenderContext:
        """What a cell renderer can use while rendering: child rendering and the format's escaping."""

        def __init__(self, spec: FormatSpec, registry: Registry, middleware: list[Middleware]):
            self.spec = spec
            self.registry = registry
            self.middleware = middleware

        def render(self, node) -> str:
            for m in self.middleware:
                m.before(node, self)
            output = self.registry.lookup(node.type, self.spec.name).render(node, self)
            for m in reversed(self.middleware):
                output = m.after(node, self, output)
            return output

        def inlines(self, children) -> str:
            return "".join(self.render(child) for child in children)

        def blocks(self, children) -> str:
            return self.spec.separator.join(self.render(child) for child in children)

        def escape(self, text: str) -> str:
            return self.spec.escape(text)
    ''')
    write(root, "markup/core/factory.py", '''
    from __future__ import annotations

    from .context import RenderContext
    from .interfaces import Middleware
    from .registry import Registry


    class ContextFactory:
        """Builds the render context for a format."""

        def __init__(self, registry: Registry, middleware: list[Middleware] | None = None):
            self.registry = registry
            self.middleware = middleware or []

        def create(self, format_name: str) -> RenderContext:
            return RenderContext(self.registry.format_spec(format_name), self.registry, list(self.middleware))
    ''')
    write(root, "markup/core/pipeline.py", '''
    from __future__ import annotations

    from dataclasses import dataclass, field

    from .factory import ContextFactory
    from .interfaces import Middleware
    from .registry import Registry


    @dataclass
    class RenderRequest:
        document: object
        format_name: str


    @dataclass
    class RenderResult:
        output: str
        format_name: str
        warnings: list[str] = field(default_factory=list)


    class RenderPipeline:
        """Renders a whole document: builds a context for the format, then renders the top-level blocks."""

        def __init__(self, registry: Registry, middleware: list[Middleware] | None = None):
            self.factory = ContextFactory(registry, middleware)

        def run(self, request: RenderRequest) -> RenderResult:
            ctx = self.factory.create(request.format_name)
            output = ctx.blocks(request.document.children) + "\\n"
            return RenderResult(output=output, format_name=request.format_name)
    ''')
    mods = "\n".join(f'    "{fmt}",' for fmt in formats)
    write(root, "markup/formats/__init__.py", f'''
    import importlib

    from ..core.registry import REGISTRY, Registry

    FORMAT_MODULES = [
    {mods}
    ]


    def load_formats() -> Registry:
        """Import every format package so its spec and cells register themselves."""
        for name in FORMAT_MODULES:
            importlib.import_module(f"{{__name__}}.{{name}}")
        return REGISTRY
    ''')
    for fmt, cells in formats.items():
        sub = dict(node="node", esc=lambda a: f"ctx.escape({a})", inl=lambda a: f"ctx.inlines({a})",
                   blk=lambda a: f"ctx.blocks({a})", rend=lambda a: f"ctx.render({a})")
        write(root, f"markup/formats/{fmt}/__init__.py", "from . import cells, spec\n\n__all__ = [\"cells\", \"spec\"]\n")
        sep = f"    separator = {cells['separator']!r}\n" if cells["separator"] != "\n\n" else ""
        esc_body = body(cells["esc"], "node", None, None, None, None, 8)
        (root / f"markup/formats/{fmt}/spec.py").write_text(
            f"from ...core.interfaces import FormatSpec\nfrom ...core.registry import REGISTRY\n\n\n@REGISTRY.format\n"
            f"class {CLASS[fmt]}Format(FormatSpec):\n    name = \"{fmt}\"\n{sep}\n    def escape(self, text: str) -> str:\n{esc_body}\n")
        parts = []
        for k in kinds:
            parts.append(f"\n@REGISTRY.cell(\"{k}\", \"{fmt}\")\nclass {CLASS[fmt]}{camel(k)}(CellRenderer):\n"
                         f"    def render(self, node, ctx) -> str:\n" + body(cells[k], indent=8, **sub) + "\n")
        src = "\n".join(parts)
        head = "from ...core.interfaces import CellRenderer\nfrom ...core.registry import REGISTRY\n"
        head += "from ...core.text import prefix_lines\n" if "prefix_lines(" in src else ""
        (root / f"markup/formats/{fmt}/cells.py").write_text((head + "\n" + src).rstrip() + "\n")


def families(root: Path, formats: dict, kinds: list[str]) -> None:
    by_format(root, {f: formats[f] for f in ("html", "bbcode", "latex")}, kinds)
    shutil.copytree(HERE / "families", root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))


def families_explicit(root: Path, formats: dict, kinds: list[str]) -> None:
    by_format(root, {f: formats[f] for f in ("html", "bbcode", "latex")}, kinds)
    shutil.copytree(HERE / "families_explicit", root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))


VARIANTS = {"by_kind": by_kind, "by_format": by_format, "flat": flat, "layered": layered, "families": families,
            "families_explicit": families_explicit}


def emit(variant: str, root: Path, formats: dict, kinds: list[str]) -> None:
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    VARIANTS[variant](root, formats, kinds)
    write(root, "README.md", README)
