from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "plain")
class PlainTextText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "plain")
class PlainTextStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children).upper()


@REGISTRY.cell("emphasis", "plain")
class PlainTextEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "_" + ctx.inlines(node.children) + "_"


@REGISTRY.cell("code", "plain")
class PlainTextCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return node.value


@REGISTRY.cell("link", "plain")
class PlainTextLink(CellRenderer):
    def render(self, node, ctx) -> str:
        text = ctx.inlines(node.children)
        return text if text == node.url else text + " <" + node.url + ">"


@REGISTRY.cell("line_break", "plain")
class PlainTextLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\n"


@REGISTRY.cell("subscript", "plain")
class PlainTextSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "_" + ctx.inlines(node.children)


@REGISTRY.cell("superscript", "plain")
class PlainTextSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "^" + ctx.inlines(node.children)


@REGISTRY.cell("highlight", "plain")
class PlainTextHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return ">>" + ctx.inlines(node.children) + "<<"


@REGISTRY.cell("kbd", "plain")
class PlainTextKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[" + node.value + "]"


@REGISTRY.cell("math", "plain")
class PlainTextMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return node.value


@REGISTRY.cell("paragraph", "plain")
class PlainTextParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "plain")
class PlainTextHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        text = ctx.inlines(node.children)
        if node.level == 1:
            return text + "\n" + "=" * len(text)
        if node.level == 2:
            return text + "\n" + "-" * len(text)
        return text


@REGISTRY.cell("code_block", "plain")
class PlainTextCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        return prefix_lines(node.code, "    ")


@REGISTRY.cell("quote", "plain")
class PlainTextQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return prefix_lines(ctx.blocks(node.children), "| ")


@REGISTRY.cell("list", "plain")
class PlainTextList(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = []
        for number, item in enumerate(node.items, 1):
            marker = f"{number}) " if node.ordered else "* "
            lines.append(prefix_lines(ctx.inlines(item.children), marker, " " * len(marker)))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), " " * len(marker)))
        return "\n".join(lines)


@REGISTRY.cell("table", "plain")
class PlainTextTable(CellRenderer):
    def render(self, node, ctx) -> str:
        rows = [[ctx.inlines(cell) for cell in node.header]] + [[ctx.inlines(cell) for cell in cells] for cells in node.rows]
        widths = [max(len(cells[i]) for cells in rows) for i in range(len(node.header))]
        def line(cells):
            return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
        lines = [line(rows[0]), "-+-".join("-" * width for width in widths)]
        lines += [line(cells) for cells in rows[1:]]
        return "\n".join(lines)


@REGISTRY.cell("rule", "plain")
class PlainTextRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "* * *"


@REGISTRY.cell("image", "plain")
class PlainTextImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[image: " + node.alt + "]"


@REGISTRY.cell("figure", "plain")
class PlainTextFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[image: " + node.alt + "]\n" + ctx.inlines(node.caption)
