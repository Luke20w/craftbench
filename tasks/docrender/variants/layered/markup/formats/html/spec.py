from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class HtmlFormat(FormatSpec):
    name = "html"
    separator = '\n'

    def escape(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
