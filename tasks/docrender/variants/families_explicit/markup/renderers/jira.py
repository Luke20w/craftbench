from .lightweight import LineMarkup, LineStyle


class JiraRenderer(LineMarkup):
    style = LineStyle(
        strong=("*", "*"), emphasis=("_", "_"), subscript=("~", "~"), superscript=("^", "^"),
        highlight=("{color:#ffab00}", "{color}"), code=("{{", "}}"), escape_code=False,
        kbd="{{{{{value}}}}}", math="{{{{{value}}}}}", link="[{text}|{url}]", url_escapes="", line_break="\n",
        heading=lambda level: (f"h{min(level, 6)}. ", ""),
        code_fence=lambda language, code: ("{code:" + language + "}" if language else "{code}", "{code}"),
        quote_prefix=None, quote_wrap=("{quote}", "{quote}"),
        list_nesting="stack", bullet="*", numbered="#", list_indent=None,
        header_cells=("||", "||", "||"), table_cells=("|", "|", "|"),
        table_rule=None,
        rule="----", image=None, figure_caption="\n_{caption}_",
    )

    def esc(self, text: str) -> str:
        for ch in "\\*_{}[]|":
            text = text.replace(ch, "\\" + ch)
        return text

    # Shapes Jira renders its own way

    def image(self, node) -> str:
        return "!" + node.src + "|alt=" + node.alt + "!" if node.alt else "!" + node.src + "!"
