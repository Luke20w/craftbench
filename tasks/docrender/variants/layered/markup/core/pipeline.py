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
        output = ctx.blocks(request.document.children) + "\n"
        return RenderResult(output=output, format_name=request.format_name)
