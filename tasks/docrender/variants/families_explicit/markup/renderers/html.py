from ..text import prefix_lines
from .base import Renderer


class HtmlRenderer(Renderer):
    separator = '\n'

    def esc(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def text(self, node) -> str:
        return self.esc(node.value)

    def strong(self, node) -> str:
        return "<strong>" + self.inlines(node.children) + "</strong>"

    def emphasis(self, node) -> str:
        return "<em>" + self.inlines(node.children) + "</em>"

    def code(self, node) -> str:
        return "<code>" + self.esc(node.value) + "</code>"

    def link(self, node) -> str:
        return '<a href="' + self.esc(node.url) + '">' + self.inlines(node.children) + "</a>"

    def line_break(self, node) -> str:
        return "<br>"

    def subscript(self, node) -> str:
        return "<sub>" + self.inlines(node.children) + "</sub>"

    def superscript(self, node) -> str:
        return "<sup>" + self.inlines(node.children) + "</sup>"

    def highlight(self, node) -> str:
        return "<mark>" + self.inlines(node.children) + "</mark>"

    def kbd(self, node) -> str:
        return "<kbd>" + self.esc(node.value) + "</kbd>"

    def math(self, node) -> str:
        return '<span class="math">\\(' + self.esc(node.value) + "\\)</span>"

    def paragraph(self, node) -> str:
        return "<p>" + self.inlines(node.children) + "</p>"

    def heading(self, node) -> str:
        level = min(node.level, 6)
        return f"<h{level}>" + self.inlines(node.children) + f"</h{level}>"

    def code_block(self, node) -> str:
        attr = ' class="language-' + self.esc(node.language) + '"' if node.language else ""
        return "<pre><code" + attr + ">" + self.esc(node.code) + "</code></pre>"

    def quote(self, node) -> str:
        return "<blockquote>\n" + self.blocks(node.children) + "\n</blockquote>"

    def list(self, node) -> str:
        tag = "ol" if node.ordered else "ul"
        items = []
        for item in node.items:
            body = self.inlines(item.children)
            if item.sublist:
                body += "\n" + self.render(item.sublist)
            items.append("<li>" + body + "</li>")
        return f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>"

    def table(self, node) -> str:
        lines = ["<table>", "<tr>" + "".join("<th>" + self.inlines(cell) + "</th>" for cell in node.header) + "</tr>"]
        for row in node.rows:
            lines.append("<tr>" + "".join("<td>" + self.inlines(cell) + "</td>" for cell in row) + "</tr>")
        lines.append("</table>")
        return "\n".join(lines)

    def rule(self, node) -> str:
        return "<hr>"

    def image(self, node) -> str:
        return '<img src="' + self.esc(node.src) + '" alt="' + self.esc(node.alt) + '">'

    def figure(self, node) -> str:
        return ('<figure>\n<img src="' + self.esc(node.src) + '" alt="' + self.esc(node.alt) + '">\n<figcaption>' + self.inlines(node.caption)
                + "</figcaption>\n</figure>")
