from ..text import prefix_lines
from .base import Renderer


class PlainTextRenderer(Renderer):
    def esc(self, text: str) -> str:
        return text

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return self.inlines(node.children).upper()

    def emphasis(self, node) -> str:
        return "_" + self.inlines(node.children) + "_"

    def code(self, node) -> str:
        return node.value

    def link(self, node) -> str:
        text = self.inlines(node.children)
        return text if text == node.url else text + " <" + node.url + ">"

    def line_break(self, node) -> str:
        return "\n"

    def subscript(self, node) -> str:
        return "_" + self.inlines(node.children)

    def superscript(self, node) -> str:
        return "^" + self.inlines(node.children)

    def highlight(self, node) -> str:
        return ">>" + self.inlines(node.children) + "<<"

    def kbd(self, node) -> str:
        return "[" + node.value + "]"

    def math(self, node) -> str:
        return node.value

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        text = self.inlines(node.children)
        if node.level == 1:
            return text + "\n" + "=" * len(text)
        if node.level == 2:
            return text + "\n" + "-" * len(text)
        return text

    def code_block(self, node) -> str:
        return prefix_lines(node.code, "    ")

    def quote(self, node) -> str:
        return prefix_lines(self.blocks(node.children), "| ")

    def list(self, node) -> str:
        lines = []
        for number, item in enumerate(node.items, 1):
            marker = f"{number}) " if node.ordered else "* "
            lines.append(prefix_lines(self.inlines(item.children), marker, " " * len(marker)))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), " " * len(marker)))
        return "\n".join(lines)

    def table(self, node) -> str:
        rows = [[self.inlines(cell) for cell in node.header]] + [[self.inlines(cell) for cell in cells] for cells in node.rows]
        widths = [max(len(cells[i]) for cells in rows) for i in range(len(node.header))]
        def line(cells):
            return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
        lines = [line(rows[0]), "-+-".join("-" * width for width in widths)]
        lines += [line(cells) for cells in rows[1:]]
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "* * *"

    def image(self, node) -> str:
        return "[image: " + node.alt + "]"

    def figure(self, node) -> str:
        return "[image: " + node.alt + "]\n" + self.inlines(node.caption)
