from ..text import prefix_lines
from .base import Renderer


class MediaWikiRenderer(Renderer):
    def esc(self, text: str) -> str:
        for ch, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("[", "&#91;"), ("]", "&#93;")):
            text = text.replace(ch, entity)
        return text

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "'''" + self.inlines(node.children) + "'''"

    def emphasis(self, node) -> str:
        return "''" + self.inlines(node.children) + "''"

    def code(self, node) -> str:
        return "<code>" + self.esc(node.value) + "</code>"

    def link(self, node) -> str:
        return "[" + node.url + " " + self.inlines(node.children) + "]"

    def line_break(self, node) -> str:
        return "<br />"

    def subscript(self, node) -> str:
        return "<sub>" + self.inlines(node.children) + "</sub>"

    def superscript(self, node) -> str:
        return "<sup>" + self.inlines(node.children) + "</sup>"

    def highlight(self, node) -> str:
        return "<mark>" + self.inlines(node.children) + "</mark>"

    def kbd(self, node) -> str:
        return "<kbd>" + self.esc(node.value) + "</kbd>"

    def math(self, node) -> str:
        return "<math>" + node.value + "</math>"

    def paragraph(self, node) -> str:
        return self.inlines(node.children)

    def heading(self, node) -> str:
        marks = "=" * (min(node.level, 5) + 1)
        return marks + " " + self.inlines(node.children) + " " + marks

    def code_block(self, node) -> str:
        if node.language:
            return '<syntaxhighlight lang="' + node.language + '">\n' + node.code + "\n</syntaxhighlight>"
        return "<pre>\n" + self.esc(node.code) + "\n</pre>"

    def quote(self, node) -> str:
        return "<blockquote>\n" + self.blocks(node.children) + "\n</blockquote>"

    def list(self, node) -> str:
        marker = "#" if node.ordered else "*"
        lines = []
        for item in node.items:
            lines.append(marker + " " + self.inlines(item.children))
            if item.sublist:
                lines.append(prefix_lines(self.render(item.sublist), marker))
        return "\n".join(lines)

    def table(self, node) -> str:
        lines = ['{| class="wikitable"', "! " + " !! ".join(self.inlines(cell) for cell in node.header)]
        for cells in node.rows:
            lines += ["|-", "| " + " || ".join(self.inlines(cell) for cell in cells)]
        lines.append("|}")
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "----"

    def image(self, node) -> str:
        return "[[File:" + node.src + "|" + self.esc(node.alt) + "]]"

    def figure(self, node) -> str:
        return "[[File:" + node.src + "|thumb|" + self.inlines(node.caption) + "]]"
