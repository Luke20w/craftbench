from ..text import prefix_lines
from .base import Renderer


class MarkdownRenderer(Renderer):
    def esc(self, text: str) -> str:
        for ch in "\\`*_[]#|":
            text = text.replace(ch, "\\" + ch)
        return text

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "**" + self.inlines(node.children) + "**"

    def emphasis(self, node) -> str:
        return "*" + self.inlines(node.children) + "*"

    def code(self, node) -> str:
        if "`" in node.value:
            return "`` " + node.value + " ``"
        return "`" + node.value + "`"

    def link(self, node) -> str:
        url = node.url.replace(" ", "%20").replace(")", "%29")
        return "[" + self.inlines(node.children) + "](" + url + ")"

    def line_break(self, node) -> str:
        return "\\\n"

    def subscript(self, node) -> str:
        return "<sub>" + self.inlines(node.children) + "</sub>"

    def superscript(self, node) -> str:
        return "<sup>" + self.inlines(node.children) + "</sup>"

    def highlight(self, node) -> str:
        return "==" + self.inlines(node.children) + "=="

    def kbd(self, node) -> str:
        return "<kbd>" + node.value + "</kbd>"

    def math(self, node) -> str:
        return "$" + node.value + "$"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        return "#" * min(node.level, 6) + " " + self.inlines(node.children)

    def code_block(self, node) -> str:
        fence = "````" if "```" in node.code else "```"
        return fence + node.language + "\n" + node.code + "\n" + fence

    def quote(self, node) -> str:
        return prefix_lines(self.blocks(node.children), "> ")

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
        lines = [row(node.header), "|" + "|".join(" --- " for _ in node.header) + "|"]
        lines += [row(cells) for cells in node.rows]
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "---"

    def image(self, node) -> str:
        return "![" + self.esc(node.alt) + "](" + node.src.replace(" ", "%20").replace(")", "%29") + ")"

    def figure(self, node) -> str:
        return "![" + self.esc(node.alt) + "](" + node.src.replace(" ", "%20").replace(")", "%29") + ")\n\n*" + self.inlines(node.caption) + "*"
