from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class OrgFormat(FormatSpec):
    name = "org"

    def escape(self, text: str) -> str:
        return text.replace("[[", "[\u200b[")
