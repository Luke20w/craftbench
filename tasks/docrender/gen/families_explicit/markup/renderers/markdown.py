from .lightweight import LineMarkup, LineStyle


class MarkdownRenderer(LineMarkup):
    style = LineStyle(
        strong=("**", "**"), emphasis=("*", "*"), subscript=("<sub>", "</sub>"), superscript=("<sup>", "</sup>"),
        highlight=("==", "=="), code=("`", "`"), escape_code=False,
        kbd="<kbd>{value}</kbd>", math="${value}$", link="[{text}]({url})", url_escapes=" )", line_break="\\\n",
        heading=lambda level: ("#" * min(level, 6) + " ", ""),
        code_fence=lambda language, code: ("````" + language, "````") if "```" in code else ("```" + language, "```"),
        quote_prefix="> ", quote_wrap=None,
        list_nesting="indent", bullet="- ", numbered="{n}. ", list_indent=None,
        header_cells=("| ", " | ", " |"), table_cells=("| ", " | ", " |"),
        table_rule=lambda columns: "|" + "|".join(" --- " for _ in range(columns)) + "|",
        rule="---", image="![{escaped_alt}]({src})", figure_caption="\n\n*{caption}*",
    )

    def esc(self, text: str) -> str:
        for ch in "\\`*_[]#|":
            text = text.replace(ch, "\\" + ch)
        return text

    # Shapes Markdown renders its own way

    def code(self, node) -> str:
        if "`" in node.value:
            return "`` " + node.value + " ``"
        return "`" + node.value + "`"
