from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "tiddlywiki")
class TiddlyWikiText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "tiddlywiki")
class TiddlyWikiStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "''" + ctx.inlines(node.children) + "''"


@REGISTRY.cell("emphasis", "tiddlywiki")
class TiddlyWikiEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "//" + ctx.inlines(node.children) + "//"


@REGISTRY.cell("code", "tiddlywiki")
class TiddlyWikiCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "`" + node.value + "`"


@REGISTRY.cell("link", "tiddlywiki")
class TiddlyWikiLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[[" + ctx.inlines(node.children) + "|" + node.url + "]]"


@REGISTRY.cell("line_break", "tiddlywiki")
class TiddlyWikiLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<br>"


@REGISTRY.cell("subscript", "tiddlywiki")
class TiddlyWikiSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return ",," + ctx.inlines(node.children) + ",,"


@REGISTRY.cell("superscript", "tiddlywiki")
class TiddlyWikiSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "^^" + ctx.inlines(node.children) + "^^"


@REGISTRY.cell("highlight", "tiddlywiki")
class TiddlyWikiHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "@@" + ctx.inlines(node.children) + "@@"


@REGISTRY.cell("kbd", "tiddlywiki")
class TiddlyWikiKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<kbd>" + node.value + "</kbd>"


@REGISTRY.cell("math", "tiddlywiki")
class TiddlyWikiMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "$$" + node.value + "$$"


@REGISTRY.cell("paragraph", "tiddlywiki")
class TiddlyWikiParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "tiddlywiki")
class TiddlyWikiHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        return "!" * min(node.level, 6) + " " + ctx.inlines(node.children)


@REGISTRY.cell("code_block", "tiddlywiki")
class TiddlyWikiCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        return "```" + node.language + "\n" + node.code + "\n```"


@REGISTRY.cell("quote", "tiddlywiki")
class TiddlyWikiQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<<<\n" + ctx.blocks(node.children) + "\n<<<"


@REGISTRY.cell("list", "tiddlywiki")
class TiddlyWikiList(CellRenderer):
    def render(self, node, ctx) -> str:
        marker = "#" if node.ordered else "*"
        lines = []
        for item in node.items:
            lines.append(marker + " " + ctx.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), marker))
        return "\n".join(lines)


@REGISTRY.cell("table", "tiddlywiki")
class TiddlyWikiTable(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = ["|!" + "|!".join(ctx.inlines(cell) for cell in node.header) + "|"]
        lines += ["|" + "|".join(ctx.inlines(cell) for cell in cells) + "|" for cells in node.rows]
        return "\n".join(lines)


@REGISTRY.cell("rule", "tiddlywiki")
class TiddlyWikiRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "---"


@REGISTRY.cell("image", "tiddlywiki")
class TiddlyWikiImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[img[" + node.alt + "|" + node.src + "]]" if node.alt else "[img[" + node.src + "]]"


@REGISTRY.cell("figure", "tiddlywiki")
class TiddlyWikiFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        image = "[img[" + node.alt + "|" + node.src + "]]" if node.alt else "[img[" + node.src + "]]"
        return image + "\n//" + ctx.inlines(node.caption) + "//"
