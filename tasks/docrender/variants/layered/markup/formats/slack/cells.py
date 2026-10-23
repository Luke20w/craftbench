from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "slack")
class SlackText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "slack")
class SlackStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "*" + ctx.inlines(node.children) + "*"


@REGISTRY.cell("emphasis", "slack")
class SlackEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "_" + ctx.inlines(node.children) + "_"


@REGISTRY.cell("code", "slack")
class SlackCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "`" + node.value + "`"


@REGISTRY.cell("link", "slack")
class SlackLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<" + node.url + "|" + ctx.inlines(node.children) + ">"


@REGISTRY.cell("line_break", "slack")
class SlackLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\n"


@REGISTRY.cell("subscript", "slack")
class SlackSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("superscript", "slack")
class SlackSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("highlight", "slack")
class SlackHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "*_" + ctx.inlines(node.children) + "_*"


@REGISTRY.cell("kbd", "slack")
class SlackKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "`" + node.value + "`"


@REGISTRY.cell("math", "slack")
class SlackMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "`" + node.value + "`"


@REGISTRY.cell("paragraph", "slack")
class SlackParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "slack")
class SlackHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        return "*" + ctx.inlines(node.children) + "*"


@REGISTRY.cell("code_block", "slack")
class SlackCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        return "```\n" + node.code + "\n```"


@REGISTRY.cell("quote", "slack")
class SlackQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return prefix_lines(ctx.blocks(node.children), "> ")


@REGISTRY.cell("list", "slack")
class SlackList(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = []
        for number, item in enumerate(node.items, 1):
            marker = f"{number}. " if node.ordered else "• "
            lines.append(prefix_lines(ctx.inlines(item.children), marker, "    "))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), "    "))
        return "\n".join(lines)


@REGISTRY.cell("table", "slack")
class SlackTable(CellRenderer):
    def render(self, node, ctx) -> str:
        rows = [[ctx.inlines(cell) for cell in node.header]] + [[ctx.inlines(cell) for cell in cells] for cells in node.rows]
        widths = [max(len(cells[i]) for cells in rows) for i in range(len(node.header))]
        lines = ["  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip() for cells in rows]
        return "```\n" + "\n".join(lines) + "\n```"


@REGISTRY.cell("rule", "slack")
class SlackRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "----------"


@REGISTRY.cell("image", "slack")
class SlackImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<" + node.src + "|" + (node.alt or node.src) + ">"


@REGISTRY.cell("figure", "slack")
class SlackFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<" + node.src + "|" + (node.alt or node.src) + ">\n_" + ctx.inlines(node.caption) + "_"
