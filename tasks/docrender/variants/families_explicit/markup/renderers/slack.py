from .lightweight import LineMarkup, LineStyle


class SlackRenderer(LineMarkup):
    style = LineStyle(
        strong=("*", "*"), emphasis=("_", "_"), subscript=("", ""), superscript=("", ""),
        highlight=("*_", "_*"), code=("`", "`"), escape_code=False,
        kbd="`{value}`", math="`{value}`", link="<{url}|{text}>", url_escapes="", line_break="\n",
        heading=lambda level: ("*", "*"),
        code_fence=lambda language, code: ("```", "```"),
        quote_prefix="> ", quote_wrap=None,
        list_nesting="indent", bullet="• ", numbered="{n}. ", list_indent="    ",
        header_cells=None, table_cells=None,
        table_rule=None,
        rule="----------", image=None, figure_caption="\n_{caption}_",
    )

    def esc(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Shapes Slack renders its own way

    def table(self, node) -> str:
        rows, widths = self.aligned(node)
        lines = ["  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip() for cells in rows]
        return "```\n" + "\n".join(lines) + "\n```"

    def image(self, node) -> str:
        return "<" + node.src + "|" + (node.alt or node.src) + ">"
