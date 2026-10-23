from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class PlainTextFormat(FormatSpec):
    name = "plain"

    def escape(self, text: str) -> str:
        return text
