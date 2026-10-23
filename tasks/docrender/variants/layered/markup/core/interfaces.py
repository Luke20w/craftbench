from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import RenderContext


class FormatSpec(ABC):
    """Format-wide settings of one output format."""

    name: str = ""
    separator: str = "\n\n"

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
