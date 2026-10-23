from ...core.interfaces import CellRenderer
from ...core.registry import REGISTRY


@REGISTRY.cell("text", "html")
class HtmlText(CellRenderer):
    def render(self, node, ctx) -> str:
        return ctx.escape(node.value)


@REGISTRY.cell("strong", "html")
class HtmlStrong(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<strong>" + ctx.inlines(node.children) + "</strong>"


@REGISTRY.cell("emphasis", "html")
class HtmlEmphasis(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<em>" + ctx.inlines(node.children) + "</em>"


@REGISTRY.cell("code", "html")
class HtmlCode(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<code>" + ctx.escape(node.value) + "</code>"


@REGISTRY.cell("link", "html")
class HtmlLink(CellRenderer):
    def render(self, node, ctx) -> str:
        return '<a href="' + ctx.escape(node.url) + '">' + ctx.inlines(node.children) + "</a>"


@REGISTRY.cell("line_break", "html")
class HtmlLineBreak(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<br>"


@REGISTRY.cell("subscript", "html")
class HtmlSubscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<sub>" + ctx.inlines(node.children) + "</sub>"


@REGISTRY.cell("superscript", "html")
class HtmlSuperscript(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<sup>" + ctx.inlines(node.children) + "</sup>"


@REGISTRY.cell("highlight", "html")
class HtmlHighlight(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<mark>" + ctx.inlines(node.children) + "</mark>"


@REGISTRY.cell("kbd", "html")
class HtmlKbd(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<kbd>" + ctx.escape(node.value) + "</kbd>"


@REGISTRY.cell("math", "html")
class HtmlMath(CellRenderer):
    def render(self, node, ctx) -> str:
        return '<span class="math">\\(' + ctx.escape(node.value) + "\\)</span>"


@REGISTRY.cell("paragraph", "html")
class HtmlParagraph(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<p>" + ctx.inlines(node.children) + "</p>"


@REGISTRY.cell("heading", "html")
class HtmlHeading(CellRenderer):
    def render(self, node, ctx) -> str:
        level = min(node.level, 6)
        return f"<h{level}>" + ctx.inlines(node.children) + f"</h{level}>"


@REGISTRY.cell("code_block", "html")
class HtmlCodeBlock(CellRenderer):
    def render(self, node, ctx) -> str:
        attr = ' class="language-' + ctx.escape(node.language) + '"' if node.language else ""
        return "<pre><code" + attr + ">" + ctx.escape(node.code) + "</code></pre>"


@REGISTRY.cell("quote", "html")
class HtmlQuote(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<blockquote>\n" + ctx.blocks(node.children) + "\n</blockquote>"


@REGISTRY.cell("list", "html")
class HtmlList(CellRenderer):
    def render(self, node, ctx) -> str:
        tag = "ol" if node.ordered else "ul"
        items = []
        for item in node.items:
            body = ctx.inlines(item.children)
            if item.sublist:
                body += "\n" + ctx.render(item.sublist)
            items.append("<li>" + body + "</li>")
        return f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>"


@REGISTRY.cell("table", "html")
class HtmlTable(CellRenderer):
    def render(self, node, ctx) -> str:
        lines = ["<table>", "<tr>" + "".join("<th>" + ctx.inlines(cell) + "</th>" for cell in node.header) + "</tr>"]
        for row in node.rows:
            lines.append("<tr>" + "".join("<td>" + ctx.inlines(cell) + "</td>" for cell in row) + "</tr>")
        lines.append("</table>")
        return "\n".join(lines)


@REGISTRY.cell("rule", "html")
class HtmlRule(CellRenderer):
    def render(self, node, ctx) -> str:
        return "<hr>"


@REGISTRY.cell("image", "html")
class HtmlImage(CellRenderer):
    def render(self, node, ctx) -> str:
        return '<img src="' + ctx.escape(node.src) + '" alt="' + ctx.escape(node.alt) + '">'


@REGISTRY.cell("figure", "html")
class HtmlFigure(CellRenderer):
    def render(self, node, ctx) -> str:
        return ('<figure>\n<img src="' + ctx.escape(node.src) + '" alt="' + ctx.escape(node.alt) + '">\n<figcaption>' + ctx.inlines(node.caption)
                + "</figcaption>\n</figure>")
