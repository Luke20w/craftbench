from .lightweight import LineMarkup, LineStyle


class CreoleRenderer(LineMarkup):
    style = LineStyle(
        strong=("**", "**"), emphasis=("//", "//"), subscript=(",,", ",,"), superscript=("^^", "^^"),
        highlight=("__", "__"), code=("{{{", "}}}"), escape_code=False,
        kbd="{{{{{{{value}}}}}}}", math="{{{{{{{value}}}}}}}", link="[[{url}|{text}]]", url_escapes="",
        line_break="\\\\",
        heading=lambda level: ("=" * min(level, 6) + " ", ""),
        code_fence=lambda language, code: ("{{{", "}}}"),
        quote_prefix="> ", quote_wrap=None,
        list_nesting="stack", bullet="*", numbered="#", list_indent=None,
        header_cells=("|=", "|=", "|"), table_cells=("|", "|", "|"),
        table_rule=None,
        rule="----", image="{{{{{src}|{alt}}}}}", figure_caption="\n//{caption}//",
    )

    def esc(self, text: str) -> str:
        for ch in "~*/[]{}\\|=#":
            text = text.replace(ch, "~" + ch)
        return text
