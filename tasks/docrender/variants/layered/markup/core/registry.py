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
