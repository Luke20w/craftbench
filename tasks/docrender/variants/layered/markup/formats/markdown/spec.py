from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class MarkdownFormat(FormatSpec):
    name = "markdown"

    def escape(self, text: str) -> str:
        for ch in "\\`*_[]#|":
            text = text.replace(ch, "\\" + ch)
        return text
