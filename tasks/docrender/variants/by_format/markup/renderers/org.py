from ..text import prefix_lines
from .base import Renderer


class OrgRenderer(Renderer):
    def esc(self, text: str) -> str:
        return text.replace("[[", "[\u200b[")

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "*" + self.inlines(node.children) + "*"

    def emphasis(self, node) -> str:
        return "/" + self.inlines(node.children) + "/"

    def code(self, node) -> str:
        return "~" + node.value + "~"

    def link(self, node) -> str:
        return "[[" + node.url + "][" + self.inlines(node.children) + "]]"

    def line_break(self, node) -> str:
        return "\\\\\n"

    def subscript(self, node) -> str:
        return "_{" + self.inlines(node.children) + "}"

    def superscript(self, node) -> str:
        return "^{" + self.inlines(node.children) + "}"

    def highlight(self, node) -> str:
        return "@@html:<mark>@@" + self.inlines(node.children) + "@@html:</mark>@@"

    def kbd(self, node) -> str:
        return "=" + node.value + "="

    def math(self, node) -> str:
        return "\\(" + node.value + "\\)"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        return "*" * node.level + " " + self.inlines(node.children)

    def code_block(self, node) -> str:
        opening = "#+BEGIN_SRC " + node.language if node.language else "#+BEGIN_SRC"
        return opening + "\n" + node.code + "\n#+END_SRC"

    def quote(self, node) -> str:
        return "#+BEGIN_QUOTE\n" + self.blocks(node.children) + "\n#+END_QUOTE"

    def list(self, node) -> str:
        lines = []
        for number, item in enumerate(node.items, 1):
            marker = f"{number}. " if node.ordered else "- "
            lines.append(prefix_lines(self.inlines(item.children), marker, " " * len(marker)))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), " " * len(marker)))
        return "\n".join(lines)

    def table(self, node) -> str:
        def row(cells):
            return "| " + " | ".join(self.inlines(cell) for cell in cells) + " |"
        lines = [row(node.header), "|" + "+".join("---" for _ in node.header) + "|"]
        lines += [row(cells) for cells in node.rows]
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "-----"

    def image(self, node) -> str:
        caption = "#+CAPTION: " + node.alt + "\n" if node.alt else ""
        return caption + "[[" + node.src + "]]"

    def figure(self, node) -> str:
        return "#+CAPTION: " + self.inlines(node.caption) + "\n[[" + node.src + "]]"
