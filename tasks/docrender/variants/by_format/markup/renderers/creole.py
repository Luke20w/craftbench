from ..text import prefix_lines
from .base import Renderer


class CreoleRenderer(Renderer):
    def esc(self, text: str) -> str:
        for ch in "~*/[]{}\\|=#":
            text = text.replace(ch, "~" + ch)
        return text

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "**" + self.inlines(node.children) + "**"

    def emphasis(self, node) -> str:
        return "//" + self.inlines(node.children) + "//"

    def code(self, node) -> str:
        return "{{{" + node.value + "}}}"

    def link(self, node) -> str:
        return "[[" + node.url + "|" + self.inlines(node.children) + "]]"

    def line_break(self, node) -> str:
        return "\\\\"

    def subscript(self, node) -> str:
        return ",," + self.inlines(node.children) + ",,"

    def superscript(self, node) -> str:
        return "^^" + self.inlines(node.children) + "^^"

    def highlight(self, node) -> str:
        return "__" + self.inlines(node.children) + "__"

    def kbd(self, node) -> str:
        return "{{{" + node.value + "}}}"

    def math(self, node) -> str:
        return "{{{" + node.value + "}}}"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        return "=" * min(node.level, 6) + " " + self.inlines(node.children)

    def code_block(self, node) -> str:
        return "{{{\n" + node.code + "\n}}}"

    def quote(self, node) -> str:
        return prefix_lines(self.blocks(node.children), "> ")

    def list(self, node) -> str:
        marker = "#" if node.ordered else "*"
        lines = []
        for item in node.items:
            lines.append(marker + " " + self.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), marker))
        return "\n".join(lines)

    def table(self, node) -> str:
        lines = ["|=" + "|=".join(self.inlines(cell) for cell in node.header) + "|"]
        lines += ["|" + "|".join(self.inlines(cell) for cell in cells) + "|" for cells in node.rows]
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "----"

    def image(self, node) -> str:
        return "{{" + node.src + "|" + node.alt + "}}"

    def figure(self, node) -> str:
        return "{{" + node.src + "|" + node.alt + "}}\n//" + self.inlines(node.caption) + "//"
