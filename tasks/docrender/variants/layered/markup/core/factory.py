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
