from ..text import prefix_lines
from .base import Renderer


class JiraRenderer(Renderer):
    def esc(self, text: str) -> str:
        for ch in "\\*_{}[]|":
            text = text.replace(ch, "\\" + ch)
        return text

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "*" + self.inlines(node.children) + "*"

    def emphasis(self, node) -> str:
        return "_" + self.inlines(node.children) + "_"

    def code(self, node) -> str:
        return "{{" + node.value + "}}"

    def link(self, node) -> str:
        return "[" + self.inlines(node.children) + "|" + node.url + "]"

    def line_break(self, node) -> str:
        return "\n"

    def subscript(self, node) -> str:
        return "~" + self.inlines(node.children) + "~"

    def superscript(self, node) -> str:
        return "^" + self.inlines(node.children) + "^"

    def highlight(self, node) -> str:
        return "{color:#ffab00}" + self.inlines(node.children) + "{color}"

    def kbd(self, node) -> str:
        return "{{" + node.value + "}}"

    def math(self, node) -> str:
        return "{{" + node.value + "}}"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        return f"h{min(node.level, 6)}. " + self.inlines(node.children)

    def code_block(self, node) -> str:
        opening = "{code:" + node.language + "}" if node.language else "{code}"
        return opening + "\n" + node.code + "\n{code}"

    def quote(self, node) -> str:
        return "{quote}\n" + self.blocks(node.children) + "\n{quote}"

    def list(self, node) -> str:
        marker = "#" if node.ordered else "*"
        lines = []
        for item in node.items:
            lines.append(marker + " " + self.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), marker))
        return "\n".join(lines)

    def table(self, node) -> str:
        lines = ["||" + "||".join(self.inlines(cell) for cell in node.header) + "||"]
        lines += ["|" + "|".join(self.inlines(cell) for cell in cells) + "|" for cells in node.rows]
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "----"

    def image(self, node) -> str:
        return "!" + node.src + "|alt=" + node.alt + "!" if node.alt else "!" + node.src + "!"

    def figure(self, node) -> str:
        image = "!" + node.src + "|alt=" + node.alt + "!" if node.alt else "!" + node.src + "!"
        return image + "\n_" + self.inlines(node.caption) + "_"
