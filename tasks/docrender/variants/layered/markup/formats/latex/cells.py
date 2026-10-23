from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY
from ...core.text import prefix_lines


@REGISTRY.cell("text", "latex")
class LatexText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "latex")
class LatexStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\textbf{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("emphasis", "latex")
class LatexEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\emph{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("code", "latex")
class LatexCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\texttt{" + ctx.escape(node.value) + "}"


@REGISTRY.cell("link", "latex")
class LatexLink(CellRenderer):
    def render(self, node, ctx) -> str:
        url = node.url.replace("%", "\\%").replace("#", "\\#")
        return "\\href{" + url + "}{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("line_break", "latex")
class LatexLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\\\\n"


@REGISTRY.cell("subscript", "latex")
class LatexSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\textsubscript{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("superscript", "latex")
class LatexSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\textsuperscript{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("highlight", "latex")
class LatexHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\hl{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("kbd", "latex")
class LatexKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\fbox{\\texttt{" + ctx.escape(node.value) + "}}"


@REGISTRY.cell("math", "latex")
class LatexMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return "$" + node.value + "$"


@REGISTRY.cell("paragraph", "latex")
class LatexParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.inlines(node.children)


@REGISTRY.cell("heading", "latex")
class LatexHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        command = {1: "section", 2: "subsection"}.get(node.level, "subsubsection")
        return "\\" + command + "{" + ctx.inlines(node.children) + "}"


@REGISTRY.cell("code_block", "latex")
class LatexCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\begin{verbatim}\n" + node.code + "\n\\end{verbatim}"


@REGISTRY.cell("quote", "latex")
class LatexQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\begin{quote}\n" + ctx.blocks(node.children) + "\n\\end{quote}"


@REGISTRY.cell("list", "latex")
class LatexList(CellRenderer):
    def render(self, node, ctx) -> str:
        env = "enumerate" if node.ordered else "itemize"
        lines = ["\\begin{" + env + "}"]
        for item in node.items:
            lines.append(prefix_lines(ctx.inlines(item.children), "  \\item ", "  "))
            if item.sublist:
                lines.append(prefix_lines(ctx.render(item.sublist), "  "))
        lines.append("\\end{" + env + "}")
        return "\n".join(lines)


@REGISTRY.cell("table", "latex")
class LatexTable(CellRenderer):
    def render(self, node, ctx) -> str:
        columns = "|" + "|".join("l" for _ in node.header) + "|"
        lines = ["\\begin{tabular}{" + columns + "}", "\\hline", " & ".join(ctx.inlines(cell) for cell in node.header) + " \\\\", "\\hline"]
        for cells in node.rows:
            lines.append(" & ".join(ctx.inlines(cell) for cell in cells) + " \\\\")
        lines += ["\\hline", "\\end{tabular}"]
        return "\n".join(lines)


@REGISTRY.cell("rule", "latex")
class LatexRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\noindent\\rule{\\linewidth}{0.4pt}"


@REGISTRY.cell("image", "latex")
class LatexImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\includegraphics{" + node.src + "}"


@REGISTRY.cell("figure", "latex")
class LatexFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return "\\begin{figure}\n\\includegraphics{" + node.src + "}\n\\caption{" + ctx.inlines(node.caption) + "}\n\\end{figure}"
