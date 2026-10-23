from ...core.interfaces import FormatSpec
from ...core.registry import REGISTRY


@REGISTRY.format
class MediaWikiFormat(FormatSpec):
    name = "mediawiki"

    def escape(self, text: str) -> str:
        for ch, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("[", "&#91;"), ("]", "&#93;")):
            text = text.replace(ch, entity)
        return text
