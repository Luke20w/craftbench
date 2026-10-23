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
