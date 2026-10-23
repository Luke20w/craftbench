from ..text import prefix_lines
from .base import Renderer


class SlackRenderer(Renderer):
    def esc(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "*" + self.inlines(node.children) + "*"

    def emphasis(self, node) -> str:
        return "_" + self.inlines(node.children) + "_"

    def code(self, node) -> str:
        return "`" + node.value + "`"

    def link(self, node) -> str:
        return "<" + node.url + "|" + self.inlines(node.children) + ">"

    def line_break(self, node) -> str:
        return "\n"

    def subscript(self, node) -> str:
        return self.inlines(node.children)

    def superscript(self, node) -> str:
        return self.inlines(node.children)

    def highlight(self, node) -> str:
        return "*_" + self.inlines(node.children) + "_*"

    def kbd(self, node) -> str:
        return "`" + node.value + "`"

    def math(self, node) -> str:
        return "`" + node.value + "`"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        return "*" + self.inlines(node.children) + "*"

    def code_block(self, node) -> str:
        return "```\n" + node.code + "\n```"

    def quote(self, node) -> str:
        return prefix_lines(self.blocks(node.children), "> ")

    def list(self, node) -> str:
        lines = []
        for number, item in enumerate(node.items, 1):
            marker = f"{number}. " if node.ordered else "• "
            lines.append(prefix_lines(self.inlines(item.children), marker, "    "))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), "    "))
        return "\n".join(lines)

    def table(self, node) -> str:
        rows = [[self.inlines(cell) for cell in node.header]] + [[self.inlines(cell) for cell in cells] for cells in node.rows]
        widths = [max(len(cells[i]) for cells in rows) for i in range(len(node.header))]
        lines = ["  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip() for cells in rows]
        return "```\n" + "\n".join(lines) + "\n```"

    def rule(self, node) -> str:
        return "----------"

    def image(self, node) -> str:
        return "<" + node.src + "|" + (node.alt or node.src) + ">"

    def figure(self, node) -> str:
        return "<" + node.src + "|" + (node.alt or node.src) + ">\n_" + self.inlines(node.caption) + "_"
