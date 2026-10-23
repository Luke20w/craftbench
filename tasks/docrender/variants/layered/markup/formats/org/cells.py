from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "org")
class OrgText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "org")
class OrgStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "*" + ctx.inlines(node.children) + "*"


@REGISTRY.cell("emphasis", "org")
class OrgEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "/" + ctx.inlines(node.children) + "/"


@REGISTRY.cell("code", "org")
class OrgCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "~" + node.value + "~"


@REGISTRY.cell("link", "org")
class OrgLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[[" + node.url + "][" + ctx.inlines(node.children) + "]]"


@REGISTRY.cell("line_break", "org")
class OrgLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\\\\n"


@REGISTRY.cell("subscript", "org")
class OrgSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "_{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("superscript", "org")
class OrgSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "^{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("highlight", "org")
class OrgHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "@@html:<mark>@@" + ctx.inlines(node.children) + "@@html:</mark>@@"


@REGISTRY.cell("kbd", "org")
class OrgKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "=" + node.value + "="


@REGISTRY.cell("math", "org")
class OrgMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\(" + node.value + "\\)"


@REGISTRY.cell("paragraph", "org")
class OrgParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "org")
class OrgHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        return "*" * node.level + " " + ctx.inlines(node.children)


@REGISTRY.cell("code_block", "org")
class OrgCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        opening = "#+BEGIN_SRC " + node.language if node.language else "#+BEGIN_SRC"
        return opening + "\n" + node.code + "\n#+END_SRC"


@REGISTRY.cell("quote", "org")
class OrgQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return "#+BEGIN_QUOTE\n" + ctx.blocks(node.children) + "\n#+END_QUOTE"


@REGISTRY.cell("list", "org")
class OrgList(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = []
        for number, item in enumerate(node.items, 1):
            marker = f"{number}. " if node.ordered else "- "
            lines.append(prefix_lines(ctx.inlines(item.children), marker, " " * len(marker)))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), " " * len(marker)))
        return "\n".join(lines)


@REGISTRY.cell("table", "org")
class OrgTable(CellRenderer):
    def render(self, node, ctx) -> str:
        def row(cells):
            return "| " + " | ".join(ctx.inlines(cell) for cell in cells) + " |"
        lines = [row(node.header), "|" + "+".join("---" for _ in node.header) + "|"]
        lines += [row(cells) for cells in node.rows]
        return "\n".join(lines)


@REGISTRY.cell("rule", "org")
class OrgRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "-----"


@REGISTRY.cell("image", "org")
class OrgImage(CellRenderer):
    def render(self, node, ctx) -> str:
        caption = "#+CAPTION: " + node.alt + "\n" if node.alt else ""
        return caption + "[[" + node.src + "]]"


@REGISTRY.cell("figure", "org")
class OrgFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return "#+CAPTION: " + ctx.inlines(node.caption) + "\n[[" + node.src + "]]"
