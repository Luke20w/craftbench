from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "markdown")
class MarkdownText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "markdown")
class MarkdownStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "**" + ctx.inlines(node.children) + "**"


@REGISTRY.cell("emphasis", "markdown")
class MarkdownEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "*" + ctx.inlines(node.children) + "*"


@REGISTRY.cell("code", "markdown")
class MarkdownCode(CellRenderer):
    def render(self, node, ctx) -> str:
        if "`" in node.value:
            return "`` " + node.value + " ``"
        return "`" + node.value + "`"


@REGISTRY.cell("link", "markdown")
class MarkdownLink(CellRenderer):
    def render(self, node, ctx) -> str:
        url = node.url.replace(" ", "%20").replace(")", "%29")
        return "[" + ctx.inlines(node.children) + "](" + url + ")"


@REGISTRY.cell("line_break", "markdown")
class MarkdownLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\\n"


@REGISTRY.cell("subscript", "markdown")
class MarkdownSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<sub>" + ctx.inlines(node.children) + "</sub>"


@REGISTRY.cell("superscript", "markdown")
class MarkdownSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<sup>" + ctx.inlines(node.children) + "</sup>"


@REGISTRY.cell("highlight", "markdown")
class MarkdownHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "==" + ctx.inlines(node.children) + "=="


@REGISTRY.cell("kbd", "markdown")
class MarkdownKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<kbd>" + node.value + "</kbd>"


@REGISTRY.cell("math", "markdown")
class MarkdownMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "$" + node.value + "$"


@REGISTRY.cell("paragraph", "markdown")
class MarkdownParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "markdown")
class MarkdownHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        return "#" * min(node.level, 6) + " " + ctx.inlines(node.children)


@REGISTRY.cell("code_block", "markdown")
class MarkdownCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        fence = "````" if "```" in node.code else "```"
        return fence + node.language + "\n" + node.code + "\n" + fence


@REGISTRY.cell("quote", "markdown")
class MarkdownQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return prefix_lines(ctx.blocks(node.children), "> ")


@REGISTRY.cell("list", "markdown")
class MarkdownList(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = []
        for number, item in enumerate(node.items, 1):
            marker = f"{number}. " if node.ordered else "- "
            lines.append(prefix_lines(ctx.inlines(item.children), marker, " " * len(marker)))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), " " * len(marker)))
        return "\n".join(lines)


@REGISTRY.cell("table", "markdown")
class MarkdownTable(CellRenderer):
    def render(self, node, ctx) -> str:
        def row(cells):
            return "| " + " | ".join(ctx.inlines(cell) for cell in cells) + " |"
        lines = [row(node.header), "|" + "|".join(" --- " for _ in node.header) + "|"]
        lines += [row(cells) for cells in node.rows]
        return "\n".join(lines)


@REGISTRY.cell("rule", "markdown")
class MarkdownRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "---"


@REGISTRY.cell("image", "markdown")
class MarkdownImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "![" + ctx.escape(node.alt) + "](" + node.src.replace(" ", "%20").replace(")", "%29") + ")"


@REGISTRY.cell("figure", "markdown")
class MarkdownFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return "![" + ctx.escape(node.alt) + "](" + node.src.replace(" ", "%20").replace(")", "%29") + ")\n\n*" + ctx.inlines(node.caption) + "*"
