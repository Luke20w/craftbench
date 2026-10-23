from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "dokuwiki")
class DokuWikiText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "dokuwiki")
class DokuWikiStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "**" + ctx.inlines(node.children) + "**"


@REGISTRY.cell("emphasis", "dokuwiki")
class DokuWikiEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "//" + ctx.inlines(node.children) + "//"


@REGISTRY.cell("code", "dokuwiki")
class DokuWikiCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "''" + node.value + "''"


@REGISTRY.cell("link", "dokuwiki")
class DokuWikiLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[[" + node.url + "|" + ctx.inlines(node.children) + "]]"


@REGISTRY.cell("line_break", "dokuwiki")
class DokuWikiLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\\\ "


@REGISTRY.cell("subscript", "dokuwiki")
class DokuWikiSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<sub>" + ctx.inlines(node.children) + "</sub>"


@REGISTRY.cell("superscript", "dokuwiki")
class DokuWikiSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<sup>" + ctx.inlines(node.children) + "</sup>"


@REGISTRY.cell("highlight", "dokuwiki")
class DokuWikiHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<color black/yellow>" + ctx.inlines(node.children) + "</color>"


@REGISTRY.cell("kbd", "dokuwiki")
class DokuWikiKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<key>" + node.value + "</key>"


@REGISTRY.cell("math", "dokuwiki")
class DokuWikiMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "$" + node.value + "$"


@REGISTRY.cell("paragraph", "dokuwiki")
class DokuWikiParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "dokuwiki")
class DokuWikiHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        marks = "=" * (7 - min(node.level, 5))
        return marks + " " + ctx.inlines(node.children) + " " + marks


@REGISTRY.cell("code_block", "dokuwiki")
class DokuWikiCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        opening = "<code " + node.language + ">" if node.language else "<code>"
        return opening + "\n" + node.code + "\n</code>"


@REGISTRY.cell("quote", "dokuwiki")
class DokuWikiQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return prefix_lines(ctx.blocks(node.children), "> ")


@REGISTRY.cell("list", "dokuwiki")
class DokuWikiList(CellRenderer):
    def render(self, node, ctx) -> str:
        marker = "  - " if node.ordered else "  * "
        lines = []
        for item in node.items:
            lines.append(marker + ctx.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), "  "))
        return "\n".join(lines)


@REGISTRY.cell("table", "dokuwiki")
class DokuWikiTable(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = ["^ " + " ^ ".join(ctx.inlines(cell) for cell in node.header) + " ^"]
        lines += ["| " + " | ".join(ctx.inlines(cell) for cell in cells) + " |" for cells in node.rows]
        return "\n".join(lines)


@REGISTRY.cell("rule", "dokuwiki")
class DokuWikiRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "----"


@REGISTRY.cell("image", "dokuwiki")
class DokuWikiImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{" + node.src + "|" + node.alt + "}}"


@REGISTRY.cell("figure", "dokuwiki")
class DokuWikiFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{" + node.src + "|" + ctx.inlines(node.caption) + "}}"
