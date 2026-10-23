from ..text import prefix_lines
from .lightweight import LineMarkup, LineStyle


class PlainTextRenderer(LineMarkup):
    style = LineStyle(
        strong=None, emphasis=("_", "_"), subscript=("_", ""), superscript=("^", ""),
        highlight=(">>", "<<"), code=("", ""), escape_code=False,
        kbd="[{value}]", math="{value}", link=None, url_escapes="", line_break="\n",
        heading=None,
        code_fence=None,
        quote_prefix="| ", quote_wrap=None,
        list_nesting="indent", bullet="* ", numbered="{n}) ", list_indent=None,
        header_cells=None, table_cells=None,
        table_rule=None,
        rule="* * *", image="[image: {alt}]", figure_caption="\n{caption}",
    )

    def esc(self, text: str) -> str:
        return text

    # Shapes plain text renders its own way

    def strong(self, node) -> str:
        return self.inlines(node.children).upper()

    def link(self, node) -> str:
        text = self.inlines(node.children)
        return text if text == node.url else text + " <" + node.url + ">"

    def heading(self, node) -> str:
        text = self.inlines(node.children)
        if node.level == 1:
            return text + "\n" + "=" * len(text)
        if node.level == 2:
            return text + "\n" + "-" * len(text)
        return text

    def code_block(self, node) -> str:
        return prefix_lines(node.code, "    ")

    def table(self, node) -> str:
        rows, widths = self.aligned(node)

        def line(cells):
            return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()
        lines = [line(rows[0]), "-+-".join("-" * width for width in widths)]
        lines += [line(cells) for cells in rows[1:]]
        return "\n".join(lines)
