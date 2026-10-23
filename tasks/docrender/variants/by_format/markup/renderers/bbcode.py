from ..text import prefix_lines
from .base import Renderer


class BBCodeRenderer(Renderer):
    def esc(self, text: str) -> str:
        return "[noparse]" + text + "[/noparse]" if "[" in text else text

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "[b]" + self.inlines(node.children) + "[/b]"

    def emphasis(self, node) -> str:
        return "[i]" + self.inlines(node.children) + "[/i]"

    def code(self, node) -> str:
        return "[icode]" + self.esc(node.value) + "[/icode]"

    def link(self, node) -> str:
        return "[url=" + node.url + "]" + self.inlines(node.children) + "[/url]"

    def line_break(self, node) -> str:
        return "\n"

    def subscript(self, node) -> str:
        return "[sub]" + self.inlines(node.children) + "[/sub]"

    def superscript(self, node) -> str:
        return "[sup]" + self.inlines(node.children) + "[/sup]"

    def highlight(self, node) -> str:
        return "[highlight]" + self.inlines(node.children) + "[/highlight]"

    def kbd(self, node) -> str:
        return "[kbd]" + node.value + "[/kbd]"

    def math(self, node) -> str:
        return "[math]" + node.value + "[/math]"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        size = {1: 200, 2: 150}.get(node.level, 120)
        return f"[size={size}%][b]" + self.inlines(node.children) + "[/b][/size]"

    def code_block(self, node) -> str:
        opening = "[code=" + node.language + "]" if node.language else "[code]"
        return opening + "\n" + node.code + "\n[/code]"

    def quote(self, node) -> str:
        return "[quote]\n" + self.blocks(node.children) + "\n[/quote]"

    def list(self, node) -> str:
        lines = ["[list=1]" if node.ordered else "[list]"]
        for item in node.items:
            lines.append("[*]" + self.inlines(item.children))
            if item.sublist:
                lines.append(self.render(item.sublist))
        lines.append("[/list]")
        return "\n".join(lines)

    def table(self, node) -> str:
        lines = ["[table]", "[tr]" + "".join("[th]" + self.inlines(cell) + "[/th]" for cell in node.header) + "[/tr]"]
        for cells in node.rows:
            lines.append("[tr]" + "".join("[td]" + self.inlines(cell) + "[/td]" for cell in cells) + "[/tr]")
        lines.append("[/table]")
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "[hr]"

    def image(self, node) -> str:
        return '[img alt="' + node.alt.replace('"', "'") + '"]' + node.src + "[/img]"

    def figure(self, node) -> str:
        return '[img alt="' + node.alt.replace('"', "'") + '"]' + node.src + "[/img]\n[i]" + self.inlines(node.caption) + "[/i]"
