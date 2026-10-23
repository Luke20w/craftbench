from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "creole")
class CreoleText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "creole")
class CreoleStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "**" + ctx.inlines(node.children) + "**"


@REGISTRY.cell("emphasis", "creole")
class CreoleEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "//" + ctx.inlines(node.children) + "//"


@REGISTRY.cell("code", "creole")
class CreoleCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{{" + node.value + "}}}"


@REGISTRY.cell("link", "creole")
class CreoleLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[[" + node.url + "|" + ctx.inlines(node.children) + "]]"


@REGISTRY.cell("line_break", "creole")
class CreoleLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\\\"


@REGISTRY.cell("subscript", "creole")
class CreoleSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return ",," + ctx.inlines(node.children) + ",,"


@REGISTRY.cell("superscript", "creole")
class CreoleSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "^^" + ctx.inlines(node.children) + "^^"


@REGISTRY.cell("highlight", "creole")
class CreoleHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "__" + ctx.inlines(node.children) + "__"


@REGISTRY.cell("kbd", "creole")
class CreoleKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{{" + node.value + "}}}"


@REGISTRY.cell("math", "creole")
class CreoleMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{{" + node.value + "}}}"


@REGISTRY.cell("paragraph", "creole")
class CreoleParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "creole")
class CreoleHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        return "=" * min(node.level, 6) + " " + ctx.inlines(node.children)


@REGISTRY.cell("code_block", "creole")
class CreoleCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{{\n" + node.code + "\n}}}"


@REGISTRY.cell("quote", "creole")
class CreoleQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return prefix_lines(ctx.blocks(node.children), "> ")


@REGISTRY.cell("list", "creole")
class CreoleList(CellRenderer):
    def render(self, node, ctx) -> str:
        marker = "#" if node.ordered else "*"
        lines = []
        for item in node.items:
            lines.append(marker + " " + ctx.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), marker))
        return "\n".join(lines)


@REGISTRY.cell("table", "creole")
class CreoleTable(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = ["|=" + "|=".join(ctx.inlines(cell) for cell in node.header) + "|"]
        lines += ["|" + "|".join(ctx.inlines(cell) for cell in cells) + "|" for cells in node.rows]
        return "\n".join(lines)


@REGISTRY.cell("rule", "creole")
class CreoleRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "----"


@REGISTRY.cell("image", "creole")
class CreoleImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{" + node.src + "|" + node.alt + "}}"


@REGISTRY.cell("figure", "creole")
class CreoleFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{" + node.src + "|" + node.alt + "}}\n//" + ctx.inlines(node.caption) + "//"
