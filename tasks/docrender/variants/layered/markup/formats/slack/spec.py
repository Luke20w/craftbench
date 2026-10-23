from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class SlackFormat(FormatSpec):
    name = "slack"

    def escape(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
