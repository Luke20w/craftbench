from ..text import prefix_lines
from .base import Renderer


class LatexRenderer(Renderer):
    def esc(self, text: str) -> str:
        out = []
        for ch in text:
            if ch == "\\":
                out.append("\\textbackslash{}")
            elif ch in "&%$#_{}":
                out.append("\\" + ch)
            elif ch == "~":
                out.append("\\textasciitilde{}")
            elif ch == "^":
                out.append("\\textasciicircum{}")
            else:
                out.append(ch)
        return "".join(out)

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "\\textbf{" + self.inlines(node.children) + "}"

    def emphasis(self, node) -> str:
        return "\\emph{" + self.inlines(node.children) + "}"

    def code(self, node) -> str:
        return "\\texttt{" + self.esc(node.value) + "}"

    def link(self, node) -> str:
        url = node.url.replace("%", "\\%").replace("#", "\\#")
        return "\\href{" + url + "}{" + self.inlines(node.children) + "}"

    def line_break(self, node) -> str:
        return "\\\\\n"

    def subscript(self, node) -> str:
        return "\\textsubscript{" + self.inlines(node.children) + "}"

    def superscript(self, node) -> str:
        return "\\textsuperscript{" + self.inlines(node.children) + "}"

    def highlight(self, node) -> str:
        return "\\hl{" + self.inlines(node.children) + "}"

    def kbd(self, node) -> str:
        return "\\fbox{\\texttt{" + self.esc(node.value) + "}}"

    def math(self, node) -> str:
        return "$" + node.value + "$"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        command = {1: "section", 2: "subsection"}.get(node.level, "subsubsection")
        return "\\" + command + "{" + self.inlines(node.children) + "}"

    def code_block(self, node) -> str:
        return "\\begin{verbatim}\n" + node.code + "\n\\end{verbatim}"

    def quote(self, node) -> str:
        return "\\begin{quote}\n" + self.blocks(node.children) + "\n\\end{quote}"

    def list(self, node) -> str:
        env = "enumerate" if node.ordered else "itemize"
        lines = ["\\begin{" + env + "}"]
        for item in node.items:
            lines.append(prefix_lines(self.inlines(item.children), "  \\item ", "  "))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), "  "))
        lines.append("\\end{" + env + "}")
        return "\n".join(lines)

    def table(self, node) -> str:
        columns = "|" + "|".join("l" for _ in node.header) + "|"
        lines = ["\\begin{tabular}{" + columns + "}", "\\hline", " & ".join(self.inlines(cell) for cell in node.header) + " \\\\", "\\hline"]
        for cells in node.rows:
            lines.append(" & ".join(self.inlines(cell) for cell in cells) + " \\\\")
        lines += ["\\hline", "\\end{tabular}"]
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "\\noindent\\rule{\\linewidth}{0.4pt}"

    def image(self, node) -> str:
        return "\\includegraphics{" + node.src + "}"

    def figure(self, node) -> str:
        return "\\begin{figure}\n\\includegraphics{" + node.src + "}\n\\caption{" + self.inlines(node.caption) + "}\n\\end{figure}"
