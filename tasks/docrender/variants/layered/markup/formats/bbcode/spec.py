from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class BBCodeFormat(FormatSpec):
    name = "bbcode"

    def escape(self, text: str) -> str:
        return "[noparse]" + text + "[/noparse]" if "[" in text else text
