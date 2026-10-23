from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class CreoleFormat(FormatSpec):
    name = "creole"

    def escape(self, text: str) -> str:
        for ch in "~*/[]{}\\|=#":
            text = text.replace(ch, "~" + ch)
        return text
