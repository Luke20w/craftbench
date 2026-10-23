from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "mediawiki")
class MediaWikiText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "mediawiki")
class MediaWikiStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "'''" + ctx.inlines(node.children) + "'''"


@REGISTRY.cell("emphasis", "mediawiki")
class MediaWikiEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "''" + ctx.inlines(node.children) + "''"


@REGISTRY.cell("code", "mediawiki")
class MediaWikiCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<code>" + ctx.escape(node.value) + "</code>"


@REGISTRY.cell("link", "mediawiki")
class MediaWikiLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[" + node.url + " " + ctx.inlines(node.children) + "]"


@REGISTRY.cell("line_break", "mediawiki")
class MediaWikiLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<br />"


@REGISTRY.cell("subscript", "mediawiki")
class MediaWikiSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<sub>" + ctx.inlines(node.children) + "</sub>"


@REGISTRY.cell("superscript", "mediawiki")
class MediaWikiSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<sup>" + ctx.inlines(node.children) + "</sup>"


@REGISTRY.cell("highlight", "mediawiki")
class MediaWikiHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<mark>" + ctx.inlines(node.children) + "</mark>"


@REGISTRY.cell("kbd", "mediawiki")
class MediaWikiKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<kbd>" + ctx.escape(node.value) + "</kbd>"


@REGISTRY.cell("math", "mediawiki")
class MediaWikiMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<math>" + node.value + "</math>"


@REGISTRY.cell("paragraph", "mediawiki")
class MediaWikiParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "mediawiki")
class MediaWikiHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        marks = "=" * (min(node.level, 5) + 1)
        return marks + " " + ctx.inlines(node.children) + " " + marks


@REGISTRY.cell("code_block", "mediawiki")
class MediaWikiCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        if node.language:
            return '<syntaxhighlight lang="' + node.language + '">\n' + node.code + "\n</syntaxhighlight>"
        return "<pre>\n" + ctx.escape(node.code) + "\n</pre>"


@REGISTRY.cell("quote", "mediawiki")
class MediaWikiQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<blockquote>\n" + ctx.blocks(node.children) + "\n</blockquote>"


@REGISTRY.cell("list", "mediawiki")
class MediaWikiList(CellRenderer):
    def render(self, node, ctx) -> str:
        marker = "#" if node.ordered else "*"
        lines = []
        for item in node.items:
            lines.append(marker + " " + ctx.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), marker))
        return "\n".join(lines)


@REGISTRY.cell("table", "mediawiki")
class MediaWikiTable(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = ['{| class="wikitable"', "! " + " !! ".join(ctx.inlines(cell) for cell in node.header)]
        for cells in node.rows:
            lines += ["|-", "| " + " || ".join(ctx.inlines(cell) for cell in cells)]
        lines.append("|}")
        return "\n".join(lines)


@REGISTRY.cell("rule", "mediawiki")
class MediaWikiRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "----"


@REGISTRY.cell("image", "mediawiki")
class MediaWikiImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[[File:" + node.src + "|" + ctx.escape(node.alt) + "]]"


@REGISTRY.cell("figure", "mediawiki")
class MediaWikiFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[[File:" + node.src + "|thumb|" + ctx.inlines(node.caption) + "]]"
