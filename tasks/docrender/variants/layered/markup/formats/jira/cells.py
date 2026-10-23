from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "jira")
class JiraText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "jira")
class JiraStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "*" + ctx.inlines(node.children) + "*"


@REGISTRY.cell("emphasis", "jira")
class JiraEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "_" + ctx.inlines(node.children) + "_"


@REGISTRY.cell("code", "jira")
class JiraCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{" + node.value + "}}"


@REGISTRY.cell("link", "jira")
class JiraLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return "[" + ctx.inlines(node.children) + "|" + node.url + "]"


@REGISTRY.cell("line_break", "jira")
class JiraLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\n"


@REGISTRY.cell("subscript", "jira")
class JiraSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "~" + ctx.inlines(node.children) + "~"


@REGISTRY.cell("superscript", "jira")
class JiraSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "^" + ctx.inlines(node.children) + "^"


@REGISTRY.cell("highlight", "jira")
class JiraHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{color:#ffab00}" + ctx.inlines(node.children) + "{color}"


@REGISTRY.cell("kbd", "jira")
class JiraKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{" + node.value + "}}"


@REGISTRY.cell("math", "jira")
class JiraMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{{" + node.value + "}}"


@REGISTRY.cell("paragraph", "jira")
class JiraParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "jira")
class JiraHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        return f"h{min(node.level, 6)}. " + ctx.inlines(node.children)


@REGISTRY.cell("code_block", "jira")
class JiraCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        opening = "{code:" + node.language + "}" if node.language else "{code}"
        return opening + "\n" + node.code + "\n{code}"


@REGISTRY.cell("quote", "jira")
class JiraQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return "{quote}\n" + ctx.blocks(node.children) + "\n{quote}"


@REGISTRY.cell("list", "jira")
class JiraList(CellRenderer):
    def render(self, node, ctx) -> str:
        marker = "#" if node.ordered else "*"
        lines = []
        for item in node.items:
            lines.append(marker + " " + ctx.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), marker))
        return "\n".join(lines)


@REGISTRY.cell("table", "jira")
class JiraTable(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = ["||" + "||".join(ctx.inlines(cell) for cell in node.header) + "||"]
        lines += ["|" + "|".join(ctx.inlines(cell) for cell in cells) + "|" for cells in node.rows]
        return "\n".join(lines)


@REGISTRY.cell("rule", "jira")
class JiraRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "----"


@REGISTRY.cell("image", "jira")
class JiraImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "!" + node.src + "|alt=" + node.alt + "!" if node.alt else "!" + node.src + "!"


@REGISTRY.cell("figure", "jira")
class JiraFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        image = "!" + node.src + "|alt=" + node.alt + "!" if node.alt else "!" + node.src + "!"
        return image + "\n_" + ctx.inlines(node.caption) + "_"
