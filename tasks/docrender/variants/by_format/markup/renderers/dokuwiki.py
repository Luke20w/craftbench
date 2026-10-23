from ..text import prefix_lines
from .base import Renderer


class DokuWikiRenderer(Renderer):
    def esc(self, text: str) -> str:
        if any(ch in text for ch in "*/[]_'^|<>{}"):
            return "%%" + text + "%%"
        return text

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "**" + self.inlines(node.children) + "**"

    def emphasis(self, node) -> str:
        return "//" + self.inlines(node.children) + "//"

    def code(self, node) -> str:
        return "''" + node.value + "''"

    def link(self, node) -> str:
        return "[[" + node.url + "|" + self.inlines(node.children) + "]]"

    def line_break(self, node) -> str:
        return "\\\\ "

    def subscript(self, node) -> str:
        return "<sub>" + self.inlines(node.children) + "</sub>"

    def superscript(self, node) -> str:
        return "<sup>" + self.inlines(node.children) + "</sup>"

    def highlight(self, node) -> str:
        return "<color black/yellow>" + self.inlines(node.children) + "</color>"

    def kbd(self, node) -> str:
        return "<key>" + node.value + "</key>"

    def math(self, node) -> str:
        return "$" + node.value + "$"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        marks = "=" * (7 - min(node.level, 5))
        return marks + " " + self.inlines(node.children) + " " + marks

    def code_block(self, node) -> str:
        opening = "<code " + node.language + ">" if node.language else "<code>"
        return opening + "\n" + node.code + "\n</code>"

    def quote(self, node) -> str:
        return prefix_lines(self.blocks(node.children), "> ")

    def list(self, node) -> str:
        marker = "  - " if node.ordered else "  * "
        lines = []
        for item in node.items:
            lines.append(marker + self.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), "  "))
        return "\n".join(lines)

    def table(self, node) -> str:
        lines = ["^ " + " ^ ".join(self.inlines(cell) for cell in node.header) + " ^"]
        lines += ["| " + " | ".join(self.inlines(cell) for cell in cells) + " |" for cells in node.rows]
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "----"

    def image(self, node) -> str:
        return "{{" + node.src + "|" + node.alt + "}}"

    def figure(self, node) -> str:
        return "{{" + node.src + "|" + self.inlines(node.caption) + "}}"
