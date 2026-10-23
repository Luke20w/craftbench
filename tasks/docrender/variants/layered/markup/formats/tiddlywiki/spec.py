from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class TiddlyWikiFormat(FormatSpec):
    name = "tiddlywiki"

    def escape(self, text: str) -> str:
        if any(ch in text for ch in "'/`[]{}<>^~_$|"):
            return '"""' + text + '"""'
        return text
